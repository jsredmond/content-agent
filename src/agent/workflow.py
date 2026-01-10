"""Workflow orchestrator for the content agent pipeline.

This module provides the main pipeline orchestration, coordinating all stages
from source fetching through CSV output and Google Drive upload.

Feature: content-agent
Implements Requirements 1.1, 1.2, 9.6
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from src.config.settings import Settings
from src.connectors.google_drive import UploadResult, upload_file
from src.engines.article_normalizer import (
    NormalizedArticle,
    RawArticle,
    ScoredArticle,
    normalize_articles,
)
from src.engines.aws_news_blog_scraper import AWSNewsBlogScraper
from src.engines.csv_writer import write_csv
from src.engines.deduplication import deduplicate
from src.engines.observability import (
    RunMetrics,
    create_run_metrics,
    log_stage_counts,
    write_run_log,
)
from src.engines.purview_blog_scraper import PurviewBlogScraper
from src.engines.relevance_scorer import score_articles
from src.engines.selector import select_top_articles
from src.engines.summarizer import (
    extract_key_topics,
    generate_hashtags,
    generate_linkedin_angle,
    generate_summary,
    generate_why_it_matters,
)


logger = logging.getLogger(__name__)


@runtime_checkable
class SourceFetcher(Protocol):
    """Protocol for source fetchers."""
    
    @property
    def source_name(self) -> str:
        """Return the source identifier."""
        ...
    
    def fetch(self, limit: int) -> list[RawArticle]:
        """Fetch articles from the source up to limit."""
        ...


@dataclass
class WorkflowResult:
    """Result of a pipeline workflow execution.
    
    Attributes:
        success: Whether the pipeline completed successfully
        csv_path: Path to the generated CSV file, or None if failed
        upload_result: Result of Google Drive upload, or None if skipped
        metrics: Run metrics collected during execution
    """
    success: bool
    csv_path: str | None
    upload_result: UploadResult | None
    metrics: RunMetrics



def _fetch_from_sources(
    fetchers: list[SourceFetcher],
    limit: int,
) -> tuple[list[RawArticle], dict[str, int], list[str]]:
    """Fetch articles from all sources, handling failures gracefully.
    
    Each source is fetched independently. If one source fails, the pipeline
    continues with the remaining sources.
    
    Args:
        fetchers: List of source fetcher instances
        limit: Maximum articles to fetch per source
        
    Returns:
        Tuple of (all_articles, counts_by_source, errors)
    """
    all_articles: list[RawArticle] = []
    counts_by_source: dict[str, int] = {}
    errors: list[str] = []
    
    for fetcher in fetchers:
        source_name = fetcher.source_name
        try:
            logger.info(f"Fetching articles from {source_name}...")
            articles = fetcher.fetch(limit)
            all_articles.extend(articles)
            counts_by_source[source_name] = len(articles)
            logger.info(f"Fetched {len(articles)} articles from {source_name}")
        except Exception as e:
            error_msg = f"Failed to fetch from {source_name}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            counts_by_source[source_name] = 0
    
    return all_articles, counts_by_source, errors


def _create_scored_articles(
    selected: list[tuple[NormalizedArticle, float, float, float]],
    settings: Settings,
) -> list[ScoredArticle]:
    """Convert selected articles to ScoredArticle format with generated metadata.
    
    Args:
        selected: List of (article, overall, recency, relevance) tuples
        settings: Configuration settings
        
    Returns:
        List of ScoredArticle objects ready for CSV output
    """
    scored_articles: list[ScoredArticle] = []
    collected_at = datetime.now()
    
    for article, overall, recency, relevance in selected:
        # Extract topics and generate metadata
        topics = extract_key_topics(article, settings.keywords)
        summary = generate_summary(article)
        why_it_matters = generate_why_it_matters(article, topics)
        linkedin_angle = generate_linkedin_angle(article)
        hashtags = generate_hashtags(topics)
        
        scored_article = ScoredArticle(
            source=article.source,
            title=article.title,
            url=article.canonical_url,
            published_date=article.published_date,
            author=article.author,
            summary=summary,
            key_topics=topics,
            why_it_matters=why_it_matters,
            suggested_linkedin_angle=linkedin_angle,
            suggested_hashtags=hashtags,
            score_overall=overall,
            score_recency=recency,
            score_relevance=relevance,
            collected_at=collected_at,
        )
        scored_articles.append(scored_article)
    
    return scored_articles


def _calculate_top_topics(scored_articles: list[ScoredArticle]) -> list[str]:
    """Calculate the most common topics among selected articles.
    
    Args:
        scored_articles: List of scored articles
        
    Returns:
        List of topic names sorted by frequency (most common first)
    """
    topic_counts: dict[str, int] = {}
    for article in scored_articles:
        for topic in article.key_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    
    # Sort by count descending
    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
    return [topic for topic, _ in sorted_topics]


def _calculate_average_score(scored_articles: list[ScoredArticle]) -> float:
    """Calculate average overall score of selected articles.
    
    Args:
        scored_articles: List of scored articles
        
    Returns:
        Average overall score, or 0.0 if no articles
    """
    if not scored_articles:
        return 0.0
    total = sum(a.score_overall for a in scored_articles)
    return total / len(scored_articles)


def run_pipeline(settings: Settings) -> WorkflowResult:
    """Execute the full content curation pipeline.
    
    Orchestrates all pipeline stages:
    1. Fetch articles from configured sources
    2. Normalize articles to common schema
    3. Deduplicate by URL and title
    4. Score for recency and relevance
    5. Generate summaries and LinkedIn metadata
    6. Select top N articles
    7. Write CSV output
    8. Upload to Google Drive
    9. Write run log
    
    Handles errors gracefully, continuing on partial failures where possible.
    
    Args:
        settings: Configuration settings for the pipeline
        
    Returns:
        WorkflowResult containing success status, paths, and metrics
        
    Requirements:
        - 1.1: Fetch articles from each configured source independently
        - 1.2: Log errors and continue with remaining sources on failure
        - 9.6: Log errors and continue processing where possible
    """
    run_timestamp = datetime.now()
    errors: list[str] = []
    
    logger.info("Starting content agent pipeline...")
    
    # Initialize source fetchers
    fetchers: list[SourceFetcher] = [
        AWSNewsBlogScraper(settings),
        PurviewBlogScraper(settings),
    ]
    
    # Stage 1: Fetch from all sources
    raw_articles, fetched_counts, fetch_errors = _fetch_from_sources(
        fetchers, settings.max_articles_per_source
    )
    errors.extend(fetch_errors)
    log_stage_counts("fetched", len(raw_articles))
    
    # Stage 2: Normalize articles
    normalized = normalize_articles(raw_articles)
    log_stage_counts("normalized", len(normalized))
    
    # Stage 3: Deduplicate
    dedup_result = deduplicate(normalized)
    deduped = dedup_result.articles
    log_stage_counts("deduped", len(deduped))
    
    # Stage 4: Score articles
    scored = score_articles(deduped, settings)
    
    # Stage 5: Select top articles
    selected = select_top_articles(
        scored,
        settings.target_selected,
        settings.min_score_threshold,
    )
    log_stage_counts("selected", len(selected))
    
    # Stage 6: Generate metadata and create ScoredArticles
    scored_articles = _create_scored_articles(selected, settings)
    
    # Stage 7: Write CSV
    csv_path: str | None = None
    try:
        csv_path = write_csv(scored_articles)
        logger.info(f"CSV written to {csv_path}")
    except Exception as e:
        error_msg = f"Failed to write CSV: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
    
    # Stage 8: Upload to Google Drive
    upload_result: UploadResult | None = None
    upload_status = "skipped"
    uploaded_file_id: str | None = None
    
    if csv_path and settings.google_drive_folder_id:
        try:
            upload_result = upload_file(
                csv_path,
                settings.google_drive_folder_id,
            )
            if upload_result.success:
                upload_status = "success"
                uploaded_file_id = upload_result.file_id
                logger.info(f"Uploaded to Google Drive: {uploaded_file_id}")
            else:
                upload_status = "failed"
                if upload_result.error:
                    errors.append(upload_result.error)
        except Exception as e:
            upload_status = "failed"
            error_msg = f"Failed to upload to Google Drive: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    elif not settings.google_drive_folder_id:
        logger.info("Google Drive upload skipped: no folder ID configured")
    
    # Stage 9: Create metrics and write run log
    top_topics = _calculate_top_topics(scored_articles)
    avg_score = _calculate_average_score(scored_articles)
    
    metrics = create_run_metrics(
        fetched_count_by_source=fetched_counts,
        normalized_count=len(normalized),
        deduped_count=len(deduped),
        selected_count=len(scored_articles),
        top_topics=top_topics,
        average_score_overall=avg_score,
        upload_status=upload_status,
        uploaded_file_id=uploaded_file_id,
        errors=errors,
        run_timestamp=run_timestamp,
    )
    
    try:
        log_path = write_run_log(metrics)
        logger.info(f"Run log written to {log_path}")
    except Exception as e:
        error_msg = f"Failed to write run log: {str(e)}"
        logger.error(error_msg)
        # Don't add to errors since metrics already created
    
    # Determine overall success
    # Pipeline is successful if we have articles and CSV was written
    success = csv_path is not None and len(scored_articles) > 0
    
    logger.info(
        f"Pipeline completed. Success: {success}, "
        f"Selected: {len(scored_articles)} articles"
    )
    
    return WorkflowResult(
        success=success,
        csv_path=csv_path,
        upload_result=upload_result,
        metrics=metrics,
    )
