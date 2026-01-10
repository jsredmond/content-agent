"""Property-based tests for article deduplication.

Feature: content-agent
Tests Properties 7, 8, 9, and 10 from the design document.
"""

from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings, strategies as st, assume

from src.engines.article_normalizer import NormalizedArticle
from src.engines.deduplication import (
    DeduplicationResult,
    deduplicate,
    normalize_title,
)


# Strategy for generating NormalizedArticle instances
@st.composite
def normalized_article_strategy(draw, url=None, title=None, published_date=None):
    """Generate a NormalizedArticle with optional fixed fields."""
    sources = ["AWS News Blog", "Microsoft Purview Blog", "Test Source"]
    
    return NormalizedArticle(
        source=draw(st.sampled_from(sources)),
        title=title if title is not None else draw(st.text(min_size=1, max_size=100)),
        canonical_url=url if url is not None else draw(st.sampled_from([
            f"https://example.com/article/{draw(st.integers(min_value=1, max_value=10000))}",
            f"https://aws.amazon.com/blogs/{draw(st.integers(min_value=1, max_value=10000))}",
            f"https://microsoft.com/blog/{draw(st.integers(min_value=1, max_value=10000))}",
        ])),
        published_date=published_date if published_date is not None else draw(st.one_of(
            st.none(),
            st.datetimes(
                min_value=datetime(2020, 1, 1),
                max_value=datetime(2026, 12, 31),
            ),
        )),
        author=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        summary_text=draw(st.one_of(st.none(), st.text(min_size=0, max_size=200))),
    )


@st.composite
def articles_with_unique_urls(draw):
    """Generate a list of articles with unique URLs."""
    num_articles = draw(st.integers(min_value=0, max_value=20))
    articles = []
    used_urls = set()
    
    for i in range(num_articles):
        url = f"https://example.com/article/{i}"
        used_urls.add(url)
        article = draw(normalized_article_strategy(url=url))
        articles.append(article)
    
    return articles


@st.composite
def articles_with_duplicate_urls(draw):
    """Generate a list of articles that may have duplicate URLs."""
    num_unique_urls = draw(st.integers(min_value=1, max_value=10))
    urls = [f"https://example.com/article/{i}" for i in range(num_unique_urls)]
    
    num_articles = draw(st.integers(min_value=num_unique_urls, max_value=num_unique_urls * 3))
    articles = []
    
    for _ in range(num_articles):
        url = draw(st.sampled_from(urls))
        article = draw(normalized_article_strategy(url=url))
        articles.append(article)
    
    return articles


@st.composite
def articles_with_duplicate_titles(draw):
    """Generate a list of articles with unique URLs but potentially duplicate titles."""
    num_unique_titles = draw(st.integers(min_value=1, max_value=10))
    titles = [f"Article Title {i}" for i in range(num_unique_titles)]
    
    num_articles = draw(st.integers(min_value=num_unique_titles, max_value=num_unique_titles * 3))
    articles = []
    
    for i in range(num_articles):
        url = f"https://example.com/article/{i}"  # Unique URLs
        title = draw(st.sampled_from(titles))
        article = draw(normalized_article_strategy(url=url, title=title))
        articles.append(article)
    
    return articles


# Feature: content-agent, Property 7: Deduplication URL Uniqueness
# Validates: Requirements 3.1
class TestDeduplicationURLUniqueness:
    """Property tests for URL uniqueness after deduplication."""

    @given(articles=articles_with_duplicate_urls())
    @settings(max_examples=100)
    def test_all_urls_unique_after_deduplication(self, articles: list[NormalizedArticle]):
        """For any list of articles, after deduplication, all canonical URLs SHALL be unique."""
        result = deduplicate(articles)
        
        urls = [a.canonical_url for a in result.articles]
        unique_urls = set(urls)
        
        assert len(urls) == len(unique_urls), (
            f"Duplicate URLs found after deduplication: {urls}"
        )

    @given(articles=articles_with_unique_urls())
    @settings(max_examples=100)
    def test_unique_urls_preserved(self, articles: list[NormalizedArticle]):
        """For any list of articles with unique URLs, all articles SHALL be preserved (URL-wise)."""
        result = deduplicate(articles)
        
        # All unique URLs should still be present
        input_urls = {a.canonical_url for a in articles}
        output_urls = {a.canonical_url for a in result.articles}
        
        # Output URLs should be subset of input (titles might cause dedup)
        assert output_urls.issubset(input_urls)

    def test_empty_list_returns_empty(self):
        """Empty input should return empty result."""
        result = deduplicate([])
        
        assert result.articles == []
        assert result.removed_count == 0
        assert result.removed_by_url == 0
        assert result.removed_by_title == 0

    def test_single_article_preserved(self):
        """Single article should be preserved."""
        article = NormalizedArticle(
            source="Test",
            title="Test Article",
            canonical_url="https://example.com/article",
            published_date=datetime(2024, 1, 15),
        )
        
        result = deduplicate([article])
        
        assert len(result.articles) == 1
        assert result.articles[0] == article
        assert result.removed_count == 0



# Feature: content-agent, Property 8: Deduplication Title Uniqueness
# Validates: Requirements 3.2
class TestDeduplicationTitleUniqueness:
    """Property tests for title uniqueness after deduplication."""

    @given(articles=articles_with_duplicate_titles())
    @settings(max_examples=100)
    def test_all_titles_unique_after_deduplication(self, articles: list[NormalizedArticle]):
        """For any list of articles after URL deduplication, after title deduplication, all normalized titles SHALL be unique."""
        result = deduplicate(articles)
        
        normalized_titles = [normalize_title(a.title) for a in result.articles]
        unique_titles = set(normalized_titles)
        
        assert len(normalized_titles) == len(unique_titles), (
            f"Duplicate titles found after deduplication: {normalized_titles}"
        )

    @given(
        base_title=st.text(
            alphabet=st.characters(whitelist_categories=('L',), whitelist_characters=' '),
            min_size=1,
            max_size=50
        ).filter(lambda x: x.strip() and x.upper() == x.upper() and x.lower() == x.lower()),
        num_duplicates=st.integers(min_value=2, max_value=5),
    )
    @settings(max_examples=100)
    def test_case_insensitive_title_dedup(self, base_title: str, num_duplicates: int):
        """Title deduplication SHALL be case-insensitive."""
        assume(base_title.strip())  # Ensure non-empty after strip
        # Ensure upper/lower case produce same normalized result
        assume(base_title.upper().lower() == base_title.lower())
        
        # Create articles with same title in different cases
        articles = []
        for i in range(num_duplicates):
            # Alternate between upper and lower case
            title = base_title.upper() if i % 2 == 0 else base_title.lower()
            article = NormalizedArticle(
                source="Test",
                title=title,
                canonical_url=f"https://example.com/article/{i}",
                published_date=datetime(2024, 1, 15) - timedelta(days=i),
            )
            articles.append(article)
        
        result = deduplicate(articles)
        
        # Should only have one article after dedup
        assert len(result.articles) == 1

    @given(
        base_title=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N')),
            min_size=2,
            max_size=30
        ),
    )
    @settings(max_examples=100)
    def test_whitespace_normalized_title_dedup(self, base_title: str):
        """Title deduplication SHALL normalize whitespace."""
        assume(base_title.strip())  # Ensure non-empty
        
        # Create articles with same title but different whitespace
        articles = [
            NormalizedArticle(
                source="Test",
                title=base_title,
                canonical_url="https://example.com/article/1",
                published_date=datetime(2024, 1, 15),
            ),
            NormalizedArticle(
                source="Test",
                title=f"  {base_title}  ",  # Extra whitespace
                canonical_url="https://example.com/article/2",
                published_date=datetime(2024, 1, 10),
            ),
            NormalizedArticle(
                source="Test",
                title=base_title.replace(" ", "   ") if " " in base_title else f"{base_title}  extra",
                canonical_url="https://example.com/article/3",
                published_date=datetime(2024, 1, 5),
            ),
        ]
        
        result = deduplicate(articles)
        
        # Titles that normalize to the same value should be deduped
        normalized_titles = [normalize_title(a.title) for a in result.articles]
        unique_titles = set(normalized_titles)
        assert len(normalized_titles) == len(unique_titles)

    def test_normalize_title_lowercase(self):
        """normalize_title SHALL convert to lowercase."""
        assert normalize_title("HELLO WORLD") == "hello world"
        assert normalize_title("Hello World") == "hello world"

    def test_normalize_title_collapse_whitespace(self):
        """normalize_title SHALL collapse whitespace."""
        assert normalize_title("hello   world") == "hello world"
        assert normalize_title("  hello  world  ") == "hello world"
        assert normalize_title("hello\t\nworld") == "hello world"

    def test_normalize_title_empty(self):
        """normalize_title SHALL handle empty strings."""
        assert normalize_title("") == ""
        assert normalize_title("   ") == ""



# Feature: content-agent, Property 9: Deduplication Keeps Earliest
# Validates: Requirements 3.3
class TestDeduplicationKeepsEarliest:
    """Property tests for keeping earliest article when duplicates found."""

    @given(
        num_duplicates=st.integers(min_value=2, max_value=10),
        base_date=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2025, 12, 31),
        ),
    )
    @settings(max_examples=100)
    def test_keeps_earliest_by_url(self, num_duplicates: int, base_date: datetime):
        """For duplicate URLs, the article with earliest published_date SHALL be kept."""
        # Create articles with same URL but different dates
        articles = []
        earliest_date = None
        
        for i in range(num_duplicates):
            date = base_date + timedelta(days=i * 10)  # Spread dates apart
            if earliest_date is None or date < earliest_date:
                earliest_date = date
            
            article = NormalizedArticle(
                source="Test",
                title=f"Article {i}",  # Different titles
                canonical_url="https://example.com/same-url",  # Same URL
                published_date=date,
            )
            articles.append(article)
        
        result = deduplicate(articles)
        
        # Should have exactly one article
        assert len(result.articles) == 1
        # The kept article should have the earliest date
        assert result.articles[0].published_date == earliest_date

    @given(
        num_duplicates=st.integers(min_value=2, max_value=10),
        base_date=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2025, 12, 31),
        ),
    )
    @settings(max_examples=100)
    def test_keeps_earliest_by_title(self, num_duplicates: int, base_date: datetime):
        """For duplicate titles, the article with earliest published_date SHALL be kept."""
        # Create articles with same title but different URLs and dates
        articles = []
        earliest_date = None
        
        for i in range(num_duplicates):
            date = base_date + timedelta(days=i * 10)  # Spread dates apart
            if earliest_date is None or date < earliest_date:
                earliest_date = date
            
            article = NormalizedArticle(
                source="Test",
                title="Same Title",  # Same title
                canonical_url=f"https://example.com/article/{i}",  # Different URLs
                published_date=date,
            )
            articles.append(article)
        
        result = deduplicate(articles)
        
        # Should have exactly one article
        assert len(result.articles) == 1
        # The kept article should have the earliest date
        assert result.articles[0].published_date == earliest_date

    @given(
        dates=st.lists(
            st.datetimes(
                min_value=datetime(2020, 1, 1),
                max_value=datetime(2025, 12, 31),
            ),
            min_size=2,
            max_size=10,
            unique=True,
        ),
    )
    @settings(max_examples=100)
    def test_keeps_earliest_regardless_of_order(self, dates: list[datetime]):
        """Earliest article SHALL be kept regardless of input order."""
        import random
        
        earliest_date = min(dates)
        
        # Create articles with same URL, shuffle the order
        articles = []
        for i, date in enumerate(dates):
            article = NormalizedArticle(
                source="Test",
                title=f"Article {i}",
                canonical_url="https://example.com/same-url",
                published_date=date,
            )
            articles.append(article)
        
        # Shuffle to randomize order
        random.shuffle(articles)
        
        result = deduplicate(articles)
        
        assert len(result.articles) == 1
        assert result.articles[0].published_date == earliest_date

    def test_none_date_treated_as_newer(self):
        """Articles with None published_date SHALL be treated as newer than dated articles."""
        articles = [
            NormalizedArticle(
                source="Test",
                title="Article 1",
                canonical_url="https://example.com/same-url",
                published_date=None,  # No date
            ),
            NormalizedArticle(
                source="Test",
                title="Article 2",
                canonical_url="https://example.com/same-url",
                published_date=datetime(2024, 1, 15),  # Has date
            ),
        ]
        
        result = deduplicate(articles)
        
        # Should keep the one with a date (it's "earlier")
        assert len(result.articles) == 1
        assert result.articles[0].published_date == datetime(2024, 1, 15)

    def test_both_none_dates_keeps_first(self):
        """When both articles have None dates, the first one SHALL be kept."""
        articles = [
            NormalizedArticle(
                source="Test",
                title="First Article",
                canonical_url="https://example.com/same-url",
                published_date=None,
            ),
            NormalizedArticle(
                source="Test",
                title="Second Article",
                canonical_url="https://example.com/same-url",
                published_date=None,
            ),
        ]
        
        result = deduplicate(articles)
        
        assert len(result.articles) == 1
        assert result.articles[0].title == "First Article"



# Feature: content-agent, Property 10: Deduplication Count Invariant
# Validates: Requirements 3.4
class TestDeduplicationCountInvariant:
    """Property tests for deduplication count invariant."""

    @given(articles=articles_with_duplicate_urls())
    @settings(max_examples=100)
    def test_removed_count_equals_input_minus_output(self, articles: list[NormalizedArticle]):
        """For any deduplication, removed_count SHALL equal input count minus output count."""
        input_count = len(articles)
        result = deduplicate(articles)
        output_count = len(result.articles)
        
        assert result.removed_count == input_count - output_count, (
            f"removed_count ({result.removed_count}) != "
            f"input ({input_count}) - output ({output_count})"
        )

    @given(articles=articles_with_duplicate_titles())
    @settings(max_examples=100)
    def test_removed_count_with_title_duplicates(self, articles: list[NormalizedArticle]):
        """For any deduplication with title duplicates, count invariant SHALL hold."""
        input_count = len(articles)
        result = deduplicate(articles)
        output_count = len(result.articles)
        
        assert result.removed_count == input_count - output_count

    @given(articles=articles_with_duplicate_urls())
    @settings(max_examples=100)
    def test_removed_by_url_plus_title_equals_total(self, articles: list[NormalizedArticle]):
        """removed_by_url + removed_by_title SHALL equal removed_count."""
        result = deduplicate(articles)
        
        assert result.removed_by_url + result.removed_by_title == result.removed_count, (
            f"removed_by_url ({result.removed_by_url}) + "
            f"removed_by_title ({result.removed_by_title}) != "
            f"removed_count ({result.removed_count})"
        )

    @given(
        num_url_duplicates=st.integers(min_value=0, max_value=5),
        num_title_duplicates=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=100)
    def test_counts_are_non_negative(self, num_url_duplicates: int, num_title_duplicates: int):
        """All count fields SHALL be non-negative."""
        # Create articles with controlled duplicates
        articles = []
        
        # Add articles with duplicate URLs
        for i in range(num_url_duplicates + 1):
            articles.append(NormalizedArticle(
                source="Test",
                title=f"URL Dup Article {i}",
                canonical_url="https://example.com/url-dup",
                published_date=datetime(2024, 1, 15) - timedelta(days=i),
            ))
        
        # Add articles with duplicate titles (unique URLs)
        for i in range(num_title_duplicates + 1):
            articles.append(NormalizedArticle(
                source="Test",
                title="Title Dup Article",
                canonical_url=f"https://example.com/title-dup/{i}",
                published_date=datetime(2024, 1, 15) - timedelta(days=i),
            ))
        
        result = deduplicate(articles)
        
        assert result.removed_count >= 0
        assert result.removed_by_url >= 0
        assert result.removed_by_title >= 0

    def test_no_duplicates_zero_removed(self):
        """When no duplicates exist, removed counts SHALL be zero."""
        articles = [
            NormalizedArticle(
                source="Test",
                title=f"Unique Article {i}",
                canonical_url=f"https://example.com/article/{i}",
                published_date=datetime(2024, 1, 15),
            )
            for i in range(5)
        ]
        
        result = deduplicate(articles)
        
        assert result.removed_count == 0
        assert result.removed_by_url == 0
        assert result.removed_by_title == 0
        assert len(result.articles) == 5

    def test_all_duplicates_removed_correctly(self):
        """When all articles are duplicates, counts SHALL be correct."""
        articles = [
            NormalizedArticle(
                source="Test",
                title="Same Title",
                canonical_url="https://example.com/same-url",
                published_date=datetime(2024, 1, 15) - timedelta(days=i),
            )
            for i in range(5)
        ]
        
        result = deduplicate(articles)
        
        # Should have 1 article left
        assert len(result.articles) == 1
        # 4 removed total
        assert result.removed_count == 4
        # All removed by URL (first pass)
        assert result.removed_by_url == 4
        # None removed by title (already deduped by URL)
        assert result.removed_by_title == 0
