"""Content type filter for identifying technical articles.

This module provides filtering functionality to identify and retain only
technical articles such as announcements, releases, walkthroughs, and tutorials.

Feature: content-agent
"""

import logging
from src.engines.article_normalizer import NormalizedArticle

logger = logging.getLogger(__name__)


def is_technical_article(
    article: NormalizedArticle,
    technical_keywords: list[str],
) -> bool:
    """Check if an article is a technical article based on keyword matching.

    Searches the article title and summary for keywords that indicate
    technical content like announcements, releases, tutorials, etc.

    Args:
        article: The normalized article to check
        technical_keywords: List of keywords indicating technical content

    Returns:
        True if the article matches any technical keyword, False otherwise
    """
    if not technical_keywords:
        return True  # No filtering if no keywords configured

    # Combine title and summary for searching
    text_to_search = article.title.lower()
    if article.summary_text:
        text_to_search += " " + article.summary_text.lower()

    # Check for any matching keyword
    for keyword in technical_keywords:
        if keyword.lower() in text_to_search:
            return True

    return False


def filter_technical_articles(
    articles: list[NormalizedArticle],
    technical_keywords: list[str],
) -> list[NormalizedArticle]:
    """Filter articles to retain only technical content.

    Filters a list of articles to keep only those that match technical
    content keywords (announcements, releases, tutorials, etc.).

    Args:
        articles: List of normalized articles to filter
        technical_keywords: List of keywords indicating technical content

    Returns:
        List of articles that match technical content criteria
    """
    if not technical_keywords:
        logger.info("No technical keywords configured, skipping filter")
        return articles

    filtered = [
        article for article in articles
        if is_technical_article(article, technical_keywords)
    ]

    excluded_count = len(articles) - len(filtered)
    logger.info(
        f"Technical filter: kept {len(filtered)} articles, "
        f"excluded {excluded_count} non-technical articles"
    )

    return filtered
