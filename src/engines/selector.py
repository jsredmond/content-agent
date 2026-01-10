"""Article selector for choosing top N articles by score.

Feature: content-agent
Implements article selection based on overall score with threshold filtering.
"""

from src.engines.article_normalizer import NormalizedArticle


def select_top_articles(
    scored_articles: list[tuple[NormalizedArticle, float, float, float]],
    target_count: int,
    min_threshold: float = 0.0,
) -> list[tuple[NormalizedArticle, float, float, float]]:
    """Select top N articles by overall score.
    
    Sorts articles by overall_score in descending order, filters out articles
    below the minimum threshold, and returns the top N articles.
    
    Args:
        scored_articles: List of tuples (article, overall_score, recency_score, relevance_score)
        target_count: Maximum number of articles to select
        min_threshold: Minimum overall_score required for selection (default 0.0)
        
    Returns:
        List of top N articles sorted by overall_score descending,
        filtered to only include articles with overall_score >= min_threshold.
        Returns all qualifying articles if fewer than target_count are available.
        
    Example:
        >>> articles = [
        ...     (article1, 85.0, 90.0, 80.0),
        ...     (article2, 70.0, 60.0, 75.0),
        ...     (article3, 95.0, 100.0, 90.0),
        ... ]
        >>> selected = select_top_articles(articles, target_count=2, min_threshold=50.0)
        >>> len(selected)
        2
        >>> selected[0][1]  # Highest score first
        95.0
    
    Requirements:
        - 6.1: Sort articles by overall_score in descending order
        - 6.2: Select top N articles (configurable)
        - 6.4: Exclude articles with overall_score below minimum threshold
    """
    # Filter by minimum threshold
    filtered = [
        item for item in scored_articles
        if item[1] >= min_threshold  # item[1] is overall_score
    ]
    
    # Sort by overall_score descending
    sorted_articles = sorted(filtered, key=lambda x: x[1], reverse=True)
    
    # Select top N (or all if fewer available)
    return sorted_articles[:target_count]
