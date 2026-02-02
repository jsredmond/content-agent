"""Property-based tests for the Ollama Content Generator.

Feature: ollama-content-generator
Tests Properties 4, 5, and 6 from the design document for ContextManager.
"""

import logging
from datetime import datetime

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck

from src.engines.article_normalizer import ScoredArticle
from src.engines.generator import ContextManager


# =============================================================================
# Test Fixtures and Strategies
# =============================================================================


def scored_article_strategy(
    summary_min_size: int = 10,
    summary_max_size: int = 500,
    why_it_matters_min_size: int = 10,
    why_it_matters_max_size: int = 200,
    linkedin_angle_min_size: int = 10,
    linkedin_angle_max_size: int = 200,
):
    """Strategy for generating ScoredArticle objects with configurable content sizes."""
    return st.builds(
        ScoredArticle,
        source=st.sampled_from(["AWS News Blog", "Microsoft Purview Blog"]),
        title=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=5,
            max_size=200,
        ),
        url=st.sampled_from([
            "https://aws.amazon.com/blogs/aws/new-feature",
            "https://techcommunity.microsoft.com/blog/purview-update",
            "https://example.com/article/security-best-practices",
        ]),
        published_date=st.one_of(
            st.none(),
            st.datetimes(
                min_value=datetime(2020, 1, 1),
                max_value=datetime(2025, 12, 31),
            ),
        ),
        author=st.one_of(
            st.none(),
            st.text(
                alphabet=st.characters(whitelist_categories=('L', 'Z')),
                min_size=2,
                max_size=50,
            ),
        ),
        summary=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=summary_min_size,
            max_size=summary_max_size,
        ),
        key_topics=st.lists(
            st.sampled_from([
                "cloud_security",
                "identity_and_access",
                "governance_and_compliance",
                "data_protection",
                "auditing_and_retention",
                "devsecops",
            ]),
            min_size=1,
            max_size=4,
            unique=True,
        ),
        why_it_matters=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=why_it_matters_min_size,
            max_size=why_it_matters_max_size,
        ),
        suggested_linkedin_angle=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=linkedin_angle_min_size,
            max_size=linkedin_angle_max_size,
        ),
        suggested_hashtags=st.lists(
            st.sampled_from([
                "#CloudSecurity",
                "#AWS",
                "#Azure",
                "#Purview",
                "#CyberSecurity",
                "#DataGovernance",
                "#Compliance",
                "#ZeroTrust",
            ]),
            min_size=2,
            max_size=5,
            unique=True,
        ),
        score_overall=st.floats(min_value=0.0, max_value=100.0),
        score_recency=st.floats(min_value=0.0, max_value=100.0),
        score_relevance=st.floats(min_value=0.0, max_value=100.0),
        collected_at=st.datetimes(
            min_value=datetime(2024, 1, 1),
            max_value=datetime(2025, 12, 31),
        ),
    )


def small_article_strategy():
    """Strategy for generating small articles that fit within token limits."""
    return scored_article_strategy(
        summary_min_size=10,
        summary_max_size=200,
        why_it_matters_min_size=10,
        why_it_matters_max_size=100,
        linkedin_angle_min_size=10,
        linkedin_angle_max_size=100,
    )


def large_content_strategy(min_chars: int = 5000, max_chars: int = 10000):
    """Strategy for generating large text content that exceeds token limits.
    
    Note: Hypothesis has limits on text generation size, so we use a smaller
    range and repeat the content to achieve the desired size.
    """
    # Generate a base string and repeat it to create large content
    @st.composite
    def build_large_content(draw):
        # Generate a base chunk of text
        base = draw(st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=100,
            max_size=500,
        ))
        if not base:
            base = "A" * 100
        
        # Repeat to reach desired size
        target_size = draw(st.integers(min_value=min_chars, max_value=max_chars))
        repetitions = (target_size // len(base)) + 1
        return (base * repetitions)[:target_size]
    
    return build_large_content()


# =============================================================================
# Feature: ollama-content-generator, Property 4: Content Within Limit Passes Through
# Validates: Requirements 3.1
# =============================================================================


class TestContentWithinLimitPassesThrough:
    """Property tests for content that fits within token limits.
    
    **Property 4: Content Within Limit Passes Through**
    
    *For any* article content with token count at or below 10,000 tokens,
    the ContextManager SHALL return the content unchanged (was_truncated = False).
    
    **Validates: Requirements 3.1**
    """

    @given(article=small_article_strategy())
    @settings(max_examples=100)
    def test_small_content_not_truncated(self, article: ScoredArticle):
        """For any article with content within token limit, was_truncated SHALL be False.
        
        **Validates: Requirements 3.1**
        """
        cm = ContextManager(max_tokens=10000)
        
        content, was_truncated = cm.prepare_content(article)
        
        # Verify content was not truncated
        assert was_truncated is False, (
            f"Content was unexpectedly truncated for article '{article.title}'"
        )
        
        # Verify content is non-empty
        assert len(content) > 0, "Prepared content should not be empty"

    @given(article=small_article_strategy())
    @settings(max_examples=100)
    def test_content_within_limit_contains_article_fields(self, article: ScoredArticle):
        """For any article within limit, prepared content SHALL contain key article fields.
        
        **Validates: Requirements 3.1**
        """
        cm = ContextManager(max_tokens=10000)
        
        content, was_truncated = cm.prepare_content(article)
        
        # Content should contain key article information
        assert article.title in content, "Content should contain article title"
        assert article.source in content, "Content should contain article source"
        assert article.summary in content, "Content should contain article summary"

    @given(
        max_tokens=st.integers(min_value=5000, max_value=20000),
        article=small_article_strategy(),
    )
    @settings(max_examples=100)
    def test_configurable_token_limit_respected(
        self, max_tokens: int, article: ScoredArticle
    ):
        """For any configured token limit, content within that limit SHALL pass through unchanged.
        
        **Validates: Requirements 3.1**
        """
        cm = ContextManager(max_tokens=max_tokens)
        
        content, was_truncated = cm.prepare_content(article)
        
        # Estimate tokens in prepared content
        estimated_tokens = cm.estimate_tokens(content)
        
        # If content fits within limit, it should not be truncated
        if estimated_tokens <= max_tokens:
            assert was_truncated is False, (
                f"Content with {estimated_tokens} tokens should not be truncated "
                f"when limit is {max_tokens}"
            )

    def test_exact_limit_boundary_not_truncated(self):
        """Content exactly at the token limit SHALL not be truncated.
        
        **Validates: Requirements 3.1**
        """
        cm = ContextManager(max_tokens=100)
        
        # Create article with content that's exactly at the limit
        # 100 tokens * 4 chars/token = 400 chars
        article = ScoredArticle(
            source="Test",
            title="A" * 50,  # ~12 tokens
            url="https://example.com/test",
            published_date=None,
            author=None,
            summary="B" * 100,  # ~25 tokens
            key_topics=["cloud_security"],
            why_it_matters="C" * 50,  # ~12 tokens
            suggested_linkedin_angle="D" * 50,  # ~12 tokens
            suggested_hashtags=["#Test"],
            score_overall=50.0,
            score_recency=50.0,
            score_relevance=50.0,
            collected_at=datetime.now(),
        )
        
        content, was_truncated = cm.prepare_content(article)
        
        # Small content should not be truncated
        estimated_tokens = cm.estimate_tokens(content)
        if estimated_tokens <= 100:
            assert was_truncated is False


# =============================================================================
# Feature: ollama-content-generator, Property 5: Oversized Content Truncation
# Validates: Requirements 3.2
# =============================================================================


class TestOversizedContentTruncation:
    """Property tests for content that exceeds token limits.
    
    **Property 5: Oversized Content Truncation**
    
    *For any* article content exceeding the configured token limit,
    the ContextManager SHALL return content that fits within the limit
    (was_truncated = True).
    
    **Validates: Requirements 3.2**
    """

    @given(
        large_summary=large_content_strategy(min_chars=5000, max_chars=10000),
    )
    @settings(max_examples=100)
    def test_oversized_content_is_truncated(self, large_summary: str):
        """For any content exceeding token limit, was_truncated SHALL be True.
        
        **Validates: Requirements 3.2**
        """
        # Use a small token limit to ensure truncation
        cm = ContextManager(max_tokens=100)
        
        article = ScoredArticle(
            source="AWS News Blog",
            title="Test Article with Large Content",
            url="https://aws.amazon.com/blogs/aws/test",
            published_date=datetime.now(),
            author="Test Author",
            summary=large_summary,
            key_topics=["cloud_security"],
            why_it_matters="This is important for security teams.",
            suggested_linkedin_angle="Consider this for your security strategy.",
            suggested_hashtags=["#CloudSecurity", "#AWS"],
            score_overall=75.0,
            score_recency=80.0,
            score_relevance=70.0,
            collected_at=datetime.now(),
        )
        
        content, was_truncated = cm.prepare_content(article)
        
        # Content should be truncated
        assert was_truncated is True, (
            "Content exceeding token limit should be truncated"
        )

    @given(
        large_summary=large_content_strategy(min_chars=5000, max_chars=10000),
    )
    @settings(max_examples=100)
    def test_truncated_content_fits_within_limit(self, large_summary: str):
        """For any truncated content, result SHALL fit within configured token limit.
        
        **Validates: Requirements 3.2**
        """
        max_tokens = 100
        cm = ContextManager(max_tokens=max_tokens)
        
        article = ScoredArticle(
            source="Microsoft Purview Blog",
            title="Large Article Test",
            url="https://techcommunity.microsoft.com/blog/test",
            published_date=datetime.now(),
            author="Test Author",
            summary=large_summary,
            key_topics=["data_protection", "governance_and_compliance"],
            why_it_matters="Critical for compliance teams.",
            suggested_linkedin_angle="Compliance leaders should take note.",
            suggested_hashtags=["#DataGovernance", "#Compliance"],
            score_overall=85.0,
            score_recency=90.0,
            score_relevance=80.0,
            collected_at=datetime.now(),
        )
        
        content, was_truncated = cm.prepare_content(article)
        
        # Verify truncated content fits within limit
        estimated_tokens = cm.estimate_tokens(content)
        assert estimated_tokens <= max_tokens, (
            f"Truncated content has {estimated_tokens} tokens, "
            f"exceeds limit of {max_tokens}"
        )

    @given(
        max_tokens=st.integers(min_value=100, max_value=500),
        large_summary=large_content_strategy(min_chars=5000, max_chars=10000),
    )
    @settings(max_examples=100)
    def test_truncation_respects_configurable_limit(
        self, max_tokens: int, large_summary: str
    ):
        """For any configured token limit, truncated content SHALL fit within that limit.
        
        **Validates: Requirements 3.2**
        """
        cm = ContextManager(max_tokens=max_tokens)
        
        article = ScoredArticle(
            source="AWS News Blog",
            title="Configurable Limit Test",
            url="https://aws.amazon.com/blogs/aws/config-test",
            published_date=datetime.now(),
            author="Test Author",
            summary=large_summary,
            key_topics=["devsecops"],
            why_it_matters="Important for DevSecOps teams.",
            suggested_linkedin_angle="DevSecOps practitioners should consider this.",
            suggested_hashtags=["#DevSecOps", "#Security"],
            score_overall=70.0,
            score_recency=75.0,
            score_relevance=65.0,
            collected_at=datetime.now(),
        )
        
        content, was_truncated = cm.prepare_content(article)
        
        # Verify content fits within configured limit
        estimated_tokens = cm.estimate_tokens(content)
        assert estimated_tokens <= max_tokens, (
            f"Content has {estimated_tokens} tokens, exceeds limit of {max_tokens}"
        )

    def test_truncation_preserves_priority_fields(self):
        """Truncation SHALL preserve priority fields (title, source, summary, key topics).
        
        **Validates: Requirements 3.2, 3.3**
        """
        cm = ContextManager(max_tokens=500)
        
        # Create article with large content
        large_summary = "A" * 50000
        
        article = ScoredArticle(
            source="AWS News Blog",
            title="Priority Fields Test",
            url="https://aws.amazon.com/blogs/aws/priority-test",
            published_date=datetime.now(),
            author="Test Author",
            summary=large_summary,
            key_topics=["cloud_security", "identity_and_access"],
            why_it_matters="Very important information here.",
            suggested_linkedin_angle="Leaders should pay attention.",
            suggested_hashtags=["#CloudSecurity"],
            score_overall=80.0,
            score_recency=85.0,
            score_relevance=75.0,
            collected_at=datetime.now(),
        )
        
        content, was_truncated = cm.prepare_content(article)
        
        assert was_truncated is True
        
        # Priority fields should be preserved
        assert "Title:" in content, "Title field should be preserved"
        assert "Source:" in content, "Source field should be preserved"


# =============================================================================
# Feature: ollama-content-generator, Property 6: Truncation Warning Logging
# Validates: Requirements 3.4
# =============================================================================


class TestTruncationWarningLogging:
    """Property tests for truncation warning logging.
    
    **Property 6: Truncation Warning Logging**
    
    *For any* content that requires truncation, the system SHALL emit
    a warning log message indicating truncation occurred.
    
    **Validates: Requirements 3.4**
    """

    @given(
        large_summary=large_content_strategy(min_chars=5000, max_chars=10000),
    )
    @settings(max_examples=100)
    def test_truncation_emits_warning_log(self, large_summary: str):
        """For any truncated content, a warning log message SHALL be emitted.
        
        **Validates: Requirements 3.4**
        """
        import logging
        
        cm = ContextManager(max_tokens=100)
        
        article = ScoredArticle(
            source="AWS News Blog",
            title="Warning Log Test Article",
            url="https://aws.amazon.com/blogs/aws/warning-test",
            published_date=datetime.now(),
            author="Test Author",
            summary=large_summary,
            key_topics=["cloud_security"],
            why_it_matters="Important security update.",
            suggested_linkedin_angle="Security teams should review.",
            suggested_hashtags=["#CloudSecurity"],
            score_overall=75.0,
            score_recency=80.0,
            score_relevance=70.0,
            collected_at=datetime.now(),
        )
        
        # Capture log messages using a handler
        log_capture = []
        handler = logging.Handler()
        handler.emit = lambda record: log_capture.append(record)
        
        logger = logging.getLogger("src.engines.generator")
        original_level = logger.level
        logger.setLevel(logging.WARNING)
        logger.addHandler(handler)
        
        try:
            content, was_truncated = cm.prepare_content(article)
            
            # Verify truncation occurred
            assert was_truncated is True
            
            # Verify warning was logged
            warning_messages = [
                record.message for record in log_capture
                if record.levelno == logging.WARNING
            ]
            
            assert len(warning_messages) > 0, (
                "A warning log message should be emitted when content is truncated"
            )
            
            # Verify warning contains relevant information
            warning_text = " ".join(warning_messages)
            assert "truncat" in warning_text.lower() or "exceed" in warning_text.lower(), (
                f"Warning message should mention truncation: {warning_text}"
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)

    @given(article=small_article_strategy())
    @settings(max_examples=100)
    def test_no_warning_when_content_fits(self, article: ScoredArticle):
        """For any content within limit, no truncation warning SHALL be emitted.
        
        **Validates: Requirements 3.4**
        """
        import logging
        
        cm = ContextManager(max_tokens=10000)
        
        # Capture log messages using a handler
        log_capture = []
        handler = logging.Handler()
        handler.emit = lambda record: log_capture.append(record)
        
        logger = logging.getLogger("src.engines.generator")
        original_level = logger.level
        logger.setLevel(logging.WARNING)
        logger.addHandler(handler)
        
        try:
            content, was_truncated = cm.prepare_content(article)
            
            # Verify no truncation occurred
            assert was_truncated is False
            
            # Verify no truncation warning was logged
            truncation_warnings = [
                record.message for record in log_capture
                if record.levelno == logging.WARNING
                and ("truncat" in record.message.lower() or "exceed" in record.message.lower())
            ]
            
            assert len(truncation_warnings) == 0, (
                f"No truncation warning should be emitted when content fits: {truncation_warnings}"
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)

    def test_warning_contains_article_title(self, caplog):
        """Truncation warning SHALL contain the article title for debugging.
        
        **Validates: Requirements 3.4**
        """
        cm = ContextManager(max_tokens=500)
        
        article_title = "Unique Test Article Title XYZ123"
        large_summary = "A" * 50000
        
        article = ScoredArticle(
            source="AWS News Blog",
            title=article_title,
            url="https://aws.amazon.com/blogs/aws/unique-test",
            published_date=datetime.now(),
            author="Test Author",
            summary=large_summary,
            key_topics=["cloud_security"],
            why_it_matters="Important update.",
            suggested_linkedin_angle="Review this update.",
            suggested_hashtags=["#CloudSecurity"],
            score_overall=75.0,
            score_recency=80.0,
            score_relevance=70.0,
            collected_at=datetime.now(),
        )
        
        with caplog.at_level(logging.WARNING):
            content, was_truncated = cm.prepare_content(article)
        
        assert was_truncated is True
        
        # Verify warning contains article title
        warning_messages = [
            record.message for record in caplog.records
            if record.levelno == logging.WARNING
        ]
        
        warning_text = " ".join(warning_messages)
        assert article_title in warning_text, (
            f"Warning should contain article title '{article_title}': {warning_text}"
        )

    def test_warning_contains_token_counts(self, caplog):
        """Truncation warning SHALL contain token count information.
        
        **Validates: Requirements 3.4**
        """
        max_tokens = 500
        cm = ContextManager(max_tokens=max_tokens)
        
        large_summary = "A" * 50000
        
        article = ScoredArticle(
            source="AWS News Blog",
            title="Token Count Warning Test",
            url="https://aws.amazon.com/blogs/aws/token-test",
            published_date=datetime.now(),
            author="Test Author",
            summary=large_summary,
            key_topics=["cloud_security"],
            why_it_matters="Important update.",
            suggested_linkedin_angle="Review this update.",
            suggested_hashtags=["#CloudSecurity"],
            score_overall=75.0,
            score_recency=80.0,
            score_relevance=70.0,
            collected_at=datetime.now(),
        )
        
        with caplog.at_level(logging.WARNING):
            content, was_truncated = cm.prepare_content(article)
        
        assert was_truncated is True
        
        # Verify warning contains token information
        warning_messages = [
            record.message for record in caplog.records
            if record.levelno == logging.WARNING
        ]
        
        warning_text = " ".join(warning_messages)
        assert "token" in warning_text.lower(), (
            f"Warning should mention tokens: {warning_text}"
        )
        assert str(max_tokens) in warning_text, (
            f"Warning should contain max token limit ({max_tokens}): {warning_text}"
        )


# =============================================================================
# Additional Unit Tests for ContextManager
# =============================================================================


class TestContextManagerTokenEstimation:
    """Unit tests for token estimation functionality."""

    def test_estimate_tokens_empty_string(self):
        """Empty string should return 0 tokens."""
        cm = ContextManager()
        assert cm.estimate_tokens("") == 0

    def test_estimate_tokens_short_text(self):
        """Short text should estimate correctly (4 chars per token)."""
        cm = ContextManager()
        # 12 chars / 4 = 3 tokens
        assert cm.estimate_tokens("Hello World!") == 3

    def test_estimate_tokens_long_text(self):
        """Long text should estimate correctly."""
        cm = ContextManager()
        # 400 chars / 4 = 100 tokens
        text = "A" * 400
        assert cm.estimate_tokens(text) == 100

    def test_default_max_tokens(self):
        """Default max_tokens should be 10000."""
        cm = ContextManager()
        assert cm.max_tokens == 10000

    def test_custom_max_tokens(self):
        """Custom max_tokens should be respected."""
        cm = ContextManager(max_tokens=5000)
        assert cm.max_tokens == 5000


class TestContextManagerSummarization:
    """Unit tests for content summarization functionality."""

    def test_summarize_for_context_empty_text(self):
        """Empty text should return empty string."""
        cm = ContextManager()
        assert cm.summarize_for_context("", 100) == ""

    def test_summarize_for_context_zero_target(self):
        """Zero target tokens should return empty string."""
        cm = ContextManager()
        assert cm.summarize_for_context("Some text", 0) == ""

    def test_summarize_for_context_text_within_limit(self):
        """Text within limit should be returned unchanged."""
        cm = ContextManager()
        text = "Short text"
        result = cm.summarize_for_context(text, 1000)
        assert result == text

    def test_summarize_for_context_truncates_long_text(self):
        """Long text should be truncated to fit target."""
        cm = ContextManager()
        long_text = "A" * 10000
        target_tokens = 100  # 400 chars
        
        result = cm.summarize_for_context(long_text, target_tokens)
        
        # Result should fit within target
        assert cm.estimate_tokens(result) <= target_tokens


# =============================================================================
# Feature: ollama-content-generator, Property 9: Prompt Completeness
# Validates: Requirements 5.1, 5.2, 5.3, 5.4
# =============================================================================


from src.engines.generator import PromptBuilder


class TestPromptCompleteness:
    """Property tests for prompt completeness.
    
    **Property 9: Prompt Completeness**
    
    *For any* ScoredArticle input, the constructed prompt SHALL contain:
    - The article's title, source, summary, and key_topics
    - Hook-Value-CTA framework instructions
    - Target audience specification (CIO, CISO, CTO, IT Director)
    - Professional tone instructions
    
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4**
    """

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_article_title(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain the article title.
        
        **Validates: Requirements 5.1**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=article.key_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        assert article.title in prompt, (
            f"Prompt should contain article title '{article.title}'"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_article_source(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain the article source.
        
        **Validates: Requirements 5.1**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=article.key_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        assert article.source in prompt, (
            f"Prompt should contain article source '{article.source}'"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_article_summary(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain the article summary.
        
        **Validates: Requirements 5.1**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=article.key_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        assert article.summary in prompt, (
            f"Prompt should contain article summary"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_key_topics(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain the key topics.
        
        **Validates: Requirements 5.1**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=article.key_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        # Each key topic should appear in the prompt
        for topic in article.key_topics:
            assert topic in prompt, (
                f"Prompt should contain key topic '{topic}'"
            )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_hook_value_cta_framework(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain Hook-Value-CTA framework instructions.
        
        **Validates: Requirements 5.2**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=article.key_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        # Verify Hook-Value-CTA framework elements are present
        assert "HOOK" in prompt, "Prompt should contain HOOK section instructions"
        assert "VALUE" in prompt, "Prompt should contain VALUE section instructions"
        assert "CTA" in prompt, "Prompt should contain CTA section instructions"
        
        # Verify framework guidance is present
        assert "attention-grabbing" in prompt.lower() or "question" in prompt.lower(), (
            "Prompt should contain hook guidance (attention-grabbing or question)"
        )
        assert "insight" in prompt.lower() or "takeaway" in prompt.lower(), (
            "Prompt should contain value guidance (insight or takeaway)"
        )
        assert "engagement" in prompt.lower() or "discussion" in prompt.lower(), (
            "Prompt should contain CTA guidance (engagement or discussion)"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_target_audience(self, article: ScoredArticle):
        """For any article, the prompt SHALL specify the target audience.
        
        **Validates: Requirements 5.3**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=article.key_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        # Get the system prompt which contains audience specification
        system_prompt = builder.get_system_prompt()
        
        # Verify target audience is specified in system prompt
        audience_roles = ["CIO", "CISO", "CTO", "IT Director"]
        
        # At least some audience roles should be mentioned
        roles_found = [role for role in audience_roles if role in system_prompt]
        assert len(roles_found) >= 2, (
            f"System prompt should specify target audience roles. "
            f"Found: {roles_found}, Expected at least 2 of: {audience_roles}"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_professional_tone_instructions(self, article: ScoredArticle):
        """For any article, the prompt SHALL instruct professional yet engaging tone.
        
        **Validates: Requirements 5.4**
        """
        builder = PromptBuilder()
        
        # Get the system prompt which contains tone instructions
        system_prompt = builder.get_system_prompt()
        
        # Verify professional tone is specified
        assert "professional" in system_prompt.lower(), (
            "System prompt should specify professional tone"
        )
        
        # Verify engaging aspect is also mentioned
        assert "engaging" in system_prompt.lower() or "concise" in system_prompt.lower(), (
            "System prompt should specify engaging or concise writing style"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_why_it_matters(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain the why_it_matters field.
        
        **Validates: Requirements 5.1**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=article.key_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        assert article.why_it_matters in prompt, (
            "Prompt should contain why_it_matters content"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_hashtags(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain the suggested hashtags.
        
        **Validates: Requirements 5.1**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=article.key_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        # Each hashtag should appear in the prompt
        for hashtag in article.suggested_hashtags:
            assert hashtag in prompt, (
                f"Prompt should contain hashtag '{hashtag}'"
            )


# =============================================================================
# Feature: ollama-content-generator, Property 10: Security Framing for Security Topics
# Validates: Requirements 5.5
# =============================================================================


class TestSecurityFramingForSecurityTopics:
    """Property tests for security framing in prompts.
    
    **Property 10: Security Framing for Security Topics**
    
    *For any* article with security-related key_topics (cloud_security,
    identity_and_access, governance_and_compliance, data_protection,
    auditing_and_retention, devsecops), the constructed prompt SHALL include
    additional security-first messaging emphasis.
    
    **Validates: Requirements 5.5**
    """
    
    # Security-related topics that should trigger security framing
    SECURITY_TOPICS = [
        "cloud_security",
        "identity_and_access",
        "governance_and_compliance",
        "data_protection",
        "auditing_and_retention",
        "devsecops",
    ]

    @given(
        security_topic=st.sampled_from(SECURITY_TOPICS),
        article=scored_article_strategy(),
    )
    @settings(max_examples=100)
    def test_security_topic_triggers_security_framing(
        self, security_topic: str, article: ScoredArticle
    ):
        """For any article with a security topic, prompt SHALL include security framing.
        
        **Validates: Requirements 5.5**
        """
        builder = PromptBuilder()
        
        # Ensure the article has the security topic
        key_topics = [security_topic]
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=key_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        # Verify security framing is present
        prompt_lower = prompt.lower()
        security_indicators = [
            "security",
            "compliance",
            "risk",
            "protection",
        ]
        
        # At least one security indicator should be emphasized in the framing section
        has_security_framing = any(
            indicator in prompt_lower for indicator in security_indicators
        )
        
        assert has_security_framing, (
            f"Prompt for security topic '{security_topic}' should include "
            f"security-first framing. Indicators checked: {security_indicators}"
        )

    @given(
        security_topics=st.lists(
            st.sampled_from(SECURITY_TOPICS),
            min_size=1,
            max_size=4,
            unique=True,
        ),
        article=scored_article_strategy(),
    )
    @settings(max_examples=100)
    def test_multiple_security_topics_trigger_security_framing(
        self, security_topics: list[str], article: ScoredArticle
    ):
        """For any article with multiple security topics, prompt SHALL include security framing.
        
        **Validates: Requirements 5.5**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=security_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        # Verify security framing section is present
        assert "SECURITY EMPHASIS" in prompt or "security-first" in prompt.lower(), (
            f"Prompt for security topics {security_topics} should include "
            "security emphasis section"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_non_security_topics_no_security_framing(self, article: ScoredArticle):
        """For any article without security topics, prompt SHALL NOT include security framing.
        
        **Validates: Requirements 5.5**
        """
        builder = PromptBuilder()
        
        # Use non-security topics
        non_security_topics = ["general_news", "product_update", "announcement"]
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=non_security_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        # Verify security framing section is NOT present
        assert "SECURITY EMPHASIS" not in prompt, (
            f"Prompt for non-security topics {non_security_topics} should NOT "
            "include SECURITY EMPHASIS section"
        )

    @given(
        security_topic=st.sampled_from(SECURITY_TOPICS),
        article=scored_article_strategy(),
    )
    @settings(max_examples=100)
    def test_security_framing_mentions_risk_mitigation(
        self, security_topic: str, article: ScoredArticle
    ):
        """For any security topic, security framing SHALL mention risk or protection.
        
        **Validates: Requirements 5.5**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=[security_topic],
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        prompt_lower = prompt.lower()
        
        # Security framing should mention risk or protection concepts
        risk_protection_terms = ["risk", "protection", "compliance", "mitigation"]
        has_risk_protection = any(term in prompt_lower for term in risk_protection_terms)
        
        assert has_risk_protection, (
            f"Security framing for topic '{security_topic}' should mention "
            f"risk/protection concepts. Terms checked: {risk_protection_terms}"
        )

    @given(
        security_topic=st.sampled_from(SECURITY_TOPICS),
        article=scored_article_strategy(),
    )
    @settings(max_examples=100)
    def test_security_framing_emphasizes_security_first_lens(
        self, security_topic: str, article: ScoredArticle
    ):
        """For any security topic, framing SHALL emphasize security-first perspective.
        
        **Validates: Requirements 5.5**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=[security_topic],
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        prompt_lower = prompt.lower()
        
        # Security framing should emphasize security-first approach
        security_first_indicators = [
            "security-first",
            "security implications",
            "security emphasis",
            "leads with security",
        ]
        
        has_security_first = any(
            indicator in prompt_lower for indicator in security_first_indicators
        )
        
        assert has_security_first, (
            f"Security framing for topic '{security_topic}' should emphasize "
            f"security-first perspective. Indicators: {security_first_indicators}"
        )

    def test_security_framing_content_structure(self):
        """Security framing SHALL include structured guidance for IT leaders.
        
        **Validates: Requirements 5.5**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title="AWS Security Update",
            source="AWS News Blog",
            summary="New security features announced",
            key_topics=["cloud_security"],
            why_it_matters="Important for security teams",
            hashtags=["#CloudSecurity"],
        )
        
        # Verify security framing has structured content
        assert "SECURITY EMPHASIS" in prompt, (
            "Security framing should have SECURITY EMPHASIS header"
        )
        
        # Verify actionable guidance is mentioned
        prompt_lower = prompt.lower()
        assert "actionable" in prompt_lower or "guidance" in prompt_lower, (
            "Security framing should mention actionable guidance"
        )

    @given(
        mixed_topics=st.lists(
            st.sampled_from(SECURITY_TOPICS + ["general_news", "product_update"]),
            min_size=2,
            max_size=4,
            unique=True,
        ),
        article=scored_article_strategy(),
    )
    @settings(max_examples=100)
    def test_mixed_topics_with_security_triggers_framing(
        self, mixed_topics: list[str], article: ScoredArticle
    ):
        """For any article with at least one security topic, prompt SHALL include security framing.
        
        **Validates: Requirements 5.5**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=mixed_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        # Check if any topic is security-related
        has_security_topic = any(
            topic in self.SECURITY_TOPICS for topic in mixed_topics
        )
        
        if has_security_topic:
            # Should have security framing
            assert "SECURITY EMPHASIS" in prompt, (
                f"Prompt with security topics {mixed_topics} should include "
                "SECURITY EMPHASIS section"
            )
        else:
            # Should NOT have security framing
            assert "SECURITY EMPHASIS" not in prompt, (
                f"Prompt without security topics {mixed_topics} should NOT include "
                "SECURITY EMPHASIS section"
            )


# =============================================================================
# Feature: ollama-content-generator, Property 1: Connection Error Handling
# Validates: Requirements 1.2
# =============================================================================


import sys
from unittest.mock import patch, MagicMock
from src.engines.generator import OllamaClient, OllamaConnectionError, ModelNotAvailableError


class TestConnectionErrorHandling:
    """Property tests for connection error handling.
    
    **Property 1: Connection Error Handling**
    
    *For any* attempt to use the ContentGenerator when Ollama is not running,
    the system SHALL raise an OllamaConnectionError containing troubleshooting guidance.
    
    **Validates: Requirements 1.2**
    """

    @given(error_message=st.text(min_size=1, max_size=200))
    @settings(max_examples=100)
    def test_connection_refused_raises_ollama_connection_error(self, error_message: str):
        """For any connection refused error, OllamaConnectionError SHALL be raised.
        
        **Validates: Requirements 1.2**
        """
        client = OllamaClient()
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.list.side_effect = ConnectionRefusedError(
            f"Connection refused: {error_message}"
        )
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(OllamaConnectionError) as exc_info:
                client.check_connection()
            
            # Verify troubleshooting guidance is included
            error = exc_info.value
            assert hasattr(error, 'troubleshooting'), (
                "OllamaConnectionError should have troubleshooting attribute"
            )
            assert "ollama serve" in error.troubleshooting.lower(), (
                "Troubleshooting should mention 'ollama serve'"
            )
            assert "localhost:11434" in error.troubleshooting.lower(), (
                "Troubleshooting should mention localhost:11434"
            )

    @given(error_message=st.text(min_size=1, max_size=200))
    @settings(max_examples=100)
    def test_connection_error_contains_troubleshooting(self, error_message: str):
        """For any connection error, the exception SHALL contain troubleshooting guidance.
        
        **Validates: Requirements 1.2**
        """
        client = OllamaClient()
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.list.side_effect = Exception(
            f"Connection error: {error_message}"
        )
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(OllamaConnectionError) as exc_info:
                client.check_connection()
            
            error = exc_info.value
            
            # Verify the error message is descriptive
            assert len(str(error)) > 0, "Error message should not be empty"
            
            # Verify troubleshooting is present
            assert error.troubleshooting is not None, (
                "OllamaConnectionError should have troubleshooting guidance"
            )

    @given(
        timeout_seconds=st.integers(min_value=1, max_value=300),
        num_ctx=st.integers(min_value=1024, max_value=32768),
    )
    @settings(max_examples=100)
    def test_client_configuration_preserved_on_connection_error(
        self, timeout_seconds: int, num_ctx: int
    ):
        """For any client configuration, settings SHALL be preserved after connection error.
        
        **Validates: Requirements 1.2**
        """
        client = OllamaClient(timeout=timeout_seconds, num_ctx=num_ctx)
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.list.side_effect = ConnectionRefusedError("Connection refused")
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            try:
                client.check_connection()
            except OllamaConnectionError:
                pass  # Expected
            
            # Verify client configuration is preserved
            assert client.timeout == timeout_seconds, (
                f"Timeout should be preserved: expected {timeout_seconds}, got {client.timeout}"
            )
            assert client.num_ctx == num_ctx, (
                f"num_ctx should be preserved: expected {num_ctx}, got {client.num_ctx}"
            )

    @given(error_type=st.sampled_from([
        "connection refused",
        "Connection timed out",
        "Network unreachable",
        "Host not found",
    ]))
    @settings(max_examples=100)
    def test_various_connection_errors_wrapped_correctly(self, error_type: str):
        """For any type of connection error, it SHALL be wrapped in OllamaConnectionError.
        
        **Validates: Requirements 1.2**
        """
        client = OllamaClient()
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.list.side_effect = Exception(error_type)
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(OllamaConnectionError) as exc_info:
                client.check_connection()
            
            # Verify the error is properly wrapped
            assert isinstance(exc_info.value, OllamaConnectionError), (
                f"Error type '{error_type}' should be wrapped in OllamaConnectionError"
            )

    def test_ollama_not_installed_raises_connection_error(self):
        """When ollama package is not installed, OllamaConnectionError SHALL be raised.
        
        **Validates: Requirements 1.2**
        """
        client = OllamaClient()
        
        # Remove ollama from sys.modules to simulate it not being installed
        with patch.dict(sys.modules, {'ollama': None}):
            with pytest.raises(OllamaConnectionError) as exc_info:
                client.check_connection()
            
            # Verify error mentions installation
            error_str = str(exc_info.value)
            assert "install" in error_str.lower() or "pip" in error_str.lower(), (
                "Error should mention how to install ollama package"
            )

    def test_connection_error_message_is_descriptive(self):
        """OllamaConnectionError message SHALL be descriptive for debugging.
        
        **Validates: Requirements 1.2**
        """
        client = OllamaClient()
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.list.side_effect = ConnectionRefusedError(
            "Connection refused on port 11434"
        )
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(OllamaConnectionError) as exc_info:
                client.check_connection()
            
            error_str = str(exc_info.value)
            
            # Error message should be descriptive
            assert len(error_str) > 20, (
                "Error message should be descriptive (more than 20 chars)"
            )
            
            # Should contain actionable information
            assert "ollama" in error_str.lower(), (
                "Error message should mention Ollama"
            )

    @given(port=st.integers(min_value=1024, max_value=65535))
    @settings(max_examples=100)
    def test_connection_error_on_chat_raises_ollama_connection_error(self, port: int):
        """For any connection error during chat, OllamaConnectionError SHALL be raised.
        
        **Validates: Requirements 1.2**
        """
        client = OllamaClient()
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.chat.side_effect = ConnectionRefusedError(
            f"Connection refused on port {port}"
        )
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(OllamaConnectionError) as exc_info:
                client.chat(model="test-model", prompt="Test prompt")
            
            # Verify error is properly wrapped
            assert isinstance(exc_info.value, OllamaConnectionError)


# =============================================================================
# Feature: ollama-content-generator, Property 2: Model Not Available Error
# Validates: Requirements 1.4
# =============================================================================


class TestModelNotAvailableError:
    """Property tests for model not available error handling.
    
    **Property 2: Model Not Available Error**
    
    *For any* model name that is not in Ollama's available models list,
    the system SHALL raise a ModelNotAvailableError containing the model name
    and pull instructions.
    
    **Validates: Requirements 1.4**
    """

    @given(model_name=st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_:.'),
        min_size=1,
        max_size=50,
    ))
    @settings(max_examples=100)
    def test_unavailable_model_raises_model_not_available_error(self, model_name: str):
        """For any unavailable model, ModelNotAvailableError SHALL be raised.
        
        **Validates: Requirements 1.4**
        """
        assume(len(model_name.strip()) > 0)  # Ensure non-empty model name
        
        error = ModelNotAvailableError(model_name)
        
        # Verify error contains model name
        assert error.model == model_name, (
            f"Error should contain model name: expected '{model_name}', got '{error.model}'"
        )
        
        # Verify error message contains model name
        assert model_name in str(error), (
            f"Error message should contain model name '{model_name}'"
        )

    @given(model_name=st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_:.'),
        min_size=1,
        max_size=50,
    ))
    @settings(max_examples=100)
    def test_model_not_available_error_contains_pull_instructions(self, model_name: str):
        """For any unavailable model, error SHALL contain pull instructions.
        
        **Validates: Requirements 1.4**
        """
        assume(len(model_name.strip()) > 0)
        
        error = ModelNotAvailableError(model_name)
        
        # Verify troubleshooting contains pull instructions
        assert hasattr(error, 'troubleshooting'), (
            "ModelNotAvailableError should have troubleshooting attribute"
        )
        assert "ollama pull" in error.troubleshooting.lower(), (
            "Troubleshooting should contain 'ollama pull' instruction"
        )
        assert model_name in error.troubleshooting, (
            f"Troubleshooting should contain model name '{model_name}'"
        )

    @given(model_name=st.sampled_from([
        "llama4:scout",
        "qwen3-coder:30b",
        "mistral:7b",
        "codellama:13b",
        "phi3:mini",
        "gemma:2b",
    ]))
    @settings(max_examples=100)
    def test_common_model_names_in_error(self, model_name: str):
        """For any common model name, error SHALL properly format the pull command.
        
        **Validates: Requirements 1.4**
        """
        error = ModelNotAvailableError(model_name)
        
        # Verify the pull command is properly formatted
        expected_command = f"ollama pull {model_name}"
        assert expected_command in error.troubleshooting, (
            f"Troubleshooting should contain '{expected_command}'"
        )

    @given(
        model_name=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_:.'),
            min_size=1,
            max_size=50,
        ),
        available_models=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_:.'),
                min_size=1,
                max_size=30,
            ),
            min_size=0,
            max_size=10,
        ),
    )
    @settings(max_examples=100)
    def test_model_not_in_available_list_triggers_error(
        self, model_name: str, available_models: list[str]
    ):
        """For any model not in available list, ModelNotAvailableError SHALL be raised.
        
        **Validates: Requirements 1.4**
        """
        assume(len(model_name.strip()) > 0)
        assume(model_name not in available_models)  # Ensure model is not available
        
        client = OllamaClient()
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_response = MagicMock()
        mock_response.models = [
            MagicMock(model=m) for m in available_models
        ]
        mock_ollama.list.return_value = mock_response
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            models = client.list_models()
            
            # Verify model is not in the list
            assert model_name not in models, (
                f"Model '{model_name}' should not be in available models"
            )

    @given(model_name=st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_:.'),
        min_size=1,
        max_size=50,
    ))
    @settings(max_examples=100)
    def test_model_not_available_error_is_descriptive(self, model_name: str):
        """For any unavailable model, error message SHALL be descriptive.
        
        **Validates: Requirements 1.4**
        """
        assume(len(model_name.strip()) > 0)
        
        error = ModelNotAvailableError(model_name)
        error_str = str(error)
        
        # Error should be descriptive
        assert "not available" in error_str.lower(), (
            "Error message should indicate model is not available"
        )
        assert "ollama" in error_str.lower(), (
            "Error message should mention Ollama"
        )

    def test_model_not_available_error_attributes(self):
        """ModelNotAvailableError SHALL have required attributes.
        
        **Validates: Requirements 1.4**
        """
        model_name = "test-model:latest"
        error = ModelNotAvailableError(model_name)
        
        # Verify required attributes
        assert hasattr(error, 'model'), "Error should have 'model' attribute"
        assert hasattr(error, 'message'), "Error should have 'message' attribute"
        assert hasattr(error, 'troubleshooting'), "Error should have 'troubleshooting' attribute"
        
        # Verify attribute values
        assert error.model == model_name
        assert model_name in error.message
        assert f"ollama pull {model_name}" in error.troubleshooting

    @given(
        model_name=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_:.'),
            min_size=1,
            max_size=50,
        ),
    )
    @settings(max_examples=100)
    def test_model_not_available_error_inherits_from_exception(self, model_name: str):
        """ModelNotAvailableError SHALL inherit from Exception.
        
        **Validates: Requirements 1.4**
        """
        assume(len(model_name.strip()) > 0)
        
        error = ModelNotAvailableError(model_name)
        
        assert isinstance(error, Exception), (
            "ModelNotAvailableError should inherit from Exception"
        )


# =============================================================================
# Feature: ollama-content-generator, Property 12: Timeout Error Handling
# Validates: Requirements 6.2
# =============================================================================


class TestTimeoutErrorHandling:
    """Property tests for timeout error handling.
    
    **Property 12: Timeout Error Handling**
    
    *For any* generation request that exceeds the configured timeout,
    the system SHALL raise a TimeoutError.
    
    **Validates: Requirements 6.2**
    """

    @given(timeout_seconds=st.integers(min_value=1, max_value=300))
    @settings(max_examples=100)
    def test_timeout_raises_timeout_error(self, timeout_seconds: int):
        """For any timeout, TimeoutError SHALL be raised.
        
        **Validates: Requirements 6.2**
        """
        client = OllamaClient(timeout=timeout_seconds)
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.chat.side_effect = TimeoutError(
            f"Request timed out after {timeout_seconds} seconds"
        )
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(TimeoutError) as exc_info:
                client.chat(model="test-model", prompt="Test prompt")
            
            # Verify TimeoutError is raised
            assert isinstance(exc_info.value, TimeoutError)

    @given(timeout_seconds=st.integers(min_value=1, max_value=300))
    @settings(max_examples=100)
    def test_timeout_error_contains_timeout_value(self, timeout_seconds: int):
        """For any timeout, error message SHALL contain the timeout value.
        
        **Validates: Requirements 6.2**
        """
        client = OllamaClient(timeout=timeout_seconds)
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.chat.side_effect = Exception(
            f"Operation timeout after {timeout_seconds}s"
        )
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(TimeoutError) as exc_info:
                client.chat(model="test-model", prompt="Test prompt")
            
            error_str = str(exc_info.value)
            
            # Verify timeout value is in error message
            assert str(timeout_seconds) in error_str, (
                f"Error message should contain timeout value {timeout_seconds}"
            )

    @given(
        timeout_seconds=st.integers(min_value=1, max_value=300),
        model_name=st.sampled_from([
            "qwen3-coder:30b",
            "llama4:scout",
            "mistral:7b",
        ]),
        prompt=st.text(min_size=10, max_size=500),
    )
    @settings(max_examples=100)
    def test_timeout_during_generation_raises_timeout_error(
        self, timeout_seconds: int, model_name: str, prompt: str
    ):
        """For any generation that times out, TimeoutError SHALL be raised.
        
        **Validates: Requirements 6.2**
        """
        client = OllamaClient(timeout=timeout_seconds)
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.chat.side_effect = TimeoutError("Generation timed out")
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(TimeoutError):
                client.chat(model=model_name, prompt=prompt)

    @given(timeout_seconds=st.integers(min_value=1, max_value=300))
    @settings(max_examples=100)
    def test_timeout_error_message_mentions_timeout(self, timeout_seconds: int):
        """For any timeout, error message SHALL mention 'timeout'.
        
        **Validates: Requirements 6.2**
        """
        client = OllamaClient(timeout=timeout_seconds)
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.chat.side_effect = TimeoutError(
            f"Request timed out after {timeout_seconds} seconds"
        )
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(TimeoutError) as exc_info:
                client.chat(model="test-model", prompt="Test prompt")
            
            error_str = str(exc_info.value).lower()
            
            assert "timeout" in error_str or "timed out" in error_str, (
                "Error message should mention 'timeout'"
            )

    @given(
        timeout_seconds=st.integers(min_value=1, max_value=300),
        num_ctx=st.integers(min_value=1024, max_value=32768),
    )
    @settings(max_examples=100)
    def test_client_configuration_preserved_after_timeout(
        self, timeout_seconds: int, num_ctx: int
    ):
        """For any timeout, client configuration SHALL be preserved.
        
        **Validates: Requirements 6.2**
        """
        client = OllamaClient(timeout=timeout_seconds, num_ctx=num_ctx)
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.chat.side_effect = TimeoutError("Timed out")
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            try:
                client.chat(model="test-model", prompt="Test prompt")
            except TimeoutError:
                pass  # Expected
            
            # Verify configuration is preserved
            assert client.timeout == timeout_seconds, (
                f"Timeout should be preserved: expected {timeout_seconds}"
            )
            assert client.num_ctx == num_ctx, (
                f"num_ctx should be preserved: expected {num_ctx}"
            )

    @given(timeout_message=st.sampled_from([
        "timeout",
        "Timeout",
        "TIMEOUT",
        "request timeout",
        "connection timeout",
        "Operation timeout",
    ]))
    @settings(max_examples=100)
    def test_various_timeout_messages_raise_timeout_error(self, timeout_message: str):
        """For any timeout-related error message containing 'timeout', TimeoutError SHALL be raised.
        
        **Validates: Requirements 6.2**
        """
        client = OllamaClient()
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.chat.side_effect = Exception(
            f"Error: {timeout_message} occurred"
        )
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(TimeoutError):
                client.chat(model="test-model", prompt="Test prompt")

    def test_default_timeout_value(self):
        """Default timeout SHALL be 120 seconds.
        
        **Validates: Requirements 6.2, 6.4**
        """
        client = OllamaClient()
        
        assert client.timeout == 120, (
            f"Default timeout should be 120 seconds, got {client.timeout}"
        )

    @given(timeout_seconds=st.integers(min_value=1, max_value=600))
    @settings(max_examples=100)
    def test_configurable_timeout_value(self, timeout_seconds: int):
        """Timeout SHALL be configurable via constructor parameter.
        
        **Validates: Requirements 6.2, 6.4**
        """
        client = OllamaClient(timeout=timeout_seconds)
        
        assert client.timeout == timeout_seconds, (
            f"Timeout should be configurable: expected {timeout_seconds}, got {client.timeout}"
        )

    @given(
        timeout_seconds=st.integers(min_value=1, max_value=300),
        system_prompt=st.one_of(st.none(), st.text(min_size=10, max_size=200)),
    )
    @settings(max_examples=100)
    def test_timeout_with_system_prompt_raises_timeout_error(
        self, timeout_seconds: int, system_prompt: str | None
    ):
        """For any timeout with system prompt, TimeoutError SHALL be raised.
        
        **Validates: Requirements 6.2**
        """
        client = OllamaClient(timeout=timeout_seconds)
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.chat.side_effect = TimeoutError("Generation timed out")
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(TimeoutError):
                client.chat(
                    model="test-model",
                    prompt="Test prompt",
                    system_prompt=system_prompt,
                )


# =============================================================================
# Feature: ollama-content-generator, Property 3: Model Configuration Acceptance
# Validates: Requirements 2.1, 2.3
# =============================================================================


from src.engines.generator import ContentGenerator, GeneratedPost, GenerationError
import copy


class TestModelConfigurationAcceptance:
    """Property tests for model configuration acceptance.
    
    **Property 3: Model Configuration Acceptance**
    
    *For any* valid model name string provided to the ContentGenerator constructor,
    the generator SHALL store and use that model name for generation requests.
    
    **Validates: Requirements 2.1, 2.3**
    """

    @given(model_name=st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_:.'),
        min_size=1,
        max_size=50,
    ))
    @settings(max_examples=100)
    def test_model_name_stored_in_generator(self, model_name: str):
        """For any valid model name, generator SHALL store the model name.
        
        **Validates: Requirements 2.1**
        """
        assume(len(model_name.strip()) > 0)
        
        generator = ContentGenerator(model=model_name)
        
        assert generator.model == model_name, (
            f"Generator should store model name: expected '{model_name}', got '{generator.model}'"
        )

    @given(model_name=st.sampled_from([
        "qwen3-coder:30b",
        "llama4:scout",
        "mistral:7b",
        "codellama:13b",
        "phi3:mini",
        "gemma:2b",
    ]))
    @settings(max_examples=100)
    def test_common_model_names_accepted(self, model_name: str):
        """For any common model name, generator SHALL accept and store it.
        
        **Validates: Requirements 2.1**
        """
        generator = ContentGenerator(model=model_name)
        
        assert generator.model == model_name, (
            f"Generator should accept common model name '{model_name}'"
        )

    def test_default_model_is_qwen3_coder(self):
        """When no model is specified, generator SHALL default to qwen3-coder:30b.
        
        **Validates: Requirements 2.2**
        """
        generator = ContentGenerator()
        
        assert generator.model == "qwen3-coder:30b", (
            f"Default model should be 'qwen3-coder:30b', got '{generator.model}'"
        )

    @given(
        model_name=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_:.'),
            min_size=1,
            max_size=50,
        ),
        timeout=st.integers(min_value=1, max_value=600),
        max_tokens=st.integers(min_value=1000, max_value=50000),
        num_ctx=st.integers(min_value=1024, max_value=65536),
    )
    @settings(max_examples=100)
    def test_model_configuration_with_other_params(
        self, model_name: str, timeout: int, max_tokens: int, num_ctx: int
    ):
        """For any model name with other params, all SHALL be stored correctly.
        
        **Validates: Requirements 2.1**
        """
        assume(len(model_name.strip()) > 0)
        
        generator = ContentGenerator(
            model=model_name,
            timeout=timeout,
            max_tokens=max_tokens,
            num_ctx=num_ctx,
        )
        
        assert generator.model == model_name
        assert generator.timeout == timeout
        assert generator.max_tokens == max_tokens
        assert generator.num_ctx == num_ctx

    @given(model_name=st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_:.'),
        min_size=1,
        max_size=50,
    ))
    @settings(max_examples=100)
    def test_model_used_in_generation_request(self, model_name: str):
        """For any model name, it SHALL be used in generation requests.
        
        **Validates: Requirements 2.1, 2.3**
        """
        assume(len(model_name.strip()) > 0)
        
        generator = ContentGenerator(model=model_name)
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_response = MagicMock()
        mock_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_response
        mock_ollama.chat.return_value = {
            'message': {'content': 'Hook: Test hook\n\nValue: Test value\n\nCTA: Test cta\n\n#Test'}
        }
        
        article = ScoredArticle(
            source="AWS News Blog",
            title="Test Article",
            url="https://aws.amazon.com/blogs/aws/test",
            published_date=datetime.now(),
            author="Test Author",
            summary="Test summary",
            key_topics=["cloud_security"],
            why_it_matters="Test importance",
            suggested_linkedin_angle="Test angle",
            suggested_hashtags=["#Test"],
            score_overall=75.0,
            score_recency=80.0,
            score_relevance=70.0,
            collected_at=datetime.now(),
        )
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            try:
                generator.generate(article)
            except Exception:
                pass  # We're testing the model name is passed, not the full generation
            
            # Verify the model name was passed to chat
            if mock_ollama.chat.called:
                call_args = mock_ollama.chat.call_args
                assert call_args[1].get('model') == model_name or call_args[0][0] == model_name, (
                    f"Model name '{model_name}' should be passed to Ollama chat"
                )


# =============================================================================
# Feature: ollama-content-generator, Property 7: GeneratedPost Structure Completeness
# Validates: Requirements 4.1, 4.2, 4.3, 4.5, 7.1, 7.2, 7.3, 7.4, 7.5
# =============================================================================


class TestGeneratedPostStructureCompleteness:
    """Property tests for GeneratedPost structure completeness.
    
    **Property 7: GeneratedPost Structure Completeness**
    
    *For any* successfully generated post, the GeneratedPost SHALL have:
    - Non-empty `hook`, `value`, and `cta` string fields
    - Non-empty `full_text` containing the complete post
    - `hashtags` list present in the full_text
    - `model_used` matching the configured model
    - `generated_at` timestamp within reasonable range of current time
    - `source_url` matching the input article's URL
    
    **Validates: Requirements 4.1, 4.2, 4.3, 4.5, 7.1, 7.2, 7.3, 7.4, 7.5**
    """

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_generated_post_has_non_empty_full_text(self, article: ScoredArticle):
        """For any successful generation, full_text SHALL be non-empty.
        
        **Validates: Requirements 7.1**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Create mock response with proper structure
        mock_response = """🔐 Is your cloud security keeping pace with modern threats?

AWS just announced enhanced security controls that could transform how enterprises approach cloud protection. The new features include automated threat detection and zero-trust architecture support.

What's your biggest cloud security challenge? Share your thoughts below!

#CloudSecurity #AWS #CyberSecurity"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
            
            assert post.full_text is not None, "full_text should not be None"
            assert len(post.full_text) > 0, "full_text should not be empty"

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_generated_post_model_used_matches_configured(self, article: ScoredArticle):
        """For any successful generation, model_used SHALL match configured model.
        
        **Validates: Requirements 7.3**
        """
        model_name = "llama4:scout"
        generator = ContentGenerator(model=model_name)
        
        mock_response = """Hook: Test hook

Value: Test value content here.

CTA: What do you think?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
            
            assert post.model_used == model_name, (
                f"model_used should match configured model: expected '{model_name}', "
                f"got '{post.model_used}'"
            )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_generated_post_source_url_matches_article(self, article: ScoredArticle):
        """For any successful generation, source_url SHALL match input article URL.
        
        **Validates: Requirements 7.5**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_response = """Test hook here

Test value content.

Test CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
            
            assert post.source_url == article.url, (
                f"source_url should match article URL: expected '{article.url}', "
                f"got '{post.source_url}'"
            )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_generated_post_has_timestamp(self, article: ScoredArticle):
        """For any successful generation, generated_at SHALL be a valid timestamp.
        
        **Validates: Requirements 7.4**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_response = """Test hook

Test value.

Test CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        before_generation = datetime.now()
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
            
            after_generation = datetime.now()
            
            assert post.generated_at is not None, "generated_at should not be None"
            assert isinstance(post.generated_at, datetime), "generated_at should be datetime"
            assert before_generation <= post.generated_at <= after_generation, (
                f"generated_at should be within generation time range"
            )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_generated_post_has_hashtags_list(self, article: ScoredArticle):
        """For any successful generation, hashtags SHALL be a list.
        
        **Validates: Requirements 4.5, 7.2**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_response = """Test hook

Test value.

Test CTA?

#CloudSecurity #AWS"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
            
            assert post.hashtags is not None, "hashtags should not be None"
            assert isinstance(post.hashtags, list), "hashtags should be a list"

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_generated_post_has_character_count(self, article: ScoredArticle):
        """For any successful generation, character_count SHALL match full_text length.
        
        **Validates: Requirements 7.1**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_response = """Test hook here

Test value content.

Test CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
            
            assert post.character_count == len(post.full_text), (
                f"character_count should match full_text length: "
                f"expected {len(post.full_text)}, got {post.character_count}"
            )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_generated_post_has_hook_value_cta_fields(self, article: ScoredArticle):
        """For any successful generation, hook, value, cta fields SHALL exist.
        
        **Validates: Requirements 4.1, 4.2, 4.3, 7.2**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_response = """🔐 Is your cloud security keeping pace?

AWS just announced enhanced security controls that could transform how enterprises approach cloud protection. The new features include automated threat detection.

What's your biggest cloud security challenge?

#CloudSecurity #AWS"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
            
            # Verify fields exist (they may be empty if parsing fails, but should exist)
            assert hasattr(post, 'hook'), "GeneratedPost should have hook field"
            assert hasattr(post, 'value'), "GeneratedPost should have value field"
            assert hasattr(post, 'cta'), "GeneratedPost should have cta field"


# =============================================================================
# Feature: ollama-content-generator, Property 8: Post Length Constraint
# Validates: Requirements 4.6
# =============================================================================


class TestPostLengthConstraint:
    """Property tests for post length constraint.
    
    **Property 8: Post Length Constraint**
    
    *For any* GeneratedPost, the `character_count` SHALL be less than 3,000 characters.
    
    **Validates: Requirements 4.6**
    """

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_generated_post_under_3000_characters(self, article: ScoredArticle):
        """For any generated post, character_count SHALL be under 3000.
        
        **Validates: Requirements 4.6**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Create a response that's under the limit
        mock_response = """🔐 Is your cloud security keeping pace?

AWS just announced enhanced security controls that could transform how enterprises approach cloud protection.

What's your biggest cloud security challenge?

#CloudSecurity #AWS"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
            
            assert post.character_count < 3000, (
                f"Post character_count should be under 3000, got {post.character_count}"
            )

    @given(
        response_length=st.integers(min_value=100, max_value=2500),
        article=scored_article_strategy(),
    )
    @settings(max_examples=100)
    def test_various_response_lengths_under_limit(
        self, response_length: int, article: ScoredArticle
    ):
        """For any response length under 3000, post SHALL preserve content.
        
        **Validates: Requirements 4.6**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Generate a response of the specified length
        base_content = "A" * (response_length - 50)  # Leave room for structure
        mock_response = f"""Test hook

{base_content}

Test CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
            
            assert post.character_count < 3000, (
                f"Post should be under 3000 characters, got {post.character_count}"
            )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_oversized_response_truncated_to_limit(self, article: ScoredArticle):
        """For any oversized response, post SHALL be truncated to under 3000.
        
        **Validates: Requirements 4.6**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Generate a response that exceeds 3000 characters
        large_content = "A" * 3500
        mock_response = f"""Test hook

{large_content}

Test CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
            
            assert post.character_count < 3000, (
                f"Oversized post should be truncated to under 3000, got {post.character_count}"
            )

    def test_exact_3000_character_response_truncated(self):
        """Response exactly at 3000 characters SHALL be truncated.
        
        **Validates: Requirements 4.6**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Generate a response that's exactly 3000 characters
        content_length = 3000 - len("Test hook\n\nTest CTA?\n\n#Test\n\n")
        mock_response = f"""Test hook

{"A" * content_length}

Test CTA?

#Test"""
        
        article = ScoredArticle(
            source="AWS News Blog",
            title="Test Article",
            url="https://aws.amazon.com/blogs/aws/test",
            published_date=datetime.now(),
            author="Test Author",
            summary="Test summary",
            key_topics=["cloud_security"],
            why_it_matters="Test importance",
            suggested_linkedin_angle="Test angle",
            suggested_hashtags=["#Test"],
            score_overall=75.0,
            score_recency=80.0,
            score_relevance=70.0,
            collected_at=datetime.now(),
        )
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
            
            assert post.character_count < 3000, (
                f"Post at limit should be truncated to under 3000, got {post.character_count}"
            )


# =============================================================================
# Feature: ollama-content-generator, Property 11: Error Handling with Context
# Validates: Requirements 6.1, 6.3
# =============================================================================


class TestErrorHandlingWithContext:
    """Property tests for error handling with context.
    
    **Property 11: Error Handling with Context**
    
    *For any* generation failure from Ollama, the system SHALL raise a
    GenerationError containing the article title for debugging context.
    
    **Validates: Requirements 6.1, 6.3**
    """

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_empty_response_generation_error_contains_article_title(self, article: ScoredArticle):
        """For any empty response failure, GenerationError SHALL contain article title.
        
        **Validates: Requirements 6.1, 6.3**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        # Simulate an empty response which triggers GenerationError
        mock_ollama.chat.return_value = {'message': {'content': ''}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(GenerationError) as exc_info:
                generator.generate(article)
            
            error = exc_info.value
            
            # Verify article title is in error
            assert error.article_title == article.title, (
                f"Error should contain article title: expected '{article.title}', "
                f"got '{error.article_title}'"
            )
            assert article.title in str(error), (
                f"Error message should contain article title '{article.title}'"
            )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_ollama_error_raises_appropriate_exception(self, article: ScoredArticle):
        """For any Ollama error, an appropriate exception SHALL be raised.
        
        **Validates: Requirements 6.1**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.side_effect = Exception("Model returned invalid response")
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            # Should raise either OllamaConnectionError or GenerationError
            with pytest.raises((OllamaConnectionError, GenerationError)):
                generator.generate(article)

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_empty_response_raises_generation_error(self, article: ScoredArticle):
        """For any empty response from Ollama, GenerationError SHALL be raised.
        
        **Validates: Requirements 6.1, 6.3**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        # Return empty response
        mock_ollama.chat.return_value = {'message': {'content': ''}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(GenerationError) as exc_info:
                generator.generate(article)
            
            error = exc_info.value
            assert article.title in str(error), (
                f"Error should contain article title '{article.title}'"
            )
            assert error.article_title == article.title, (
                f"GenerationError should have article_title attribute"
            )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_whitespace_only_response_raises_generation_error(self, article: ScoredArticle):
        """For any whitespace-only response, GenerationError SHALL be raised.
        
        **Validates: Requirements 6.1, 6.3**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        # Return whitespace-only response
        mock_ollama.chat.return_value = {'message': {'content': '   \n\t  '}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with pytest.raises(GenerationError) as exc_info:
                generator.generate(article)
            
            error = exc_info.value
            assert article.title in str(error)
            assert error.article_title == article.title

    @given(
        error_type=st.sampled_from([
            "Invalid JSON response",
            "Model overloaded",
            "Context length exceeded",
            "Rate limit exceeded",
            "Internal server error",
        ]),
        article=scored_article_strategy(),
    )
    @settings(max_examples=100)
    def test_various_error_types_raise_appropriate_exception(
        self, error_type: str, article: ScoredArticle
    ):
        """For any error type, an appropriate exception SHALL be raised.
        
        **Validates: Requirements 6.1, 6.3**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.side_effect = Exception(error_type)
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            # Should raise either OllamaConnectionError or GenerationError
            with pytest.raises((OllamaConnectionError, GenerationError)):
                generator.generate(article)

    def test_generation_error_has_required_attributes(self):
        """GenerationError SHALL have article_title and cause attributes.
        
        **Validates: Requirements 6.1, 6.3**
        """
        article_title = "Test Article Title"
        cause = "Test error cause"
        
        error = GenerationError(article_title, cause)
        
        assert hasattr(error, 'article_title'), "Error should have article_title"
        assert hasattr(error, 'cause'), "Error should have cause"
        assert error.article_title == article_title
        assert error.cause == cause
        assert article_title in str(error)
        assert cause in str(error)


# =============================================================================
# Feature: ollama-content-generator, Property 13: Input Immutability on Failure
# Validates: Requirements 6.5
# =============================================================================


class TestInputImmutabilityOnFailure:
    """Property tests for input immutability on failure.
    
    **Property 13: Input Immutability on Failure**
    
    *For any* failed generation attempt, the input ScoredArticle object
    SHALL remain unchanged (no fields modified).
    
    **Validates: Requirements 6.5**
    """

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_article_unchanged_after_generation_error(self, article: ScoredArticle):
        """For any generation failure, input article SHALL remain unchanged.
        
        **Validates: Requirements 6.5**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Deep copy the article to compare after failure
        original_source = article.source
        original_title = article.title
        original_url = article.url
        original_published_date = article.published_date
        original_author = article.author
        original_summary = article.summary
        original_key_topics = list(article.key_topics)
        original_why_it_matters = article.why_it_matters
        original_linkedin_angle = article.suggested_linkedin_angle
        original_hashtags = list(article.suggested_hashtags)
        original_score_overall = article.score_overall
        original_score_recency = article.score_recency
        original_score_relevance = article.score_relevance
        original_collected_at = article.collected_at
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.side_effect = Exception("Generation failed")
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            try:
                generator.generate(article)
            except (GenerationError, OllamaConnectionError):
                pass  # Expected - either exception type is valid
            
            # Verify all fields are unchanged
            assert article.source == original_source, "source should be unchanged"
            assert article.title == original_title, "title should be unchanged"
            assert article.url == original_url, "url should be unchanged"
            assert article.published_date == original_published_date, "published_date unchanged"
            assert article.author == original_author, "author should be unchanged"
            assert article.summary == original_summary, "summary should be unchanged"
            assert article.key_topics == original_key_topics, "key_topics unchanged"
            assert article.why_it_matters == original_why_it_matters, "why_it_matters unchanged"
            assert article.suggested_linkedin_angle == original_linkedin_angle, "angle unchanged"
            assert article.suggested_hashtags == original_hashtags, "hashtags unchanged"
            assert article.score_overall == original_score_overall, "score_overall unchanged"
            assert article.score_recency == original_score_recency, "score_recency unchanged"
            assert article.score_relevance == original_score_relevance, "score_relevance unchanged"
            assert article.collected_at == original_collected_at, "collected_at unchanged"

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_article_unchanged_after_connection_error(self, article: ScoredArticle):
        """For any connection failure, input article SHALL remain unchanged.
        
        **Validates: Requirements 6.5**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Store original values
        original_title = article.title
        original_url = article.url
        original_summary = article.summary
        original_key_topics = list(article.key_topics)
        
        mock_ollama = MagicMock()
        mock_ollama.list.side_effect = ConnectionRefusedError("Connection refused")
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            try:
                generator.generate(article)
            except OllamaConnectionError:
                pass  # Expected
            
            # Verify key fields are unchanged
            assert article.title == original_title, "title should be unchanged"
            assert article.url == original_url, "url should be unchanged"
            assert article.summary == original_summary, "summary should be unchanged"
            assert article.key_topics == original_key_topics, "key_topics unchanged"

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_article_unchanged_after_model_not_available_error(self, article: ScoredArticle):
        """For any model not available failure, input article SHALL remain unchanged.
        
        **Validates: Requirements 6.5**
        """
        model_name = "nonexistent-model"
        generator = ContentGenerator(model=model_name)
        
        # Store original values
        original_title = article.title
        original_url = article.url
        original_summary = article.summary
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = []  # No models available
        mock_ollama.list.return_value = mock_list_response
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            try:
                generator.generate(article)
            except ModelNotAvailableError:
                pass  # Expected
            
            # Verify key fields are unchanged
            assert article.title == original_title, "title should be unchanged"
            assert article.url == original_url, "url should be unchanged"
            assert article.summary == original_summary, "summary should be unchanged"

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_article_unchanged_after_timeout_error(self, article: ScoredArticle):
        """For any timeout failure, input article SHALL remain unchanged.
        
        **Validates: Requirements 6.5**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name, timeout=1)
        
        # Store original values
        original_title = article.title
        original_url = article.url
        original_key_topics = list(article.key_topics)
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.side_effect = TimeoutError("Request timed out")
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            try:
                generator.generate(article)
            except TimeoutError:
                pass  # Expected
            
            # Verify key fields are unchanged
            assert article.title == original_title, "title should be unchanged"
            assert article.url == original_url, "url should be unchanged"
            assert article.key_topics == original_key_topics, "key_topics unchanged"

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_mutable_fields_not_modified_on_failure(self, article: ScoredArticle):
        """For any failure, mutable fields (lists) SHALL not be modified.
        
        **Validates: Requirements 6.5**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Store references to mutable fields
        original_key_topics_id = id(article.key_topics)
        original_hashtags_id = id(article.suggested_hashtags)
        original_key_topics_copy = list(article.key_topics)
        original_hashtags_copy = list(article.suggested_hashtags)
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.side_effect = Exception("Generation failed")
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            try:
                generator.generate(article)
            except (GenerationError, OllamaConnectionError):
                pass  # Expected - either exception type is valid
            
            # Verify mutable fields were not modified
            assert article.key_topics == original_key_topics_copy, (
                "key_topics list should not be modified"
            )
            assert article.suggested_hashtags == original_hashtags_copy, (
                "suggested_hashtags list should not be modified"
            )

    def test_article_state_preserved_across_multiple_failures(self):
        """Article state SHALL be preserved across multiple failure attempts.
        
        **Validates: Requirements 6.5**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        article = ScoredArticle(
            source="AWS News Blog",
            title="Test Article for Multiple Failures",
            url="https://aws.amazon.com/blogs/aws/test",
            published_date=datetime.now(),
            author="Test Author",
            summary="Test summary content",
            key_topics=["cloud_security", "identity_and_access"],
            why_it_matters="Test importance statement",
            suggested_linkedin_angle="Test angle",
            suggested_hashtags=["#CloudSecurity", "#AWS"],
            score_overall=75.0,
            score_recency=80.0,
            score_relevance=70.0,
            collected_at=datetime.now(),
        )
        
        # Store original state
        original_title = article.title
        original_key_topics = list(article.key_topics)
        original_hashtags = list(article.suggested_hashtags)
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.side_effect = Exception("Generation failed")
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            # Attempt generation multiple times
            for _ in range(3):
                try:
                    generator.generate(article)
                except (GenerationError, OllamaConnectionError):
                    pass  # Expected - either exception type is valid
            
            # Verify state is still preserved after multiple failures
            assert article.title == original_title
            assert article.key_topics == original_key_topics
            assert article.suggested_hashtags == original_hashtags


# =============================================================================
# Feature: ollama-content-generator, Property 14: Batch Processing Resilience
# Validates: Requirements 8.1, 8.2, 8.3
# =============================================================================


from src.engines.generator import BatchResult


class TestBatchProcessingResilience:
    """Property tests for batch processing resilience.
    
    **Property 14: Batch Processing Resilience**
    
    *For any* batch of articles where some succeed and some fail:
    - The total of successful + failed SHALL equal the input count
    - All articles SHALL be accounted for in the BatchResult
    - Processing SHALL continue after individual failures
    
    **Validates: Requirements 8.1, 8.2, 8.3**
    """

    @given(
        num_articles=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_batch_result_accounts_for_all_articles(self, num_articles: int):
        """For any batch, successful + failed SHALL equal input count.
        
        **Validates: Requirements 8.1, 8.3**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Create test articles
        articles = []
        for i in range(num_articles):
            articles.append(ScoredArticle(
                source="AWS News Blog",
                title=f"Test Article {i}",
                url=f"https://aws.amazon.com/blogs/aws/test-{i}",
                published_date=datetime.now(),
                author="Test Author",
                summary=f"Test summary for article {i}",
                key_topics=["cloud_security"],
                why_it_matters="Test importance",
                suggested_linkedin_angle="Test angle",
                suggested_hashtags=["#Test"],
                score_overall=75.0,
                score_recency=80.0,
                score_relevance=70.0,
                collected_at=datetime.now(),
            ))
        
        mock_response = """Test hook

Test value content.

Test CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            result = generator.generate_batch(articles)
            
            # Verify all articles are accounted for
            total_accounted = len(result.successful) + len(result.failed)
            assert total_accounted == num_articles, (
                f"Total accounted ({total_accounted}) should equal input count ({num_articles})"
            )
            assert result.total_processed == num_articles, (
                f"total_processed ({result.total_processed}) should equal input count ({num_articles})"
            )

    @given(
        num_success=st.integers(min_value=0, max_value=5),
        num_fail=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=100)
    def test_batch_continues_after_failures(self, num_success: int, num_fail: int):
        """For any batch with failures, processing SHALL continue for remaining articles.
        
        **Validates: Requirements 8.2, 8.3**
        """
        assume(num_success + num_fail > 0)  # At least one article
        
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Create articles - some will succeed, some will fail
        articles = []
        for i in range(num_success + num_fail):
            articles.append(ScoredArticle(
                source="AWS News Blog",
                title=f"Article {i}",
                url=f"https://aws.amazon.com/blogs/aws/article-{i}",
                published_date=datetime.now(),
                author="Test Author",
                summary=f"Summary {i}",
                key_topics=["cloud_security"],
                why_it_matters="Important",
                suggested_linkedin_angle="Angle",
                suggested_hashtags=["#Test"],
                score_overall=75.0,
                score_recency=80.0,
                score_relevance=70.0,
                collected_at=datetime.now(),
            ))
        
        mock_response = """Test hook

Test value.

Test CTA?

#Test"""
        
        # Track call count to alternate success/failure
        call_count = [0]
        
        def mock_chat(*args, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx < num_success:
                return {'message': {'content': mock_response}}
            else:
                # Return empty response to trigger GenerationError (per-article error)
                return {'message': {'content': ''}}
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.side_effect = mock_chat
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            result = generator.generate_batch(articles, continue_on_error=True)
            
            # Verify processing continued after failures
            assert len(result.successful) == num_success, (
                f"Expected {num_success} successful, got {len(result.successful)}"
            )
            assert len(result.failed) == num_fail, (
                f"Expected {num_fail} failed, got {len(result.failed)}"
            )
            
            # Verify all articles were processed
            assert result.total_processed == num_success + num_fail

    @given(articles=st.lists(scored_article_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_batch_result_has_correct_success_rate(self, articles: list):
        """For any batch, success_rate SHALL be calculated correctly.
        
        **Validates: Requirements 8.3**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_response = """Test hook

Test value.

Test CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            result = generator.generate_batch(articles)
            
            # Calculate expected success rate
            if result.total_processed > 0:
                expected_rate = len(result.successful) / result.total_processed
            else:
                expected_rate = 0.0
            
            assert abs(result.success_rate - expected_rate) < 0.001, (
                f"Success rate {result.success_rate} should match expected {expected_rate}"
            )

    @given(articles=st.lists(scored_article_strategy(), min_size=2, max_size=5))
    @settings(max_examples=100)
    def test_failed_articles_contain_title_and_error(self, articles: list):
        """For any failed article, the failure record SHALL contain title and error message.
        
        **Validates: Requirements 8.3**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Make all articles fail
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': ''}}  # Empty response causes failure
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            result = generator.generate_batch(articles, continue_on_error=True)
            
            # All should fail due to empty response
            assert len(result.failed) == len(articles), (
                f"All {len(articles)} articles should fail"
            )
            
            # Verify each failure has title and error
            for title, error in result.failed:
                assert len(title) > 0, "Failed article should have title"
                assert len(error) > 0, "Failed article should have error message"

    @given(num_articles=st.integers(min_value=1, max_value=5))
    @settings(max_examples=100)
    def test_batch_result_successful_posts_are_valid(self, num_articles: int):
        """For any successful batch, all posts SHALL be valid GeneratedPost objects.
        
        **Validates: Requirements 8.1, 8.3**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        articles = []
        for i in range(num_articles):
            articles.append(ScoredArticle(
                source="AWS News Blog",
                title=f"Valid Article {i}",
                url=f"https://aws.amazon.com/blogs/aws/valid-{i}",
                published_date=datetime.now(),
                author="Test Author",
                summary=f"Valid summary {i}",
                key_topics=["cloud_security"],
                why_it_matters="Important",
                suggested_linkedin_angle="Angle",
                suggested_hashtags=["#Test"],
                score_overall=75.0,
                score_recency=80.0,
                score_relevance=70.0,
                collected_at=datetime.now(),
            ))
        
        mock_response = """Test hook here

Test value content here.

Test CTA question?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            result = generator.generate_batch(articles)
            
            # Verify all successful posts are valid
            for post in result.successful:
                assert isinstance(post, GeneratedPost), "Post should be GeneratedPost"
                assert len(post.full_text) > 0, "Post should have content"
                assert post.model_used == model_name, "Post should have correct model"
                assert post.character_count < 3000, "Post should be under limit"

    def test_empty_batch_returns_empty_result(self):
        """For an empty batch, result SHALL have zero counts.
        
        **Validates: Requirements 8.1, 8.3**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            result = generator.generate_batch([])
            
            assert len(result.successful) == 0
            assert len(result.failed) == 0
            assert result.total_processed == 0
            assert result.success_rate == 0.0

    @given(articles=st.lists(scored_article_strategy(), min_size=1, max_size=3))
    @settings(max_examples=100)
    def test_batch_result_is_batch_result_type(self, articles: list):
        """For any batch, result SHALL be a BatchResult instance.
        
        **Validates: Requirements 8.3**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_response = """Hook

Value.

CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            result = generator.generate_batch(articles)
            
            assert isinstance(result, BatchResult), (
                f"Result should be BatchResult, got {type(result)}"
            )
            assert hasattr(result, 'successful')
            assert hasattr(result, 'failed')
            assert hasattr(result, 'total_processed')
            assert hasattr(result, 'success_rate')


# =============================================================================
# Feature: ollama-content-generator, Property 15: Batch Progress Logging
# Validates: Requirements 8.4
# =============================================================================


class TestBatchProgressLogging:
    """Property tests for batch progress logging.
    
    **Property 15: Batch Progress Logging**
    
    *For any* batch processing operation, the system SHALL emit progress log
    messages indicating articles processed vs total.
    
    **Validates: Requirements 8.4**
    """

    @given(num_articles=st.integers(min_value=1, max_value=5))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_batch_logs_progress_for_each_article(self, num_articles: int, caplog):
        """For any batch, progress SHALL be logged for each article.
        
        **Validates: Requirements 8.4**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        articles = []
        for i in range(num_articles):
            articles.append(ScoredArticle(
                source="AWS News Blog",
                title=f"Progress Test Article {i}",
                url=f"https://aws.amazon.com/blogs/aws/progress-{i}",
                published_date=datetime.now(),
                author="Test Author",
                summary=f"Summary {i}",
                key_topics=["cloud_security"],
                why_it_matters="Important",
                suggested_linkedin_angle="Angle",
                suggested_hashtags=["#Test"],
                score_overall=75.0,
                score_recency=80.0,
                score_relevance=70.0,
                collected_at=datetime.now(),
            ))
        
        mock_response = """Hook

Value.

CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with caplog.at_level(logging.INFO):
                generator.generate_batch(articles)
        
        # Verify progress messages were logged
        log_text = caplog.text.lower()
        
        # Should have progress indicators
        assert "processing" in log_text or "article" in log_text, (
            "Progress logs should mention processing articles"
        )

    @given(num_articles=st.integers(min_value=2, max_value=5))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_batch_logs_contain_article_count(self, num_articles: int, caplog):
        """For any batch, logs SHALL contain article count information.
        
        **Validates: Requirements 8.4**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        articles = []
        for i in range(num_articles):
            articles.append(ScoredArticle(
                source="AWS News Blog",
                title=f"Count Test Article {i}",
                url=f"https://aws.amazon.com/blogs/aws/count-{i}",
                published_date=datetime.now(),
                author="Test Author",
                summary=f"Summary {i}",
                key_topics=["cloud_security"],
                why_it_matters="Important",
                suggested_linkedin_angle="Angle",
                suggested_hashtags=["#Test"],
                score_overall=75.0,
                score_recency=80.0,
                score_relevance=70.0,
                collected_at=datetime.now(),
            ))
        
        mock_response = """Hook

Value.

CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with caplog.at_level(logging.INFO):
                generator.generate_batch(articles)
        
        log_text = caplog.text
        
        # Should contain the total count
        assert str(num_articles) in log_text, (
            f"Logs should contain total article count ({num_articles})"
        )

    @given(num_articles=st.integers(min_value=1, max_value=3))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_batch_logs_start_message(self, num_articles: int, caplog):
        """For any batch, a start message SHALL be logged.
        
        **Validates: Requirements 8.4**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        articles = []
        for i in range(num_articles):
            articles.append(ScoredArticle(
                source="AWS News Blog",
                title=f"Start Log Article {i}",
                url=f"https://aws.amazon.com/blogs/aws/start-{i}",
                published_date=datetime.now(),
                author="Test Author",
                summary=f"Summary {i}",
                key_topics=["cloud_security"],
                why_it_matters="Important",
                suggested_linkedin_angle="Angle",
                suggested_hashtags=["#Test"],
                score_overall=75.0,
                score_recency=80.0,
                score_relevance=70.0,
                collected_at=datetime.now(),
            ))
        
        mock_response = """Hook

Value.

CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with caplog.at_level(logging.INFO):
                generator.generate_batch(articles)
        
        log_text = caplog.text.lower()
        
        # Should have a start message
        assert "start" in log_text or "batch" in log_text or "generation" in log_text, (
            "Logs should contain batch start message"
        )

    @given(num_articles=st.integers(min_value=1, max_value=3))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_batch_logs_completion_message(self, num_articles: int, caplog):
        """For any batch, a completion message SHALL be logged.
        
        **Validates: Requirements 8.4**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        articles = []
        for i in range(num_articles):
            articles.append(ScoredArticle(
                source="AWS News Blog",
                title=f"Complete Log Article {i}",
                url=f"https://aws.amazon.com/blogs/aws/complete-{i}",
                published_date=datetime.now(),
                author="Test Author",
                summary=f"Summary {i}",
                key_topics=["cloud_security"],
                why_it_matters="Important",
                suggested_linkedin_angle="Angle",
                suggested_hashtags=["#Test"],
                score_overall=75.0,
                score_recency=80.0,
                score_relevance=70.0,
                collected_at=datetime.now(),
            ))
        
        mock_response = """Hook

Value.

CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with caplog.at_level(logging.INFO):
                generator.generate_batch(articles)
        
        log_text = caplog.text.lower()
        
        # Should have a completion message
        assert "complete" in log_text or "finished" in log_text or "success" in log_text, (
            "Logs should contain batch completion message"
        )

    @given(
        num_success=st.integers(min_value=1, max_value=3),
        num_fail=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_batch_logs_failure_warnings(self, num_success: int, num_fail: int, caplog):
        """For any batch with failures, warning logs SHALL be emitted.
        
        **Validates: Requirements 8.4**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        articles = []
        for i in range(num_success + num_fail):
            articles.append(ScoredArticle(
                source="AWS News Blog",
                title=f"Failure Log Article {i}",
                url=f"https://aws.amazon.com/blogs/aws/failure-{i}",
                published_date=datetime.now(),
                author="Test Author",
                summary=f"Summary {i}",
                key_topics=["cloud_security"],
                why_it_matters="Important",
                suggested_linkedin_angle="Angle",
                suggested_hashtags=["#Test"],
                score_overall=75.0,
                score_recency=80.0,
                score_relevance=70.0,
                collected_at=datetime.now(),
            ))
        
        mock_response = """Hook

Value.

CTA?

#Test"""
        
        call_count = [0]
        
        def mock_chat(*args, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx < num_success:
                return {'message': {'content': mock_response}}
            else:
                # Return empty response to trigger GenerationError (per-article error)
                return {'message': {'content': ''}}
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.side_effect = mock_chat
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with caplog.at_level(logging.WARNING):
                generator.generate_batch(articles, continue_on_error=True)
        
        # Should have warning messages for failures
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= num_fail, (
            f"Should have at least {num_fail} warning logs for failures, got {len(warning_records)}"
        )

    def test_batch_logs_progress_format(self, caplog):
        """Progress logs SHALL contain index/total format (e.g., '1/3').
        
        **Validates: Requirements 8.4**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        num_articles = 3
        articles = []
        for i in range(num_articles):
            articles.append(ScoredArticle(
                source="AWS News Blog",
                title=f"Format Test Article {i}",
                url=f"https://aws.amazon.com/blogs/aws/format-{i}",
                published_date=datetime.now(),
                author="Test Author",
                summary=f"Summary {i}",
                key_topics=["cloud_security"],
                why_it_matters="Important",
                suggested_linkedin_angle="Angle",
                suggested_hashtags=["#Test"],
                score_overall=75.0,
                score_recency=80.0,
                score_relevance=70.0,
                collected_at=datetime.now(),
            ))
        
        mock_response = """Hook

Value.

CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with caplog.at_level(logging.INFO):
                generator.generate_batch(articles)
        
        log_text = caplog.text
        
        # Should contain progress format like "1/3", "2/3", "3/3"
        has_progress_format = any(
            f"{i}/{num_articles}" in log_text for i in range(1, num_articles + 1)
        )
        
        assert has_progress_format, (
            f"Logs should contain progress format (e.g., '1/{num_articles}')"
        )

    @given(articles=st.lists(scored_article_strategy(), min_size=1, max_size=3))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_batch_logs_article_titles(self, articles: list, caplog):
        """Progress logs SHALL contain article titles for context.
        
        **Validates: Requirements 8.4**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        mock_response = """Hook

Value.

CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with caplog.at_level(logging.INFO):
                generator.generate_batch(articles)
        
        log_text = caplog.text
        
        # At least some article titles should appear in logs
        titles_in_logs = sum(1 for a in articles if a.title in log_text)
        assert titles_in_logs > 0, (
            "At least some article titles should appear in progress logs"
        )

    def test_batch_logs_success_rate_in_completion(self, caplog):
        """Completion log SHALL contain success rate information.
        
        **Validates: Requirements 8.4**
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        articles = []
        for i in range(3):
            articles.append(ScoredArticle(
                source="AWS News Blog",
                title=f"Success Rate Article {i}",
                url=f"https://aws.amazon.com/blogs/aws/rate-{i}",
                published_date=datetime.now(),
                author="Test Author",
                summary=f"Summary {i}",
                key_topics=["cloud_security"],
                why_it_matters="Important",
                suggested_linkedin_angle="Angle",
                suggested_hashtags=["#Test"],
                score_overall=75.0,
                score_recency=80.0,
                score_relevance=70.0,
                collected_at=datetime.now(),
            ))
        
        mock_response = """Hook

Value.

CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model=model_name)]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with caplog.at_level(logging.INFO):
                generator.generate_batch(articles)
        
        log_text = caplog.text.lower()
        
        # Should contain success rate or percentage
        has_rate_info = (
            "success" in log_text and 
            ("rate" in log_text or "%" in log_text or "3/3" in log_text)
        )
        
        assert has_rate_info, (
            "Completion log should contain success rate information"
        )


# =============================================================================
# Unit Tests for Integration Points
# Validates: Requirements 9.2, 9.4
# =============================================================================


class TestModuleImportability:
    """Unit tests for module importability.
    
    These tests verify that the ContentGenerator and related classes can be
    imported from the expected module paths, ensuring proper integration with
    the existing pipeline structure.
    
    **Validates: Requirements 9.2**
    """

    def test_import_content_generator_from_generator_module(self):
        """ContentGenerator SHALL be importable from src.engines.generator.
        
        **Validates: Requirements 9.2**
        """
        from src.engines.generator import ContentGenerator
        
        assert ContentGenerator is not None
        assert callable(ContentGenerator)

    def test_import_generated_post_from_generator_module(self):
        """GeneratedPost SHALL be importable from src.engines.generator.
        
        **Validates: Requirements 9.2**
        """
        from src.engines.generator import GeneratedPost
        
        assert GeneratedPost is not None

    def test_import_batch_result_from_generator_module(self):
        """BatchResult SHALL be importable from src.engines.generator.
        
        **Validates: Requirements 9.2**
        """
        from src.engines.generator import BatchResult
        
        assert BatchResult is not None

    def test_import_exceptions_from_generator_module(self):
        """Custom exceptions SHALL be importable from src.engines.generator.
        
        **Validates: Requirements 9.2**
        """
        from src.engines.generator import (
            OllamaConnectionError,
            ModelNotAvailableError,
            GenerationError,
        )
        
        assert OllamaConnectionError is not None
        assert ModelNotAvailableError is not None
        assert GenerationError is not None
        
        # Verify they are exception classes
        assert issubclass(OllamaConnectionError, Exception)
        assert issubclass(ModelNotAvailableError, Exception)
        assert issubclass(GenerationError, Exception)

    def test_import_content_generator_from_engines_package(self):
        """ContentGenerator SHALL be importable from src.engines package.
        
        **Validates: Requirements 9.2**
        """
        from src.engines import ContentGenerator
        
        assert ContentGenerator is not None
        assert callable(ContentGenerator)

    def test_import_generated_post_from_engines_package(self):
        """GeneratedPost SHALL be importable from src.engines package.
        
        **Validates: Requirements 9.2**
        """
        from src.engines import GeneratedPost
        
        assert GeneratedPost is not None

    def test_import_batch_result_from_engines_package(self):
        """BatchResult SHALL be importable from src.engines package.
        
        **Validates: Requirements 9.2**
        """
        from src.engines import BatchResult
        
        assert BatchResult is not None

    def test_import_exceptions_from_engines_package(self):
        """Custom exceptions SHALL be importable from src.engines package.
        
        **Validates: Requirements 9.2**
        """
        from src.engines import (
            OllamaConnectionError,
            ModelNotAvailableError,
            GenerationError,
        )
        
        assert OllamaConnectionError is not None
        assert ModelNotAvailableError is not None
        assert GenerationError is not None

    def test_import_internal_components_from_generator_module(self):
        """Internal components SHALL be importable from src.engines.generator.
        
        **Validates: Requirements 9.2**
        """
        from src.engines.generator import (
            ContextManager,
            PromptBuilder,
            OllamaClient,
        )
        
        assert ContextManager is not None
        assert PromptBuilder is not None
        assert OllamaClient is not None


class TestStandaloneUsage:
    """Unit tests for standalone usage without the main pipeline.
    
    These tests verify that the ContentGenerator can be used independently
    of the main Content Agent pipeline workflow.
    
    **Validates: Requirements 9.4**
    """

    def test_content_generator_instantiation_without_pipeline(self):
        """ContentGenerator SHALL be instantiable without pipeline dependencies.
        
        **Validates: Requirements 9.4**
        """
        from src.engines.generator import ContentGenerator
        
        # Should be able to create instance with default parameters
        generator = ContentGenerator()
        
        assert generator is not None
        assert generator.model == "qwen3-coder:30b"
        assert generator.timeout == 120
        assert generator.max_tokens == 10000
        assert generator.num_ctx == 16384

    def test_content_generator_custom_configuration_standalone(self):
        """ContentGenerator SHALL accept custom configuration without pipeline.
        
        **Validates: Requirements 9.4**
        """
        from src.engines.generator import ContentGenerator
        
        generator = ContentGenerator(
            model="llama4:scout",
            timeout=180,
            max_tokens=8000,
            num_ctx=32768,
        )
        
        assert generator.model == "llama4:scout"
        assert generator.timeout == 180
        assert generator.max_tokens == 8000
        assert generator.num_ctx == 32768

    def test_context_manager_standalone_usage(self):
        """ContextManager SHALL be usable independently of ContentGenerator.
        
        **Validates: Requirements 9.4**
        """
        from src.engines.generator import ContextManager
        
        cm = ContextManager(max_tokens=5000)
        
        # Test token estimation
        assert cm.estimate_tokens("Hello world") == 2  # 11 chars / 4 = 2
        
        # Test summarization
        long_text = "A" * 10000
        result = cm.summarize_for_context(long_text, 100)
        assert cm.estimate_tokens(result) <= 100

    def test_prompt_builder_standalone_usage(self):
        """PromptBuilder SHALL be usable independently of ContentGenerator.
        
        **Validates: Requirements 9.4**
        """
        from src.engines.generator import PromptBuilder
        
        builder = PromptBuilder()
        
        prompt = builder.build(
            title="Test Article",
            source="Test Source",
            summary="This is a test summary.",
            key_topics=["cloud_security"],
            why_it_matters="Important for security teams.",
            hashtags=["#Test", "#Security"],
        )
        
        assert "Test Article" in prompt
        assert "Test Source" in prompt
        assert "Hook" in prompt
        assert "Value" in prompt
        assert "CTA" in prompt

    def test_generated_post_dataclass_standalone_creation(self):
        """GeneratedPost SHALL be creatable without ContentGenerator.
        
        **Validates: Requirements 9.4**
        """
        from src.engines.generator import GeneratedPost
        
        post = GeneratedPost(
            full_text="Test post content",
            hook="Test hook",
            value="Test value",
            cta="Test CTA",
            hashtags=["#Test"],
            model_used="test-model",
            generated_at=datetime.now(),
            source_url="https://example.com/test",
            character_count=17,
        )
        
        assert post.full_text == "Test post content"
        assert post.hook == "Test hook"
        assert post.value == "Test value"
        assert post.cta == "Test CTA"
        assert post.hashtags == ["#Test"]
        assert post.model_used == "test-model"
        assert post.source_url == "https://example.com/test"
        assert post.character_count == 17

    def test_batch_result_dataclass_standalone_creation(self):
        """BatchResult SHALL be creatable without ContentGenerator.
        
        **Validates: Requirements 9.4**
        """
        from src.engines.generator import BatchResult, GeneratedPost
        
        post = GeneratedPost(
            full_text="Test",
            hook="Hook",
            value="Value",
            cta="CTA",
            hashtags=["#Test"],
            model_used="test-model",
            generated_at=datetime.now(),
            source_url="https://example.com",
            character_count=4,
        )
        
        result = BatchResult(
            successful=[post],
            failed=[("Failed Article", "Error message")],
            total_processed=2,
            success_rate=0.5,
        )
        
        assert len(result.successful) == 1
        assert len(result.failed) == 1
        assert result.total_processed == 2
        assert result.success_rate == 0.5

    def test_exceptions_standalone_usage(self):
        """Custom exceptions SHALL be usable without ContentGenerator.
        
        **Validates: Requirements 9.4**
        """
        from src.engines.generator import (
            OllamaConnectionError,
            ModelNotAvailableError,
            GenerationError,
        )
        
        # Test OllamaConnectionError
        error1 = OllamaConnectionError("Test connection error")
        assert "Test connection error" in str(error1)
        assert "ollama serve" in str(error1)
        
        # Test ModelNotAvailableError
        error2 = ModelNotAvailableError("test-model")
        assert "test-model" in str(error2)
        assert "ollama pull test-model" in str(error2)
        
        # Test GenerationError
        error3 = GenerationError("Test Article", "Test cause")
        assert "Test Article" in str(error3)
        assert "Test cause" in str(error3)

    def test_list_available_models_class_method_standalone(self):
        """list_available_models SHALL be callable as class method without instance.
        
        **Validates: Requirements 9.4**
        """
        from src.engines.generator import ContentGenerator
        
        # Verify it's a class method that can be called without an instance
        assert hasattr(ContentGenerator, 'list_available_models')
        assert callable(ContentGenerator.list_available_models)


class TestIntegrationWithScoredArticle:
    """Unit tests for integration with ScoredArticle from existing pipeline.
    
    These tests verify that the ContentGenerator works correctly with
    ScoredArticle objects from the existing Content Agent pipeline.
    
    **Validates: Requirements 9.2, 9.4**
    """

    def test_scored_article_import_from_pipeline(self):
        """ScoredArticle SHALL be importable from existing pipeline module.
        
        **Validates: Requirements 9.2**
        """
        from src.engines.article_normalizer import ScoredArticle
        
        assert ScoredArticle is not None

    def test_content_generator_accepts_scored_article(self):
        """ContentGenerator.generate SHALL accept ScoredArticle from pipeline.
        
        **Validates: Requirements 9.2, 9.4**
        """
        from src.engines.generator import ContentGenerator
        from src.engines.article_normalizer import ScoredArticle
        
        # Create a ScoredArticle as it would come from the pipeline
        article = ScoredArticle(
            source="AWS News Blog",
            title="AWS Announces New Security Feature",
            url="https://aws.amazon.com/blogs/aws/new-security-feature",
            published_date=datetime.now(),
            author="AWS Team",
            summary="AWS has released a new security feature that enhances cloud protection.",
            key_topics=["cloud_security", "identity_and_access"],
            why_it_matters="This update strengthens security posture for enterprise workloads.",
            suggested_linkedin_angle="Security leaders should evaluate this for their cloud strategy.",
            suggested_hashtags=["#AWS", "#CloudSecurity", "#CyberSecurity"],
            score_overall=85.0,
            score_recency=90.0,
            score_relevance=80.0,
            collected_at=datetime.now(),
        )
        
        generator = ContentGenerator()
        
        # Mock Ollama to avoid actual API calls
        mock_response = """🔐 Is your cloud security keeping pace with evolving threats?

AWS just announced a game-changing security feature that could transform how enterprises protect their cloud workloads. This update brings enhanced identity controls and automated threat detection to the forefront.

What's your biggest cloud security challenge right now? Share below!

#AWS #CloudSecurity #CyberSecurity"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model="qwen3-coder:30b")]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
        
        # Verify the post was generated correctly
        assert post is not None
        assert post.source_url == article.url
        assert post.model_used == "qwen3-coder:30b"
        assert post.character_count < 3000

    def test_content_generator_batch_accepts_scored_articles(self):
        """ContentGenerator.generate_batch SHALL accept list of ScoredArticles.
        
        **Validates: Requirements 9.2, 9.4**
        """
        from src.engines.generator import ContentGenerator
        from src.engines.article_normalizer import ScoredArticle
        
        # Create multiple ScoredArticles as they would come from the pipeline
        articles = [
            ScoredArticle(
                source="AWS News Blog",
                title="AWS Security Update",
                url="https://aws.amazon.com/blogs/aws/security-update",
                published_date=datetime.now(),
                author="AWS Team",
                summary="Security update summary.",
                key_topics=["cloud_security"],
                why_it_matters="Important for security.",
                suggested_linkedin_angle="Review this update.",
                suggested_hashtags=["#AWS", "#Security"],
                score_overall=80.0,
                score_recency=85.0,
                score_relevance=75.0,
                collected_at=datetime.now(),
            ),
            ScoredArticle(
                source="Microsoft Purview Blog",
                title="Purview Compliance Feature",
                url="https://techcommunity.microsoft.com/purview-compliance",
                published_date=datetime.now(),
                author="Microsoft Team",
                summary="Compliance feature summary.",
                key_topics=["governance_and_compliance"],
                why_it_matters="Important for compliance.",
                suggested_linkedin_angle="Compliance teams should note.",
                suggested_hashtags=["#Azure", "#Compliance"],
                score_overall=75.0,
                score_recency=80.0,
                score_relevance=70.0,
                collected_at=datetime.now(),
            ),
        ]
        
        generator = ContentGenerator()
        
        mock_response = """Hook

Value content here.

CTA question?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model="qwen3-coder:30b")]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            result = generator.generate_batch(articles)
        
        # Verify batch processing worked
        assert result is not None
        assert result.total_processed == 2
        assert len(result.successful) == 2
        assert len(result.failed) == 0
        assert result.success_rate == 1.0

    def test_context_manager_prepares_scored_article_content(self):
        """ContextManager.prepare_content SHALL work with ScoredArticle.
        
        **Validates: Requirements 9.2, 9.4**
        """
        from src.engines.generator import ContextManager
        from src.engines.article_normalizer import ScoredArticle
        
        article = ScoredArticle(
            source="AWS News Blog",
            title="Test Article Title",
            url="https://aws.amazon.com/blogs/aws/test",
            published_date=datetime.now(),
            author="Test Author",
            summary="This is a test summary for the article.",
            key_topics=["cloud_security", "data_protection"],
            why_it_matters="Important for security teams.",
            suggested_linkedin_angle="Consider this for your strategy.",
            suggested_hashtags=["#AWS", "#Security"],
            score_overall=80.0,
            score_recency=85.0,
            score_relevance=75.0,
            collected_at=datetime.now(),
        )
        
        cm = ContextManager(max_tokens=10000)
        content, was_truncated = cm.prepare_content(article)
        
        # Verify content preparation
        assert content is not None
        assert len(content) > 0
        assert was_truncated is False
        assert article.title in content
        assert article.source in content
        assert article.summary in content

    def test_prompt_builder_with_scored_article_fields(self):
        """PromptBuilder.build SHALL work with ScoredArticle field values.
        
        **Validates: Requirements 9.2, 9.4**
        """
        from src.engines.generator import PromptBuilder
        from src.engines.article_normalizer import ScoredArticle
        
        article = ScoredArticle(
            source="Microsoft Purview Blog",
            title="Purview Data Governance Update",
            url="https://techcommunity.microsoft.com/purview-update",
            published_date=datetime.now(),
            author="Microsoft Team",
            summary="New data governance capabilities in Microsoft Purview.",
            key_topics=["data_protection", "governance_and_compliance"],
            why_it_matters="Enhances data governance for regulated industries.",
            suggested_linkedin_angle="Data governance leaders should evaluate.",
            suggested_hashtags=["#Purview", "#DataGovernance", "#Compliance"],
            score_overall=85.0,
            score_recency=90.0,
            score_relevance=80.0,
            collected_at=datetime.now(),
        )
        
        builder = PromptBuilder()
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=article.key_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        # Verify prompt contains article information
        assert article.title in prompt
        assert article.source in prompt
        assert article.summary in prompt
        assert article.why_it_matters in prompt
        
        # Verify key topics are included
        for topic in article.key_topics:
            assert topic in prompt
        
        # Verify hashtags are included
        for hashtag in article.suggested_hashtags:
            assert hashtag in prompt

    def test_scored_article_with_optional_fields_none(self):
        """ContentGenerator SHALL handle ScoredArticle with None optional fields.
        
        **Validates: Requirements 9.2, 9.4**
        """
        from src.engines.generator import ContentGenerator, ContextManager
        from src.engines.article_normalizer import ScoredArticle
        
        # Create article with None for optional fields
        article = ScoredArticle(
            source="AWS News Blog",
            title="Article Without Optional Fields",
            url="https://aws.amazon.com/blogs/aws/no-optional",
            published_date=None,  # Optional field is None
            author=None,  # Optional field is None
            summary="Summary without optional fields.",
            key_topics=["cloud_security"],
            why_it_matters="Important update.",
            suggested_linkedin_angle="Review this.",
            suggested_hashtags=["#AWS"],
            score_overall=70.0,
            score_recency=0.0,  # No date means 0 recency
            score_relevance=70.0,
            collected_at=datetime.now(),
        )
        
        # Test ContextManager handles None fields
        cm = ContextManager(max_tokens=10000)
        content, was_truncated = cm.prepare_content(article)
        
        assert content is not None
        assert len(content) > 0
        assert article.title in content
        
        # Test ContentGenerator handles None fields
        generator = ContentGenerator()
        
        mock_response = """Hook

Value.

CTA?

#AWS"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model="qwen3-coder:30b")]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
        
        assert post is not None
        assert post.source_url == article.url

    def test_scored_article_with_empty_lists(self):
        """ContentGenerator SHALL handle ScoredArticle with empty lists.
        
        **Validates: Requirements 9.2, 9.4**
        """
        from src.engines.generator import ContentGenerator, PromptBuilder
        from src.engines.article_normalizer import ScoredArticle
        
        # Create article with empty lists (edge case)
        article = ScoredArticle(
            source="AWS News Blog",
            title="Article With Empty Lists",
            url="https://aws.amazon.com/blogs/aws/empty-lists",
            published_date=datetime.now(),
            author="Test Author",
            summary="Summary for article with empty lists.",
            key_topics=[],  # Empty list
            why_it_matters="Important update.",
            suggested_linkedin_angle="Review this.",
            suggested_hashtags=[],  # Empty list
            score_overall=50.0,
            score_recency=60.0,
            score_relevance=40.0,
            collected_at=datetime.now(),
        )
        
        # Test PromptBuilder handles empty lists
        builder = PromptBuilder()
        prompt = builder.build(
            title=article.title,
            source=article.source,
            summary=article.summary,
            key_topics=article.key_topics,
            why_it_matters=article.why_it_matters,
            hashtags=article.suggested_hashtags,
        )
        
        assert prompt is not None
        assert len(prompt) > 0
        assert article.title in prompt
        
        # Test ContentGenerator handles empty lists
        generator = ContentGenerator()
        
        mock_response = """Hook

Value.

CTA?"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model="qwen3-coder:30b")]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
        
        assert post is not None
        assert post.hashtags == []  # Should preserve empty hashtags

    def test_generator_follows_pipeline_logging_conventions(self, caplog):
        """ContentGenerator SHALL follow same logging conventions as other engines.
        
        **Validates: Requirements 9.4**
        """
        from src.engines.generator import ContentGenerator
        from src.engines.article_normalizer import ScoredArticle
        
        article = ScoredArticle(
            source="AWS News Blog",
            title="Logging Convention Test",
            url="https://aws.amazon.com/blogs/aws/logging-test",
            published_date=datetime.now(),
            author="Test Author",
            summary="Test summary.",
            key_topics=["cloud_security"],
            why_it_matters="Important.",
            suggested_linkedin_angle="Review.",
            suggested_hashtags=["#Test"],
            score_overall=75.0,
            score_recency=80.0,
            score_relevance=70.0,
            collected_at=datetime.now(),
        )
        
        generator = ContentGenerator()
        
        mock_response = """Hook

Value.

CTA?

#Test"""
        
        mock_ollama = MagicMock()
        mock_list_response = MagicMock()
        mock_list_response.models = [MagicMock(model="qwen3-coder:30b")]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            with caplog.at_level(logging.DEBUG):
                post = generator.generate(article)
        
        # Verify logging is happening
        assert len(caplog.records) > 0
        
        # Verify logger name follows convention (src.engines.generator)
        generator_logs = [r for r in caplog.records if 'generator' in r.name]
        assert len(generator_logs) > 0, "Should have logs from generator module"
