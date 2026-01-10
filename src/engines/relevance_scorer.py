"""Relevance scoring engine for article ranking.

This module provides functions to calculate recency, relevance, and overall
scores for articles based on publication date and keyword matching.

Feature: content-agent
Implements Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6
"""

from datetime import datetime, timezone
from typing import Optional

from src.config.settings import Settings
from src.engines.article_normalizer import NormalizedArticle


def calculate_recency_score(
    published_date: datetime | None,
    window_days: int,
    reference_date: datetime | None = None
) -> float:
    """Calculate recency score (0-100) based on days since publication.
    
    The score is 100 for articles published today and decays linearly to 0
    at the edge of the recency window.
    
    Args:
        published_date: The article's publication date, or None
        window_days: Number of days for the recency window
        reference_date: Reference date for comparison (defaults to now)
        
    Returns:
        Recency score between 0 and 100. Returns 0 if published_date is None
        or if the article is outside the recency window.
        
    Example:
        >>> from datetime import datetime, timedelta
        >>> today = datetime.now()
        >>> calculate_recency_score(today, 30, today)
        100.0
        >>> calculate_recency_score(today - timedelta(days=15), 30, today)
        50.0
    """
    if published_date is None:
        return 0.0
    
    if window_days <= 0:
        return 0.0
    
    # Use current time as reference if not provided
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)
    
    # Make both datetimes timezone-aware or naive for comparison
    if published_date.tzinfo is None and reference_date.tzinfo is not None:
        # Make published_date timezone-aware (assume UTC)
        published_date = published_date.replace(tzinfo=timezone.utc)
    elif published_date.tzinfo is not None and reference_date.tzinfo is None:
        # Make reference_date timezone-aware
        reference_date = reference_date.replace(tzinfo=timezone.utc)
    
    # Calculate days since publication
    delta = reference_date - published_date
    days_old = delta.total_seconds() / (24 * 60 * 60)
    
    # If article is from the future or today, score is 100
    if days_old <= 0:
        return 100.0
    
    # If article is outside the window, score is 0
    if days_old >= window_days:
        return 0.0
    
    # Linear decay from 100 to 0 over the window
    score = 100.0 * (1.0 - days_old / window_days)
    
    return max(0.0, min(100.0, score))


def calculate_relevance_score(
    title: str,
    summary: str | None,
    keywords: dict[str, list[str]]
) -> float:
    """Calculate relevance score (0-100) based on keyword matches.
    
    Searches the title and summary for keywords from configured themes.
    The score is based on the number of unique themes matched.
    
    Args:
        title: Article title to search
        summary: Article summary/teaser to search, or None
        keywords: Dictionary mapping theme names to keyword lists
        
    Returns:
        Relevance score between 0 and 100. Returns 0 if no keywords match.
        
    Example:
        >>> keywords = {"security": ["cloud security", "encryption"]}
        >>> calculate_relevance_score("Cloud Security Best Practices", None, keywords)
        100.0
    """
    if not keywords:
        return 0.0
    
    # Combine title and summary for searching
    text_to_search = title.lower()
    if summary:
        text_to_search += " " + summary.lower()
    
    # Count how many themes have at least one keyword match
    themes_matched = 0
    total_themes = len(keywords)
    
    for theme, theme_keywords in keywords.items():
        for keyword in theme_keywords:
            if keyword.lower() in text_to_search:
                themes_matched += 1
                break  # Only count each theme once
    
    if total_themes == 0:
        return 0.0
    
    # Score based on percentage of themes matched
    score = 100.0 * themes_matched / total_themes
    
    return max(0.0, min(100.0, score))


def calculate_overall_score(
    recency_score: float,
    relevance_score: float,
    recency_weight: float = 0.4,
    relevance_weight: float = 0.6
) -> float:
    """Calculate weighted overall score from recency and relevance scores.
    
    Args:
        recency_score: Recency score (0-100)
        relevance_score: Relevance score (0-100)
        recency_weight: Weight for recency score (default 0.4)
        relevance_weight: Weight for relevance score (default 0.6)
        
    Returns:
        Overall score between 0 and 100.
        
    Example:
        >>> calculate_overall_score(100.0, 50.0, 0.4, 0.6)
        70.0
    """
    score = recency_weight * recency_score + relevance_weight * relevance_score
    return max(0.0, min(100.0, score))


def score_articles(
    articles: list[NormalizedArticle],
    settings: Settings,
    reference_date: datetime | None = None
) -> list[tuple[NormalizedArticle, float, float, float]]:
    """Score all articles and return with their scores.
    
    Args:
        articles: List of normalized articles to score
        settings: Configuration settings with scoring parameters
        reference_date: Reference date for recency calculation (defaults to now)
        
    Returns:
        List of tuples containing (article, overall_score, recency_score, relevance_score)
        
    Example:
        >>> from src.config.settings import Settings
        >>> settings = Settings()
        >>> articles = [NormalizedArticle(...)]
        >>> scored = score_articles(articles, settings)
        >>> article, overall, recency, relevance = scored[0]
    """
    results = []
    
    for article in articles:
        recency = calculate_recency_score(
            article.published_date,
            settings.recency_window_days,
            reference_date
        )
        
        relevance = calculate_relevance_score(
            article.title,
            article.summary_text,
            settings.keywords
        )
        
        overall = calculate_overall_score(
            recency,
            relevance,
            settings.recency_weight,
            settings.relevance_weight
        )
        
        results.append((article, overall, recency, relevance))
    
    return results
