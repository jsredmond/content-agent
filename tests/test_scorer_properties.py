"""Property-based tests for relevance scoring.

Feature: content-agent
Tests Properties 11, 12, and 13 from the design document.
"""

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings, strategies as st, assume

from src.config.settings import Settings, DEFAULT_KEYWORDS
from src.engines.article_normalizer import NormalizedArticle
from src.engines.relevance_scorer import (
    calculate_recency_score,
    calculate_relevance_score,
    calculate_overall_score,
    score_articles,
)


# Strategies for generating test data
@st.composite
def datetime_strategy(draw):
    """Generate datetime objects within a reasonable range."""
    return draw(st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31),
    ))


@st.composite
def normalized_article_strategy(draw):
    """Generate NormalizedArticle instances for testing."""
    source = draw(st.sampled_from(["AWS News Blog", "Microsoft Purview Blog"]))
    title = draw(st.text(min_size=1, max_size=200))
    url = draw(st.sampled_from([
        "https://aws.amazon.com/blogs/news/article",
        "https://techcommunity.microsoft.com/blog/post",
        "https://example.com/article",
    ]))
    published_date = draw(st.one_of(
        st.none(),
        datetime_strategy(),
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


# Feature: content-agent, Property 11: Score Bounds
# Validates: Requirements 4.1, 4.4
class TestScoreBounds:
    """Property tests for score bounds.
    
    For any article and scoring configuration, recency_score, relevance_score,
    and overall_score SHALL all be in the range [0, 100].
    """

    @given(
        published_date=st.one_of(st.none(), datetime_strategy()),
        window_days=st.integers(min_value=1, max_value=365),
        reference_date=datetime_strategy(),
    )
    @settings(max_examples=100)
    def test_recency_score_bounds(
        self,
        published_date: datetime | None,
        window_days: int,
        reference_date: datetime,
    ):
        """For any article, recency_score SHALL be in the range [0, 100]."""
        score = calculate_recency_score(published_date, window_days, reference_date)
        
        assert 0.0 <= score <= 100.0, (
            f"Recency score {score} is out of bounds [0, 100]"
        )

    @given(
        title=st.text(min_size=0, max_size=200),
        summary=st.one_of(st.none(), st.text(min_size=0, max_size=500)),
    )
    @settings(max_examples=100)
    def test_relevance_score_bounds(self, title: str, summary: str | None):
        """For any article, relevance_score SHALL be in the range [0, 100]."""
        score = calculate_relevance_score(title, summary, DEFAULT_KEYWORDS)
        
        assert 0.0 <= score <= 100.0, (
            f"Relevance score {score} is out of bounds [0, 100]"
        )

    @given(
        recency_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        relevance_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        recency_weight=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_overall_score_bounds(
        self,
        recency_score: float,
        relevance_score: float,
        recency_weight: float,
    ):
        """For any scores and weights, overall_score SHALL be in the range [0, 100]."""
        relevance_weight = 1.0 - recency_weight
        score = calculate_overall_score(
            recency_score, relevance_score, recency_weight, relevance_weight
        )
        
        assert 0.0 <= score <= 100.0, (
            f"Overall score {score} is out of bounds [0, 100]"
        )

    @given(article=normalized_article_strategy())
    @settings(max_examples=100)
    def test_score_articles_all_scores_in_bounds(self, article: NormalizedArticle):
        """For any article scored through score_articles, all scores SHALL be in [0, 100]."""
        settings_obj = Settings()
        reference_date = datetime.now(timezone.utc)
        
        results = score_articles([article], settings_obj, reference_date)
        
        assert len(results) == 1
        _, overall, recency, relevance = results[0]
        
        assert 0.0 <= overall <= 100.0, f"Overall score {overall} out of bounds"
        assert 0.0 <= recency <= 100.0, f"Recency score {recency} out of bounds"
        assert 0.0 <= relevance <= 100.0, f"Relevance score {relevance} out of bounds"


# Feature: content-agent, Property 12: Keyword Matching Contribution
# Validates: Requirements 4.5
class TestKeywordMatchingContribution:
    """Property tests for keyword matching contribution.
    
    For any article containing a configured keyword in its title or summary,
    the relevance_score SHALL be greater than 0.
    """

    @given(
        theme=st.sampled_from(list(DEFAULT_KEYWORDS.keys())),
        keyword_index=st.integers(min_value=0, max_value=5),
        prefix=st.text(min_size=0, max_size=50),
        suffix=st.text(min_size=0, max_size=50),
    )
    @settings(max_examples=100)
    def test_keyword_in_title_gives_positive_score(
        self,
        theme: str,
        keyword_index: int,
        prefix: str,
        suffix: str,
    ):
        """For any article with a keyword in title, relevance_score SHALL be > 0."""
        keywords_list = DEFAULT_KEYWORDS[theme]
        assume(len(keywords_list) > 0)
        
        keyword = keywords_list[keyword_index % len(keywords_list)]
        title = f"{prefix} {keyword} {suffix}"
        
        score = calculate_relevance_score(title, None, DEFAULT_KEYWORDS)
        
        assert score > 0.0, (
            f"Expected positive score for title containing '{keyword}', got {score}"
        )

    @given(
        theme=st.sampled_from(list(DEFAULT_KEYWORDS.keys())),
        keyword_index=st.integers(min_value=0, max_value=5),
        prefix=st.text(min_size=0, max_size=50),
        suffix=st.text(min_size=0, max_size=50),
    )
    @settings(max_examples=100)
    def test_keyword_in_summary_gives_positive_score(
        self,
        theme: str,
        keyword_index: int,
        prefix: str,
        suffix: str,
    ):
        """For any article with a keyword in summary, relevance_score SHALL be > 0."""
        keywords_list = DEFAULT_KEYWORDS[theme]
        assume(len(keywords_list) > 0)
        
        keyword = keywords_list[keyword_index % len(keywords_list)]
        summary = f"{prefix} {keyword} {suffix}"
        
        score = calculate_relevance_score("Generic Title", summary, DEFAULT_KEYWORDS)
        
        assert score > 0.0, (
            f"Expected positive score for summary containing '{keyword}', got {score}"
        )

    def test_no_keywords_gives_zero_score(self):
        """Article with no matching keywords should have relevance_score of 0."""
        title = "Completely unrelated article about cooking recipes"
        summary = "This article discusses various pasta dishes and sauces."
        
        score = calculate_relevance_score(title, summary, DEFAULT_KEYWORDS)
        
        assert score == 0.0, f"Expected 0 score for unrelated content, got {score}"

    def test_empty_keywords_dict_gives_zero_score(self):
        """Empty keywords dictionary should give relevance_score of 0."""
        score = calculate_relevance_score("Any title", "Any summary", {})
        
        assert score == 0.0


# Feature: content-agent, Property 13: Overall Score Calculation
# Validates: Requirements 4.6
class TestOverallScoreCalculation:
    """Property tests for overall score calculation.
    
    For any recency_score R, relevance_score V, and weights (w1, w2) where
    w1 + w2 = 1, the overall_score SHALL equal w1 * R + w2 * V.
    """

    @given(
        recency_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        relevance_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        recency_weight=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_overall_score_equals_weighted_sum(
        self,
        recency_score: float,
        relevance_score: float,
        recency_weight: float,
    ):
        """overall_score SHALL equal w1 * R + w2 * V where w1 + w2 = 1."""
        relevance_weight = 1.0 - recency_weight
        
        actual = calculate_overall_score(
            recency_score, relevance_score, recency_weight, relevance_weight
        )
        expected = recency_weight * recency_score + relevance_weight * relevance_score
        
        # Use approximate equality due to floating point
        assert abs(actual - expected) < 0.001, (
            f"Expected {expected}, got {actual}"
        )

    def test_default_weights(self):
        """Default weights should be 0.4 recency and 0.6 relevance."""
        recency = 100.0
        relevance = 50.0
        
        score = calculate_overall_score(recency, relevance)
        expected = 0.4 * 100.0 + 0.6 * 50.0  # 40 + 30 = 70
        
        assert abs(score - expected) < 0.001, f"Expected {expected}, got {score}"

    def test_all_recency_weight(self):
        """With recency_weight=1.0, overall should equal recency."""
        recency = 75.0
        relevance = 25.0
        
        score = calculate_overall_score(recency, relevance, 1.0, 0.0)
        
        assert abs(score - recency) < 0.001

    def test_all_relevance_weight(self):
        """With relevance_weight=1.0, overall should equal relevance."""
        recency = 75.0
        relevance = 25.0
        
        score = calculate_overall_score(recency, relevance, 0.0, 1.0)
        
        assert abs(score - relevance) < 0.001

    def test_equal_weights(self):
        """With equal weights, overall should be average of scores."""
        recency = 80.0
        relevance = 40.0
        
        score = calculate_overall_score(recency, relevance, 0.5, 0.5)
        expected = (80.0 + 40.0) / 2  # 60
        
        assert abs(score - expected) < 0.001


# Additional unit tests for edge cases
class TestRecencyScoreEdgeCases:
    """Unit tests for recency score edge cases."""

    def test_none_date_returns_zero(self):
        """None published_date should return 0."""
        score = calculate_recency_score(None, 30)
        assert score == 0.0

    def test_today_returns_100(self):
        """Article published today should score 100."""
        now = datetime.now(timezone.utc)
        score = calculate_recency_score(now, 30, now)
        assert score == 100.0

    def test_at_window_edge_returns_zero(self):
        """Article at window edge should score approximately 0."""
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=30)
        score = calculate_recency_score(old_date, 30, now)
        assert score == 0.0

    def test_outside_window_returns_zero(self):
        """Article outside window should score 0."""
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=60)
        score = calculate_recency_score(old_date, 30, now)
        assert score == 0.0

    def test_half_window_returns_50(self):
        """Article at half the window should score approximately 50."""
        now = datetime.now(timezone.utc)
        half_old = now - timedelta(days=15)
        score = calculate_recency_score(half_old, 30, now)
        assert abs(score - 50.0) < 1.0  # Allow small tolerance

    def test_future_date_returns_100(self):
        """Future publication date should score 100."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=5)
        score = calculate_recency_score(future, 30, now)
        assert score == 100.0

    def test_zero_window_returns_zero(self):
        """Zero window days should return 0."""
        now = datetime.now(timezone.utc)
        score = calculate_recency_score(now, 0, now)
        assert score == 0.0


class TestScoreArticlesIntegration:
    """Integration tests for score_articles function."""

    def test_empty_list_returns_empty(self):
        """Empty article list should return empty results."""
        settings_obj = Settings()
        results = score_articles([], settings_obj)
        assert results == []

    def test_returns_correct_tuple_structure(self):
        """Results should be tuples of (article, overall, recency, relevance)."""
        article = NormalizedArticle(
            source="Test",
            title="Cloud Security Best Practices",
            canonical_url="https://example.com/article",
            published_date=datetime.now(timezone.utc),
            author="Test Author",
            summary_text="Learn about cloud security.",
        )
        settings_obj = Settings()
        
        results = score_articles([article], settings_obj)
        
        assert len(results) == 1
        result = results[0]
        assert len(result) == 4
        assert result[0] is article
        assert isinstance(result[1], float)  # overall
        assert isinstance(result[2], float)  # recency
        assert isinstance(result[3], float)  # relevance

    def test_multiple_articles_scored(self):
        """Multiple articles should all be scored."""
        articles = [
            NormalizedArticle(
                source="Test",
                title=f"Article {i}",
                canonical_url=f"https://example.com/{i}",
            )
            for i in range(5)
        ]
        settings_obj = Settings()
        
        results = score_articles(articles, settings_obj)
        
        assert len(results) == 5
