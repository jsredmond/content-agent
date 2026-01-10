"""Property-based tests for CSV writer.

Feature: content-agent
Tests Property 21 from the design document.
"""

import csv
import os
import re
import tempfile
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings, strategies as st

from src.engines.article_normalizer import ScoredArticle
from src.engines.csv_writer import (
    CSV_COLUMNS,
    format_scored_article_for_csv,
    write_csv,
)


# Strategies for generating test data
@st.composite
def scored_article_strategy(draw):
    """Generate ScoredArticle instances for testing."""
    source = draw(st.sampled_from(["AWS News Blog", "Microsoft Purview Blog"]))
    title = draw(st.text(min_size=1, max_size=200).filter(lambda x: x.strip()))
    url = draw(st.text(min_size=5, max_size=100).map(lambda s: f"https://example.com/{s.replace(chr(0), '')}"))
    published_date = draw(st.one_of(
        st.none(),
        st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
    ))
    author = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    summary = draw(st.text(min_size=1, max_size=500).filter(lambda x: x.strip()))
    key_topics = draw(st.lists(
        st.text(min_size=1, max_size=30).filter(lambda x: x.strip() and ';' not in x),
        min_size=0,
        max_size=5,
    ))
    why_it_matters = draw(st.text(min_size=1, max_size=200).filter(lambda x: x.strip()))
    suggested_linkedin_angle = draw(st.text(min_size=1, max_size=150).filter(lambda x: x.strip()))
    suggested_hashtags = draw(st.lists(
        st.text(min_size=1, max_size=20).filter(lambda x: x.strip() and ';' not in x).map(lambda x: f"#{x}"),
        min_size=0,
        max_size=5,
    ))
    score_overall = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False))
    score_recency = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False))
    score_relevance = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False))
    collected_at = draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)))
    
    return ScoredArticle(
        source=source,
        title=title,
        url=url,
        published_date=published_date,
        author=author,
        summary=summary,
        key_topics=key_topics,
        why_it_matters=why_it_matters,
        suggested_linkedin_angle=suggested_linkedin_angle,
        suggested_hashtags=suggested_hashtags,
        score_overall=score_overall,
        score_recency=score_recency,
        score_relevance=score_relevance,
        collected_at=collected_at,
    )


@st.composite
def scored_articles_list_strategy(draw, min_size=0, max_size=10):
    """Generate a list of ScoredArticle instances."""
    return draw(st.lists(scored_article_strategy(), min_size=min_size, max_size=max_size))


# Feature: content-agent, Property 21: CSV Output Validation
# Validates: Requirements 7.1, 7.2, 7.3, 7.4
class TestCSVOutputValidation:
    """Property tests for CSV output validation.
    
    For any list of ScoredArticles written to CSV:
    - The filename SHALL match pattern `content_candidates_YYYYMMDD_HHMMSS.csv`
    - The CSV SHALL contain all required columns
    - Multi-value fields (key_topics, suggested_hashtags) SHALL use semicolon delimiters
    - The file SHALL be valid UTF-8
    """

    @given(articles=scored_articles_list_strategy(min_size=0, max_size=10))
    @settings(max_examples=100)
    def test_filename_matches_pattern(self, articles: list[ScoredArticle]):
        """Filename SHALL match pattern content_candidates_YYYYMMDD_HHMMSS.csv."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = write_csv(articles, output_dir=tmpdir)
            filename = os.path.basename(filepath)
            
            # Pattern: content_candidates_YYYYMMDD_HHMMSS.csv
            pattern = r'^content_candidates_\d{8}_\d{6}\.csv$'
            assert re.match(pattern, filename), (
                f"Filename '{filename}' does not match expected pattern "
                f"'content_candidates_YYYYMMDD_HHMMSS.csv'"
            )

    @given(articles=scored_articles_list_strategy(min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_csv_contains_all_required_columns(self, articles: list[ScoredArticle]):
        """CSV SHALL contain all required columns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = write_csv(articles, output_dir=tmpdir)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                
                assert fieldnames is not None, "CSV has no header row"
                
                for column in CSV_COLUMNS:
                    assert column in fieldnames, (
                        f"Required column '{column}' missing from CSV. "
                        f"Found columns: {fieldnames}"
                    )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_multi_value_fields_use_semicolon_delimiter(self, article: ScoredArticle):
        """Multi-value fields SHALL use semicolon delimiters."""
        formatted = format_scored_article_for_csv(article)
        
        # Verify key_topics uses semicolon delimiter
        if len(article.key_topics) > 1:
            assert ';' in formatted['key_topics'], (
                f"key_topics with multiple values should use semicolon delimiter. "
                f"Got: '{formatted['key_topics']}'"
            )
        
        # Verify suggested_hashtags uses semicolon delimiter
        if len(article.suggested_hashtags) > 1:
            assert ';' in formatted['suggested_hashtags'], (
                f"suggested_hashtags with multiple values should use semicolon delimiter. "
                f"Got: '{formatted['suggested_hashtags']}'"
            )
        
        # Verify the values can be split back correctly
        if article.key_topics:
            split_topics = formatted['key_topics'].split(';')
            assert split_topics == article.key_topics, (
                f"key_topics round-trip failed. Expected {article.key_topics}, "
                f"got {split_topics}"
            )
        
        if article.suggested_hashtags:
            split_hashtags = formatted['suggested_hashtags'].split(';')
            assert split_hashtags == article.suggested_hashtags, (
                f"suggested_hashtags round-trip failed. Expected {article.suggested_hashtags}, "
                f"got {split_hashtags}"
            )

    @given(articles=scored_articles_list_strategy(min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_file_is_valid_utf8(self, articles: list[ScoredArticle]):
        """File SHALL be valid UTF-8."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = write_csv(articles, output_dir=tmpdir)
            
            # Read file as bytes and verify UTF-8 decoding works
            with open(filepath, 'rb') as f:
                content = f.read()
            
            try:
                decoded = content.decode('utf-8')
                assert decoded is not None
            except UnicodeDecodeError as e:
                pytest.fail(f"File is not valid UTF-8: {e}")

    @given(articles=scored_articles_list_strategy(min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_csv_row_count_matches_article_count(self, articles: list[ScoredArticle]):
        """CSV SHALL have one row per article plus header."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = write_csv(articles, output_dir=tmpdir)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == len(articles), (
                f"Expected {len(articles)} data rows, got {len(rows)}"
            )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_format_preserves_all_fields(self, article: ScoredArticle):
        """Formatting SHALL preserve all article field values."""
        formatted = format_scored_article_for_csv(article)
        
        # Verify all required columns are present
        for column in CSV_COLUMNS:
            assert column in formatted, f"Missing column: {column}"
        
        # Verify field values are preserved
        assert formatted['source'] == article.source
        assert formatted['title'] == article.title
        assert formatted['url'] == article.url
        assert formatted['summary'] == article.summary
        assert formatted['why_it_matters'] == article.why_it_matters
        assert formatted['suggested_linkedin_angle'] == article.suggested_linkedin_angle
        
        # Verify scores are preserved (as strings)
        assert float(formatted['score_overall']) == article.score_overall
        assert float(formatted['score_recency']) == article.score_recency
        assert float(formatted['score_relevance']) == article.score_relevance

    def test_empty_articles_list_creates_valid_csv(self):
        """Empty article list should create CSV with only header."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = write_csv([], output_dir=tmpdir)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 0
            assert reader.fieldnames == CSV_COLUMNS

    def test_none_published_date_handled(self):
        """None published_date should be formatted as empty string."""
        article = ScoredArticle(
            source="Test",
            title="Test Article",
            url="https://example.com/test",
            published_date=None,
            author="Test Author",
            summary="Test summary.",
            key_topics=["test"],
            why_it_matters="Test matters.",
            suggested_linkedin_angle="Test angle.",
            suggested_hashtags=["#test"],
            score_overall=50.0,
            score_recency=50.0,
            score_relevance=50.0,
            collected_at=datetime(2024, 1, 15, 10, 30),
        )
        
        formatted = format_scored_article_for_csv(article)
        assert formatted['published_date'] == ''

    def test_none_author_handled(self):
        """None author should be formatted as empty string."""
        article = ScoredArticle(
            source="Test",
            title="Test Article",
            url="https://example.com/test",
            published_date=datetime(2024, 1, 15),
            author=None,
            summary="Test summary.",
            key_topics=["test"],
            why_it_matters="Test matters.",
            suggested_linkedin_angle="Test angle.",
            suggested_hashtags=["#test"],
            score_overall=50.0,
            score_recency=50.0,
            score_relevance=50.0,
            collected_at=datetime(2024, 1, 15, 10, 30),
        )
        
        formatted = format_scored_article_for_csv(article)
        assert formatted['author'] == ''
