"""Article data models and normalization utilities."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawArticle:
    """Represents an article as fetched from a source before normalization.
    
    Attributes:
        source: Source identifier (e.g., "AWS News Blog")
        title: Article title as scraped
        url: Article URL as scraped (may contain tracking params)
        published_date: Date string in source format
        author: Author name if available
        teaser: Teaser or first paragraph
    """
    source: str
    title: str
    url: str
    published_date: str | None = None
    author: str | None = None
    teaser: str | None = None


@dataclass
class NormalizedArticle:
    """Represents an article after normalization with standardized fields.
    
    Attributes:
        source: Source identifier
        title: Cleaned title
        canonical_url: URL with tracking params removed
        published_date: Parsed datetime
        author: Author name
        summary_text: Teaser/summary text
    """
    source: str
    title: str
    canonical_url: str
    published_date: datetime | None = None
    author: str | None = None
    summary_text: str | None = None


@dataclass
class ScoredArticle:
    """Represents a fully processed article ready for CSV output.
    
    Attributes:
        source: Source identifier
        title: Article title
        url: Canonical URL
        published_date: Publication date
        author: Author name
        summary: Generated 1-3 sentence summary
        key_topics: Extracted topic keywords
        why_it_matters: Security-first framing statement
        suggested_linkedin_angle: LinkedIn post angle
        suggested_hashtags: Relevant hashtags
        score_overall: Weighted overall score (0-100)
        score_recency: Recency score (0-100)
        score_relevance: Relevance score (0-100)
        collected_at: Timestamp of collection
    """
    source: str
    title: str
    url: str
    published_date: datetime | None
    author: str | None
    summary: str
    key_topics: list[str]
    why_it_matters: str
    suggested_linkedin_angle: str
    suggested_hashtags: list[str]
    score_overall: float
    score_recency: float
    score_relevance: float
    collected_at: datetime
