#!/usr/bin/env python3
"""Run the content pipeline with Ollama-based LinkedIn post generation.

This script extends the standard pipeline to include AI-generated LinkedIn posts
using the ContentGenerator. It:
1. Runs the standard content curation pipeline
2. Generates LinkedIn posts for selected articles using Ollama
3. Writes generated posts to a separate CSV
4. Uploads both CSVs to Google Drive

Usage:
    python -m src.run_with_generator           # Production run
    python -m src.run_with_generator -v        # Verbose logging
    python -m src.run_with_generator --model llama3.2  # Use different model
"""

import argparse
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path

from src.agent.workflow import run_pipeline
from src.config.settings import load_settings
from src.connectors.google_drive import upload_file
from src.engines.generator import (
    ContentGenerator,
    GeneratedPost,
    BatchResult,
    OllamaConnectionError,
    ModelNotAvailableError,
)


logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def write_posts_csv(posts: list[GeneratedPost], output_dir: Path) -> str:
    """Write generated posts to a CSV file.
    
    Args:
        posts: List of GeneratedPost objects
        output_dir: Directory to write the CSV file
        
    Returns:
        Path to the written CSV file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"linkedin_posts_{timestamp}.csv"
    filepath = output_dir / filename
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    fieldnames = [
        "source_url",
        "hook",
        "value",
        "cta",
        "full_text",
        "hashtags",
        "character_count",
        "model_used",
        "generated_at",
    ]
    
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for post in posts:
            writer.writerow({
                "source_url": post.source_url,
                "hook": post.hook,
                "value": post.value,
                "cta": post.cta,
                "full_text": post.full_text,
                "hashtags": "; ".join(post.hashtags),
                "character_count": post.character_count,
                "model_used": post.model_used,
                "generated_at": post.generated_at.isoformat(),
            })
    
    logger.info(f"Wrote {len(posts)} posts to {filepath}")
    return str(filepath)


def main() -> int:
    """Main entry point for the pipeline with generator."""
    parser = argparse.ArgumentParser(
        description="Run content pipeline with LinkedIn post generation"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--model",
        default="llama4:scout",
        help="Ollama model to use (default: llama4:scout)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout in seconds for Ollama requests (default: 120)"
    )
    parser.add_argument(
        "--skip-generation",
        action="store_true",
        help="Skip post generation, only run curation pipeline"
    )
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    logger.info("Starting content pipeline with generator...")
    
    # Load settings
    try:
        settings = load_settings()
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        return 1
    
    # Run the standard curation pipeline
    logger.info("Running content curation pipeline...")
    result = run_pipeline(settings)
    
    if not result.success:
        logger.error("Pipeline failed to produce articles")
        return 1
    
    logger.info(f"Pipeline completed: {result.metrics.selected_count} articles selected")
    
    if args.skip_generation:
        logger.info("Skipping post generation (--skip-generation flag)")
        return 0
    
    # Get the scored articles from the pipeline
    # We need to re-read them from the CSV or access them differently
    # For now, let's read from the CSV that was just written
    if not result.csv_path:
        logger.error("No CSV path available from pipeline")
        return 1
    
    # Read scored articles from CSV and convert to ScoredArticle objects
    from src.engines.article_normalizer import ScoredArticle
    from dateutil import parser as date_parser
    
    scored_articles: list[ScoredArticle] = []
    try:
        with open(result.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Parse the CSV row back into a ScoredArticle
                published_date = None
                if row.get("published_date"):
                    try:
                        published_date = date_parser.parse(row["published_date"])
                    except Exception:
                        pass
                
                collected_at = datetime.now()
                if row.get("collected_at"):
                    try:
                        collected_at = date_parser.parse(row["collected_at"])
                    except Exception:
                        pass
                
                article = ScoredArticle(
                    source=row.get("source", ""),
                    title=row.get("title", ""),
                    url=row.get("url", ""),
                    published_date=published_date,
                    author=row.get("author"),
                    summary=row.get("summary", ""),
                    key_topics=row.get("key_topics", "").split("; ") if row.get("key_topics") else [],
                    why_it_matters=row.get("why_it_matters", ""),
                    suggested_linkedin_angle=row.get("suggested_linkedin_angle", ""),
                    suggested_hashtags=row.get("suggested_hashtags", "").split("; ") if row.get("suggested_hashtags") else [],
                    score_overall=float(row.get("score_overall", 0)),
                    score_recency=float(row.get("score_recency", 0)),
                    score_relevance=float(row.get("score_relevance", 0)),
                    collected_at=collected_at,
                )
                scored_articles.append(article)
    except Exception as e:
        logger.error(f"Failed to read articles from CSV: {e}")
        return 1
    
    if not scored_articles:
        logger.warning("No articles to generate posts for")
        return 0
    
    logger.info(f"Loaded {len(scored_articles)} articles for post generation")
    
    # Initialize the ContentGenerator
    try:
        generator = ContentGenerator(
            model=args.model,
            timeout=args.timeout,
        )
        logger.info(f"ContentGenerator initialized with model: {args.model}")
    except OllamaConnectionError as e:
        logger.error(f"Cannot connect to Ollama: {e}")
        logger.error("Make sure Ollama is running: ollama serve")
        return 1
    except ModelNotAvailableError as e:
        logger.error(f"Model not available: {e}")
        logger.error(f"Pull the model with: ollama pull {args.model}")
        return 1
    except Exception as e:
        logger.error(f"Failed to initialize ContentGenerator: {e}")
        return 1
    
    # Generate posts for all articles
    logger.info("Generating LinkedIn posts...")
    batch_result: BatchResult = generator.generate_batch(scored_articles)
    
    logger.info(
        f"Generation complete: {len(batch_result.successful)} successful, "
        f"{len(batch_result.failed)} failed "
        f"({batch_result.success_rate:.1%} success rate)"
    )
    
    if batch_result.failed:
        logger.warning("Failed articles:")
        for title, error in batch_result.failed:
            logger.warning(f"  - {title}: {error}")
    
    if not batch_result.successful:
        logger.error("No posts were generated successfully")
        return 1
    
    # Write posts to CSV
    output_dir = Path("src/output")
    posts_csv_path = write_posts_csv(batch_result.successful, output_dir)
    
    # Upload posts CSV to Google Drive
    if settings.google_drive_folder_id:
        logger.info("Uploading posts CSV to Google Drive...")
        upload_result = upload_file(
            posts_csv_path,
            settings.google_drive_folder_id,
        )
        if upload_result.success:
            logger.info(f"Posts CSV uploaded: {upload_result.file_id}")
        else:
            logger.warning(f"Failed to upload posts CSV: {upload_result.error}")
    else:
        logger.info("Google Drive upload skipped: no folder ID configured")
    
    logger.info("Pipeline with generation completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
