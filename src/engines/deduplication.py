"""Deduplication engine for removing duplicate articles."""

import logging
import re
from dataclasses import dataclass

from src.engines.article_normalizer import NormalizedArticle


logger = logging.getLogger(__name__)


@dataclass
class DeduplicationResult:
    """Result of deduplication operation.
    
    Attributes:
        articles: List of deduplicated articles
        removed_count: Total number of articles removed
        removed_by_url: Number of articles removed due to duplicate URLs
        removed_by_title: Number of articles removed due to duplicate titles
    """
    articles: list[NormalizedArticle]
    removed_count: int
    removed_by_url: int
    removed_by_title: int


def normalize_title(title: str) -> str:
    """Normalize title for comparison.
    
    Converts to lowercase and collapses all whitespace to single spaces.
    
    Args:
        title: The title to normalize
        
    Returns:
        Normalized title string
        
    Example:
        >>> normalize_title("  Hello   World  ")
        'hello world'
        >>> normalize_title("AWS News Blog")
        'aws news blog'
    """
    if not title:
        return ""
    
    # Lowercase
    normalized = title.lower()
    
    # Collapse whitespace (including newlines, tabs) to single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Strip leading/trailing whitespace
    normalized = normalized.strip()
    
    return normalized



def deduplicate(articles: list[NormalizedArticle]) -> DeduplicationResult:
    """Remove duplicate articles by URL and title.
    
    Performs two-pass deduplication:
    1. First pass: Remove articles with duplicate canonical URLs
    2. Second pass: Remove articles with duplicate normalized titles
    
    When duplicates are found, keeps the article with the earliest published_date.
    Articles with None published_date are considered "newer" than any dated article.
    
    Args:
        articles: List of normalized articles to deduplicate
        
    Returns:
        DeduplicationResult containing deduplicated articles and removal counts
        
    Example:
        >>> from datetime import datetime
        >>> articles = [
        ...     NormalizedArticle(source="AWS", title="Hello", canonical_url="https://a.com/1",
        ...                       published_date=datetime(2024, 1, 15)),
        ...     NormalizedArticle(source="AWS", title="Hello", canonical_url="https://a.com/2",
        ...                       published_date=datetime(2024, 1, 10)),
        ... ]
        >>> result = deduplicate(articles)
        >>> len(result.articles)
        1
        >>> result.articles[0].published_date
        datetime.datetime(2024, 1, 10, 0, 0)
    """
    if not articles:
        return DeduplicationResult(
            articles=[],
            removed_count=0,
            removed_by_url=0,
            removed_by_title=0,
        )
    
    input_count = len(articles)
    
    # First pass: deduplicate by canonical URL
    url_deduped = _deduplicate_by_key(
        articles,
        key_func=lambda a: a.canonical_url,
    )
    removed_by_url = input_count - len(url_deduped)
    
    if removed_by_url > 0:
        logger.info(f"Removed {removed_by_url} articles with duplicate URLs")
    
    # Second pass: deduplicate by normalized title
    title_deduped = _deduplicate_by_key(
        url_deduped,
        key_func=lambda a: normalize_title(a.title),
    )
    removed_by_title = len(url_deduped) - len(title_deduped)
    
    if removed_by_title > 0:
        logger.info(f"Removed {removed_by_title} articles with duplicate titles")
    
    removed_count = input_count - len(title_deduped)
    
    return DeduplicationResult(
        articles=title_deduped,
        removed_count=removed_count,
        removed_by_url=removed_by_url,
        removed_by_title=removed_by_title,
    )


def _deduplicate_by_key(
    articles: list[NormalizedArticle],
    key_func: callable,
) -> list[NormalizedArticle]:
    """Deduplicate articles by a key function, keeping earliest published.
    
    Args:
        articles: List of articles to deduplicate
        key_func: Function to extract the deduplication key from an article
        
    Returns:
        List of deduplicated articles
    """
    # Group articles by key
    seen: dict[str, NormalizedArticle] = {}
    
    for article in articles:
        key = key_func(article)
        
        if key not in seen:
            seen[key] = article
        else:
            # Keep the one with earliest published_date
            existing = seen[key]
            seen[key] = _keep_earliest(existing, article)
    
    # Preserve original order for articles that were kept
    result = []
    seen_keys = set()
    for article in articles:
        key = key_func(article)
        if key not in seen_keys:
            result.append(seen[key])
            seen_keys.add(key)
    
    return result


def _keep_earliest(a: NormalizedArticle, b: NormalizedArticle) -> NormalizedArticle:
    """Return the article with the earliest published_date.
    
    Articles with None published_date are considered "newer" than dated articles.
    If both have None, returns the first article.
    
    Args:
        a: First article
        b: Second article
        
    Returns:
        The article with the earlier published_date
    """
    # If both have dates, compare them
    if a.published_date is not None and b.published_date is not None:
        return a if a.published_date <= b.published_date else b
    
    # If only one has a date, prefer the one with a date (it's "earlier")
    if a.published_date is not None:
        return a
    if b.published_date is not None:
        return b
    
    # Both are None, keep the first one
    return a
