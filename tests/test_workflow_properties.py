"""Property-based tests for workflow orchestrator.

Feature: content-agent
Tests Property 2 from the design document.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

import pytest
from hypothesis import given, settings, strategies as st

from src.config.settings import Settings
from src.engines.article_normalizer import RawArticle
from src.agent.workflow import _fetch_from_sources


@runtime_checkable
class SourceFetcher(Protocol):
    """Protocol for source fetchers."""
    
    @property
    def source_name(self) -> str:
        ...
    
    def fetch(self, limit: int) -> list[RawArticle]:
        ...


class MockSuccessFetcher:
    """Mock fetcher that always succeeds."""
    
    def __init__(self, source_name: str, articles: list[RawArticle]):
        self._source_name = source_name
        self._articles = articles
    
    @property
    def source_name(self) -> str:
        return self._source_name
    
    def fetch(self, limit: int) -> list[RawArticle]:
        return self._articles[:limit]


class MockFailingFetcher:
    """Mock fetcher that always raises an exception."""
    
    def __init__(self, source_name: str, error_message: str = "Fetch failed"):
        self._source_name = source_name
        self._error_message = error_message
    
    @property
    def source_name(self) -> str:
        return self._source_name
    
    def fetch(self, limit: int) -> list[RawArticle]:
        raise RuntimeError(self._error_message)


# Strategy for generating RawArticle objects
@st.composite
def raw_article_strategy(draw, source: str = "Test Source"):
    """Generate a valid RawArticle for testing."""
    title = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        whitelist_characters=' '
    )))
    # Ensure title is not empty after stripping
    if not title.strip():
        title = "Test Article"
    
    url_id = draw(st.integers(min_value=1, max_value=100000))
    url = f"https://example.com/article-{url_id}"
    
    return RawArticle(
        source=source,
        title=title,
        url=url,
        published_date="2024-01-15",
        author="Test Author",
        teaser="Test teaser content.",
    )


# Feature: content-agent, Property 2: Source Fetch Isolation
# Validates: Requirements 1.1, 1.2
class TestSourceFetchIsolation:
    """Property tests for source fetch isolation.
    
    For any set of configured sources where one or more sources fail,
    the Content_Agent SHALL still return articles from the sources that succeeded.
    """

    @given(
        num_success_articles=st.integers(min_value=1, max_value=20),
        limit=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_failing_source_does_not_affect_successful_source(
        self, num_success_articles: int, limit: int
    ):
        """When one source fails, articles from successful sources SHALL still be returned."""
        # Create articles for the successful source
        success_articles = [
            RawArticle(
                source="Success Source",
                title=f"Article {i}",
                url=f"https://success.com/article-{i}",
                published_date="2024-01-15",
            )
            for i in range(num_success_articles)
        ]
        
        # Create fetchers: one succeeds, one fails
        success_fetcher = MockSuccessFetcher("Success Source", success_articles)
        failing_fetcher = MockFailingFetcher("Failing Source", "Network error")
        
        fetchers = [success_fetcher, failing_fetcher]
        
        # Execute fetch
        articles, counts, errors = _fetch_from_sources(fetchers, limit)
        
        # Verify successful source articles are returned
        expected_count = min(num_success_articles, limit)
        assert len(articles) == expected_count, (
            f"Expected {expected_count} articles from successful source, got {len(articles)}"
        )
        
        # Verify counts are correct
        assert counts["Success Source"] == expected_count
        assert counts["Failing Source"] == 0
        
        # Verify error was logged
        assert len(errors) == 1
        assert "Failing Source" in errors[0]

    @given(
        num_articles_source1=st.integers(min_value=1, max_value=10),
        num_articles_source2=st.integers(min_value=1, max_value=10),
        limit=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_multiple_successful_sources_combined(
        self, num_articles_source1: int, num_articles_source2: int, limit: int
    ):
        """When multiple sources succeed, all articles SHALL be combined."""
        # Create articles for both sources
        articles1 = [
            RawArticle(
                source="Source 1",
                title=f"S1 Article {i}",
                url=f"https://source1.com/article-{i}",
            )
            for i in range(num_articles_source1)
        ]
        articles2 = [
            RawArticle(
                source="Source 2",
                title=f"S2 Article {i}",
                url=f"https://source2.com/article-{i}",
            )
            for i in range(num_articles_source2)
        ]
        
        fetcher1 = MockSuccessFetcher("Source 1", articles1)
        fetcher2 = MockSuccessFetcher("Source 2", articles2)
        
        fetchers = [fetcher1, fetcher2]
        
        articles, counts, errors = _fetch_from_sources(fetchers, limit)
        
        # Verify total count
        expected_from_1 = min(num_articles_source1, limit)
        expected_from_2 = min(num_articles_source2, limit)
        expected_total = expected_from_1 + expected_from_2
        
        assert len(articles) == expected_total, (
            f"Expected {expected_total} total articles, got {len(articles)}"
        )
        
        # Verify per-source counts
        assert counts["Source 1"] == expected_from_1
        assert counts["Source 2"] == expected_from_2
        
        # Verify no errors
        assert len(errors) == 0

    @given(
        num_articles=st.integers(min_value=1, max_value=20),
        limit=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_all_sources_fail_returns_empty(
        self, num_articles: int, limit: int
    ):
        """When all sources fail, an empty list SHALL be returned with errors logged."""
        failing_fetcher1 = MockFailingFetcher("Failing Source 1", "Error 1")
        failing_fetcher2 = MockFailingFetcher("Failing Source 2", "Error 2")
        
        fetchers = [failing_fetcher1, failing_fetcher2]
        
        articles, counts, errors = _fetch_from_sources(fetchers, limit)
        
        # Verify no articles returned
        assert len(articles) == 0
        
        # Verify counts are zero
        assert counts["Failing Source 1"] == 0
        assert counts["Failing Source 2"] == 0
        
        # Verify errors were logged for both
        assert len(errors) == 2

    @given(
        num_success_articles=st.integers(min_value=1, max_value=10),
        num_failing_sources=st.integers(min_value=1, max_value=3),
        limit=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_one_success_among_multiple_failures(
        self, num_success_articles: int, num_failing_sources: int, limit: int
    ):
        """When one source succeeds among multiple failures, its articles SHALL be returned."""
        success_articles = [
            RawArticle(
                source="Success Source",
                title=f"Article {i}",
                url=f"https://success.com/article-{i}",
            )
            for i in range(num_success_articles)
        ]
        
        fetchers = []
        
        # Add failing fetchers
        for i in range(num_failing_sources):
            fetchers.append(MockFailingFetcher(f"Failing Source {i}", f"Error {i}"))
        
        # Add successful fetcher
        fetchers.append(MockSuccessFetcher("Success Source", success_articles))
        
        articles, counts, errors = _fetch_from_sources(fetchers, limit)
        
        # Verify successful source articles are returned
        expected_count = min(num_success_articles, limit)
        assert len(articles) == expected_count
        
        # Verify errors logged for failing sources
        assert len(errors) == num_failing_sources

    def test_empty_fetchers_list_returns_empty(self):
        """When no fetchers are configured, an empty list SHALL be returned."""
        articles, counts, errors = _fetch_from_sources([], 10)
        
        assert len(articles) == 0
        assert len(counts) == 0
        assert len(errors) == 0

    @given(
        num_articles=st.integers(min_value=0, max_value=20),
        limit=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_source_returning_empty_list_is_not_error(
        self, num_articles: int, limit: int
    ):
        """A source returning an empty list SHALL not be treated as an error."""
        # One source with articles, one with none
        articles = [
            RawArticle(
                source="Source With Articles",
                title=f"Article {i}",
                url=f"https://example.com/article-{i}",
            )
            for i in range(num_articles)
        ]
        
        fetcher_with_articles = MockSuccessFetcher("Source With Articles", articles)
        fetcher_empty = MockSuccessFetcher("Empty Source", [])
        
        fetchers = [fetcher_with_articles, fetcher_empty]
        
        result_articles, counts, errors = _fetch_from_sources(fetchers, limit)
        
        # Verify no errors (empty list is valid)
        assert len(errors) == 0
        
        # Verify counts
        expected_count = min(num_articles, limit)
        assert counts["Source With Articles"] == expected_count
        assert counts["Empty Source"] == 0
