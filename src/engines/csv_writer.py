"""CSV writer for exporting curated articles.

This module provides functions to format ScoredArticle objects and write them
to CSV files with proper encoding and formatting.

Feature: content-agent
Implements Requirements 7.1, 7.2, 7.3, 7.4
"""

import csv
import os
from datetime import datetime
from pathlib import Path

from src.engines.article_normalizer import ScoredArticle


# CSV column headers matching the required schema
CSV_COLUMNS = [
    'source',
    'title',
    'url',
    'published_date',
    'author',
    'summary',
    'key_topics',
    'why_it_matters',
    'suggested_linkedin_angle',
    'suggested_hashtags',
    'score_overall',
    'score_recency',
    'score_relevance',
    'collected_at',
]


def format_scored_article_for_csv(article: ScoredArticle) -> dict[str, str]:
    """Format a ScoredArticle's fields for CSV output.
    
    Converts all fields to string format suitable for CSV writing.
    Multi-value fields (key_topics, suggested_hashtags) use semicolon delimiters.
    
    Args:
        article: The ScoredArticle to format
        
    Returns:
        Dictionary with string values for all CSV columns
        
    Example:
        >>> article = ScoredArticle(
        ...     source="AWS News Blog",
        ...     title="New Feature",
        ...     url="https://aws.amazon.com/blog/new-feature",
        ...     published_date=datetime(2024, 1, 15),
        ...     author="Jane Doe",
        ...     summary="A new feature was released.",
        ...     key_topics=["cloud security", "identity"],
        ...     why_it_matters="Improves security posture.",
        ...     suggested_linkedin_angle="Check out this new feature!",
        ...     suggested_hashtags=["#AWS", "#CloudSecurity"],
        ...     score_overall=85.5,
        ...     score_recency=90.0,
        ...     score_relevance=82.0,
        ...     collected_at=datetime(2024, 1, 16, 10, 30),
        ... )
        >>> formatted = format_scored_article_for_csv(article)
        >>> formatted['key_topics']
        'cloud security;identity'
    """
    # Format datetime fields
    published_date_str = ''
    if article.published_date is not None:
        published_date_str = article.published_date.isoformat()
    
    collected_at_str = article.collected_at.isoformat()
    
    # Format multi-value fields with semicolon delimiter
    key_topics_str = ';'.join(article.key_topics)
    suggested_hashtags_str = ';'.join(article.suggested_hashtags)
    
    # Format author (handle None)
    author_str = article.author if article.author is not None else ''
    
    return {
        'source': article.source,
        'title': article.title,
        'url': article.url,
        'published_date': published_date_str,
        'author': author_str,
        'summary': article.summary,
        'key_topics': key_topics_str,
        'why_it_matters': article.why_it_matters,
        'suggested_linkedin_angle': article.suggested_linkedin_angle,
        'suggested_hashtags': suggested_hashtags_str,
        'score_overall': str(article.score_overall),
        'score_recency': str(article.score_recency),
        'score_relevance': str(article.score_relevance),
        'collected_at': collected_at_str,
    }


def write_csv(
    articles: list[ScoredArticle],
    output_dir: str = "src/output"
) -> str:
    """Write articles to a CSV file with timestamped filename.
    
    Creates a CSV file in the specified output directory with filename format:
    content_candidates_YYYYMMDD_HHMMSS.csv
    
    The file is encoded as UTF-8 and includes all required columns.
    
    Args:
        articles: List of ScoredArticle objects to write
        output_dir: Directory path for output file (default: "src/output")
        
    Returns:
        The filepath of the written CSV file
        
    Raises:
        OSError: If the output directory cannot be created or file cannot be written
        
    Example:
        >>> articles = [...]  # List of ScoredArticle objects
        >>> filepath = write_csv(articles)
        >>> filepath
        'src/output/content_candidates_20240116_103045.csv'
    """
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamped filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"content_candidates_{timestamp}.csv"
    filepath = output_path / filename
    
    # Write CSV with UTF-8 encoding
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        
        for article in articles:
            row = format_scored_article_for_csv(article)
            writer.writerow(row)
    
    return str(filepath)
