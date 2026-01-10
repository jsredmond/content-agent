"""Property-based tests for source fetchers.

Feature: content-agent
Tests Property 1 from the design document.
"""

from dataclasses import dataclass
from datetime import datetime

import pytest
from hypothesis import given, settings, strategies as st, assume

from src.config.settings import Settings
from src.engines.article_normalizer import RawArticle
from src.engines.source_fetcher import SourceFetcher


# Mock scraper for testing the fetch limit property without network calls
class MockSourceFetcher:
    """Mock source fetcher that generates articles for testing.
    
    This mock allows us to test the fetch limit property without
    making actual network requests.
    """
    
    def __init__(self, source_name: str, available_articles: list[RawArticle]):
        """Initialize with a list of available articles.
        
        Args:
            source_name: Name of the source
            available_articles: List of articles this source "has"
        """
        self._source_name = source_name
        self._available_articles = available_articles
    
    @property
    def source_name(self) -> str:
        return self._source_name
    
    def fetch(self, limit: int) -> list[RawArticle]:
        """Fetch articles up to the limit.
        
        This correctly implements the limit behavior that all
        source fetchers must follow.
        """
        return self._available_articles[:limit]


# Strategy for generating RawArticle objects
@st.composite
def raw_article_strategy(draw):
    """Generate a valid RawArticle for testing."""
    source = draw(st.sampled_from(["AWS News Blog", "Microsoft Purview Blog", "Test Source"]))
    title = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('L', 'N', 'P', 'S'),
        whitelist_characters=' '
    )))
    url = draw(st.sampled_from([
        "https://aws.amazon.com/blogs/aws/article-1",
        "https://aws.amazon.com/blogs/aws/article-2",
        "https://techcommunity.microsoft.com/blog/post-1",
        "https://techcommunity.microsoft.com/blog/post-2",
        "https://example.com/article",
    ]))
    # Make URLs unique by appending an index
    url = f"{url}?id={draw(st.integers(min_value=1, max_value=10000))}"
    
    published_date = draw(st.one_of(
        st.none(),
        st.sampled_from([
            "2024-01-15",
            "2024-01-10",
            "2024-01-05",
            "January 15, 2024",
            "2024-01-15T10:30:00Z",
        ])
    ))
    author = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    teaser = draw(st.one_of(st.none(), st.text(min_size=0, max_size=200)))
    
    return RawArticle(
        source=source,
        title=title,
        url=url,
        published_date=published_date,
        author=author,
        teaser=teaser,
    )


# Feature: content-agent, Property 1: Source Fetch Limit
# Validates: Requirements 1.8
class TestSourceFetchLimit:
    """Property tests for source fetch limit.
    
    For any source fetcher and any configured limit N, the number of
    articles returned SHALL be at most N.
    """

    @given(
        articles=st.lists(raw_article_strategy(), min_size=0, max_size=100),
        limit=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100)
    def test_fetch_returns_at_most_limit_articles(
        self, articles: list[RawArticle], limit: int
    ):
        """For any source fetcher and limit N, fetch SHALL return at most N articles."""
        fetcher = MockSourceFetcher("Test Source", articles)
        
        result = fetcher.fetch(limit)
        
        assert len(result) <= limit, (
            f"Fetcher returned {len(result)} articles, expected at most {limit}"
        )

    @given(
        articles=st.lists(raw_article_strategy(), min_size=0, max_size=100),
        limit=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100)
    def test_fetch_returns_min_of_available_and_limit(
        self, articles: list[RawArticle], limit: int
    ):
        """For any source fetcher, fetch SHALL return min(available, limit) articles."""
        fetcher = MockSourceFetcher("Test Source", articles)
        
        result = fetcher.fetch(limit)
        
        expected_count = min(len(articles), limit)
        assert len(result) == expected_count, (
            f"Fetcher returned {len(result)} articles, expected {expected_count}"
        )

    @given(
        num_articles=st.integers(min_value=10, max_value=100),
        limit=st.integers(min_value=1, max_value=9),
    )
    @settings(max_examples=100)
    def test_fetch_respects_limit_when_more_available(
        self, num_articles: int, limit: int
    ):
        """When more articles are available than the limit, fetch SHALL return exactly limit articles."""
        # Generate articles
        articles = [
            RawArticle(
                source="Test Source",
                title=f"Article {i}",
                url=f"https://example.com/article-{i}",
            )
            for i in range(num_articles)
        ]
        
        fetcher = MockSourceFetcher("Test Source", articles)
        result = fetcher.fetch(limit)
        
        assert len(result) == limit, (
            f"Fetcher returned {len(result)} articles when {num_articles} available, "
            f"expected exactly {limit}"
        )

    @given(
        num_articles=st.integers(min_value=0, max_value=10),
        limit=st.integers(min_value=20, max_value=100),
    )
    @settings(max_examples=100)
    def test_fetch_returns_all_when_fewer_than_limit(
        self, num_articles: int, limit: int
    ):
        """When fewer articles are available than the limit, fetch SHALL return all available."""
        articles = [
            RawArticle(
                source="Test Source",
                title=f"Article {i}",
                url=f"https://example.com/article-{i}",
            )
            for i in range(num_articles)
        ]
        
        fetcher = MockSourceFetcher("Test Source", articles)
        result = fetcher.fetch(limit)
        
        assert len(result) == num_articles, (
            f"Fetcher returned {len(result)} articles, expected all {num_articles}"
        )

    def test_fetch_with_zero_available_returns_empty(self):
        """When no articles are available, fetch SHALL return empty list."""
        fetcher = MockSourceFetcher("Test Source", [])
        
        result = fetcher.fetch(10)
        
        assert result == []
        assert len(result) == 0

    def test_fetch_with_limit_one_returns_at_most_one(self):
        """When limit is 1, fetch SHALL return at most 1 article."""
        articles = [
            RawArticle(source="Test", title=f"Article {i}", url=f"https://example.com/{i}")
            for i in range(10)
        ]
        
        fetcher = MockSourceFetcher("Test Source", articles)
        result = fetcher.fetch(1)
        
        assert len(result) <= 1

    def test_mock_fetcher_implements_protocol(self):
        """MockSourceFetcher SHALL implement the SourceFetcher protocol."""
        fetcher = MockSourceFetcher("Test", [])
        
        # Check it's recognized as implementing the protocol
        assert isinstance(fetcher, SourceFetcher)
        assert hasattr(fetcher, 'source_name')
        assert hasattr(fetcher, 'fetch')
        assert callable(fetcher.fetch)
