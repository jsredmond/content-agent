"""Article data models and normalization utilities."""

import logging
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import tldextract
from dateutil import parser as date_parser
from dateutil.parser import ParserError


logger = logging.getLogger(__name__)


# Tracking parameters to strip from URLs (all lowercase for case-insensitive matching)
TRACKING_PARAMS = frozenset({
    # UTM parameters
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'utm_id', 'utm_source_platform', 'utm_creative_format', 'utm_marketing_tactic',
    # Facebook
    'fbclid', 'fb_action_ids', 'fb_action_types', 'fb_source', 'fb_ref',
    # Google
    'gclid', 'gclsrc', 'dclid',
    # Microsoft/Bing
    'msclkid',
    # Twitter
    'twclid',
    # LinkedIn
    'li_fat_id',
    # Other common tracking params
    'mc_cid', 'mc_eid',  # Mailchimp
    '_ga', '_gl',  # Google Analytics
    'ref', 'ref_src', 'ref_url',
    'source', 'src',
    'trk', 'trkinfo',  # LinkedIn tracking (lowercase for matching)
    'clickid', 'click_id',
    'campaign_id', 'ad_id', 'adset_id',
})


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


def normalize_url(url: str) -> str:
    """Strip tracking parameters and normalize URL to canonical form.
    
    Removes common tracking parameters (utm_*, fbclid, gclid, etc.) from URLs
    while preserving the essential path and non-tracking query parameters.
    
    Args:
        url: The URL to normalize, may contain tracking parameters
        
    Returns:
        Canonical URL with tracking parameters removed
        
    Example:
        >>> normalize_url("https://example.com/article?utm_source=twitter&id=123")
        'https://example.com/article?id=123'
    """
    if not url:
        return url
    
    parsed = urlparse(url)
    
    # Parse query parameters and filter out tracking params
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    
    # Filter out tracking parameters (case-insensitive check)
    filtered_params = {
        key: values
        for key, values in query_params.items()
        if key.lower() not in TRACKING_PARAMS
        and not key.lower().startswith('utm_')  # Catch any utm_ variants
    }
    
    # Rebuild query string with filtered params
    # Use doseq=True to handle multiple values for same key
    new_query = urlencode(filtered_params, doseq=True) if filtered_params else ''
    
    # Reconstruct URL without tracking params
    canonical = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        ''  # Remove fragment as well for canonical form
    ))
    
    return canonical


def parse_date(date_str: str | None) -> datetime | None:
    """Parse a date string into a datetime object.
    
    Uses python-dateutil for flexible parsing of various date formats.
    Returns None on parse failure instead of raising an exception.
    
    Args:
        date_str: Date string in any common format, or None
        
    Returns:
        Parsed datetime object, or None if parsing fails or input is None
        
    Example:
        >>> parse_date("2024-01-15T10:30:00Z")
        datetime.datetime(2024, 1, 15, 10, 30, tzinfo=tzutc())
        >>> parse_date("January 15, 2024")
        datetime.datetime(2024, 1, 15, 0, 0)
        >>> parse_date("invalid date")
        None
    """
    if date_str is None:
        return None
    
    if not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    if not date_str:
        return None
    
    try:
        return date_parser.parse(date_str)
    except (ParserError, ValueError, OverflowError) as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None


def normalize_text(text: str | None) -> str | None:
    """Normalize text by trimming whitespace and normalizing unicode.
    
    Performs the following normalizations:
    - Strips leading and trailing whitespace
    - Normalizes unicode to NFC form (canonical composition)
    - Collapses multiple consecutive whitespace characters to single space
    
    Args:
        text: Text string to normalize, or None
        
    Returns:
        Normalized text string, or None if input is None
        
    Example:
        >>> normalize_text("  Hello   World  ")
        'Hello World'
        >>> normalize_text("café")  # Already NFC
        'café'
    """
    if text is None:
        return None
    
    import unicodedata
    import re
    
    # Normalize unicode to NFC form
    normalized = unicodedata.normalize('NFC', text)
    
    # Strip leading and trailing whitespace
    normalized = normalized.strip()
    
    # Collapse multiple whitespace to single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    return normalized


def normalize_article(raw: RawArticle) -> NormalizedArticle:
    """Convert a RawArticle to a NormalizedArticle.
    
    Applies URL canonicalization, date parsing, and text normalization
    to produce a standardized article record.
    
    Args:
        raw: The raw article fetched from a source
        
    Returns:
        NormalizedArticle with standardized fields
        
    Example:
        >>> raw = RawArticle(
        ...     source="AWS News Blog",
        ...     title="  New Feature  ",
        ...     url="https://aws.amazon.com/blog?utm_source=twitter",
        ...     published_date="2024-01-15",
        ...     author="Jane Doe",
        ...     teaser="  Check out this feature  "
        ... )
        >>> normalized = normalize_article(raw)
        >>> normalized.title
        'New Feature'
        >>> normalized.canonical_url
        'https://aws.amazon.com/blog'
    """
    return NormalizedArticle(
        source=raw.source,
        title=normalize_text(raw.title) or raw.title,
        canonical_url=normalize_url(raw.url),
        published_date=parse_date(raw.published_date),
        author=normalize_text(raw.author),
        summary_text=normalize_text(raw.teaser),
    )


def normalize_articles(articles: list[RawArticle]) -> list[NormalizedArticle]:
    """Normalize a batch of articles.
    
    Converts a list of RawArticle objects to NormalizedArticle objects,
    applying URL canonicalization, date parsing, and text normalization
    to each article.
    
    Args:
        articles: List of raw articles to normalize
        
    Returns:
        List of normalized articles
        
    Example:
        >>> raw_articles = [
        ...     RawArticle(source="AWS", title="Article 1", url="https://aws.com/1"),
        ...     RawArticle(source="AWS", title="Article 2", url="https://aws.com/2"),
        ... ]
        >>> normalized = normalize_articles(raw_articles)
        >>> len(normalized)
        2
    """
    return [normalize_article(raw) for raw in articles]
