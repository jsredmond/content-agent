"""Property-based tests for article selector.

Feature: content-agent
Tests Properties 18, 19, and 20 from the design document.
"""

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings, strategies as st, assume

from src.engines.article_normalizer import NormalizedArticle
from src.engines.selector import select_top_articles


# Strategies for generating test data
@st.composite
def normalized_article_strategy(draw):
    """Generate NormalizedArticle instances for testing."""
    source = draw(st.sampled_from(["AWS News Blog", "Microsoft Purview Blog"]))
    title = draw(st.text(min_size=1, max_size=200))
    url = draw(st.text(min_size=10, max_size=100).map(lambda s: f"https://example.com/{s}"))
    published_date = draw(st.one_of(
        st.none(),
        st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
    ))
    author = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    summary_text = draw(st.one_of(st.none(), st.text(min_size=0, max_size=500)))
    
    return NormalizedArticle(
        source=source,
        title=title,
        canonical_url=url,
        published_date=published_date,
        author=author,
        summary_text=summary_text,
    )


@st.composite
def scored_article_strategy(draw):
    """Generate a scored article tuple (article, overall, recency, relevance)."""
    article = draw(normalized_article_strategy())
    overall_score = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False))
    recency_score = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False))
    relevance_score = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False))
    
    return (article, overall_score, recency_score, relevance_score)


@st.composite
def scored_articles_list_strategy(draw, min_size=0, max_size=20):
    """Generate a list of scored article tuples."""
    return draw(st.lists(scored_article_strategy(), min_size=min_size, max_size=max_size))


# Feature: content-agent, Property 18: Selection Sorting
# Validates: Requirements 6.1
class TestSelectionSorting:
    """Property tests for selection sorting.
    
    For any list of selected articles, the articles SHALL be sorted
    by overall_score in descending order.
    """

    @given(
        scored_articles=scored_articles_list_strategy(min_size=0, max_size=20),
        target_count=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_selected_articles_sorted_descending(
        self,
        scored_articles: list[tuple[NormalizedArticle, float, float, float]],
        target_count: int,
    ):
        """Selected articles SHALL be sorted by overall_score in descending order."""
        selected = select_top_articles(scored_articles, target_count)
        
        # Verify descending order
        for i in range(len(selected) - 1):
            current_score = selected[i][1]
            next_score = selected[i + 1][1]
            assert current_score >= next_score, (
                f"Articles not sorted: score {current_score} at index {i} "
                f"should be >= score {next_score} at index {i + 1}"
            )

    @given(
        scored_articles=scored_articles_list_strategy(min_size=2, max_size=20),
        target_count=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_highest_score_first(
        self,
        scored_articles: list[tuple[NormalizedArticle, float, float, float]],
        target_count: int,
    ):
        """The first selected article SHALL have the highest overall_score."""
        assume(len(scored_articles) > 0)
        
        selected = select_top_articles(scored_articles, target_count)
        
        if len(selected) > 0:
            max_score_in_input = max(item[1] for item in scored_articles)
            first_selected_score = selected[0][1]
            assert first_selected_score == max_score_in_input, (
                f"First selected score {first_selected_score} should equal "
                f"max input score {max_score_in_input}"
            )


# Feature: content-agent, Property 19: Selection Count
# Validates: Requirements 6.2
class TestSelectionCount:
    """Property tests for selection count.
    
    For any target count N and list of M articles (after threshold filtering),
    the selected count SHALL be min(N, M).
    """

    @given(
        scored_articles=scored_articles_list_strategy(min_size=0, max_size=30),
        target_count=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_selection_count_is_min_of_target_and_available(
        self,
        scored_articles: list[tuple[NormalizedArticle, float, float, float]],
        target_count: int,
    ):
        """Selected count SHALL be min(N, M) where N is target and M is available."""
        selected = select_top_articles(scored_articles, target_count, min_threshold=0.0)
        
        expected_count = min(target_count, len(scored_articles))
        assert len(selected) == expected_count, (
            f"Expected {expected_count} articles, got {len(selected)}"
        )

    @given(
        scored_articles=scored_articles_list_strategy(min_size=5, max_size=20),
    )
    @settings(max_examples=100)
    def test_target_count_limits_selection(
        self,
        scored_articles: list[tuple[NormalizedArticle, float, float, float]],
    ):
        """When more articles available than target, selection SHALL be limited to target."""
        target_count = 3
        assume(len(scored_articles) > target_count)
        
        selected = select_top_articles(scored_articles, target_count)
        
        assert len(selected) == target_count, (
            f"Expected exactly {target_count} articles, got {len(selected)}"
        )

    def test_empty_input_returns_empty(self):
        """Empty input list should return empty selection."""
        selected = select_top_articles([], target_count=10)
        assert selected == []

    def test_fewer_than_target_returns_all(self):
        """When fewer articles than target, all should be returned."""
        article = NormalizedArticle(
            source="Test",
            title="Test Article",
            canonical_url="https://example.com/test",
        )
        scored_articles = [
            (article, 80.0, 70.0, 85.0),
            (article, 60.0, 50.0, 65.0),
        ]
        
        selected = select_top_articles(scored_articles, target_count=10)
        
        assert len(selected) == 2


# Feature: content-agent, Property 20: Selection Threshold
# Validates: Requirements 6.4
class TestSelectionThreshold:
    """Property tests for selection threshold.
    
    For any minimum threshold T, all selected articles SHALL have
    overall_score >= T.
    """

    @given(
        scored_articles=scored_articles_list_strategy(min_size=0, max_size=20),
        target_count=st.integers(min_value=1, max_value=50),
        min_threshold=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_all_selected_above_threshold(
        self,
        scored_articles: list[tuple[NormalizedArticle, float, float, float]],
        target_count: int,
        min_threshold: float,
    ):
        """All selected articles SHALL have overall_score >= min_threshold."""
        selected = select_top_articles(scored_articles, target_count, min_threshold)
        
        for item in selected:
            overall_score = item[1]
            assert overall_score >= min_threshold, (
                f"Selected article with score {overall_score} is below "
                f"threshold {min_threshold}"
            )

    @given(
        scored_articles=scored_articles_list_strategy(min_size=1, max_size=20),
        min_threshold=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_threshold_filters_low_scores(
        self,
        scored_articles: list[tuple[NormalizedArticle, float, float, float]],
        min_threshold: float,
    ):
        """Articles below threshold SHALL NOT be selected."""
        selected = select_top_articles(scored_articles, target_count=100, min_threshold=min_threshold)
        
        # Count how many input articles are above threshold
        above_threshold = [item for item in scored_articles if item[1] >= min_threshold]
        
        assert len(selected) == len(above_threshold), (
            f"Expected {len(above_threshold)} articles above threshold, "
            f"got {len(selected)}"
        )

    def test_high_threshold_excludes_all(self):
        """Threshold of 100 should exclude articles with score < 100."""
        article = NormalizedArticle(
            source="Test",
            title="Test Article",
            canonical_url="https://example.com/test",
        )
        scored_articles = [
            (article, 99.9, 100.0, 99.0),
            (article, 50.0, 40.0, 55.0),
        ]
        
        selected = select_top_articles(scored_articles, target_count=10, min_threshold=100.0)
        
        assert len(selected) == 0

    def test_zero_threshold_includes_all(self):
        """Threshold of 0 should include all articles."""
        article = NormalizedArticle(
            source="Test",
            title="Test Article",
            canonical_url="https://example.com/test",
        )
        scored_articles = [
            (article, 0.0, 0.0, 0.0),
            (article, 50.0, 40.0, 55.0),
        ]
        
        selected = select_top_articles(scored_articles, target_count=10, min_threshold=0.0)
        
        assert len(selected) == 2
