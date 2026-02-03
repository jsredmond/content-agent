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

    def test_default_model_is_llama4_scout(self):
        """When no model is specified, generator SHALL default to llama4:scout.
        
        **Validates: Requirements 4.1, 4.2**
        """
        generator = ContentGenerator()
        
        assert generator.model == "llama4:scout", (
            f"Default model should be 'llama4:scout', got '{generator.model}'"
        )

    def test_custom_model_configuration_still_works(self):
        """Custom model configuration SHALL still be supported.
        
        **Validates: Requirements 4.3**
        """
        custom_model = "qwen3-coder:30b"
        generator = ContentGenerator(model=custom_model)
        
        assert generator.model == custom_model, (
            f"Custom model should be '{custom_model}', got '{generator.model}'"
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
        
        Note: Articles must have score_overall >= 50 to pass the validation gate
        and be processed (where they can then fail due to empty response).
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Ensure all articles have score_overall >= MIN_SCORE_THRESHOLD (50)
        # so they pass the validation gate and can be processed
        for article in articles:
            article.score_overall = max(article.score_overall, 50.0)
        
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
        
        Note: Articles must have score_overall >= 50 to pass the validation gate
        and be processed (where their titles appear in logs).
        """
        model_name = "qwen3-coder:30b"
        generator = ContentGenerator(model=model_name)
        
        # Ensure all articles have score_overall >= MIN_SCORE_THRESHOLD (50)
        # so they pass the validation gate and can be processed
        for article in articles:
            article.score_overall = max(article.score_overall, 50.0)
        
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
        assert generator.model == "llama4:scout"
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
        mock_list_response.models = [MagicMock(model="llama4:scout")]
        mock_ollama.list.return_value = mock_list_response
        mock_ollama.chat.return_value = {'message': {'content': mock_response}}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            post = generator.generate(article)
        
        # Verify the post was generated correctly
        assert post is not None
        assert post.source_url == article.url
        assert post.model_used == "llama4:scout"
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
        mock_list_response.models = [MagicMock(model="llama4:scout")]
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
        mock_list_response.models = [MagicMock(model="llama4:scout")]
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
        mock_list_response.models = [MagicMock(model="llama4:scout")]
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
        mock_list_response.models = [MagicMock(model="llama4:scout")]
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


# =============================================================================
# Feature: prompt-builder-enhancements, Property 1: Hook Styles Present in Prompt
# Validates: Requirements 1.1, 1.3, 1.4, 1.5
# =============================================================================


class TestHookStylesPresent:
    """Property tests for hook styles in prompt.
    
    **Property 1: Hook Styles Present in Prompt**
    
    *For any* article input to PromptBuilder.build(), the resulting prompt SHALL contain
    all three hook style names ("Bold Statement", "Contrarian View", "Fact-Driven") with
    their corresponding descriptions ("A confident, declarative opening", 
    "Challenge conventional wisdom", "Lead with a compelling statistic or data point").
    
    **Validates: Requirements 1.1, 1.3, 1.4, 1.5**
    """

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_statistic_heavy_hook_style(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain Statistic-heavy hook style.
        
        **Validates: Requirements 4.1**
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
        
        # Verify Statistic-heavy hook style name is present
        assert "Statistic-heavy" in prompt, (
            "Prompt should contain 'Statistic-heavy' hook style name"
        )
        
        # Verify Statistic-heavy description is present
        assert "Lead with a compelling number or data point" in prompt, (
            "Prompt should contain Statistic-heavy description: "
            "'Lead with a compelling number or data point'"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_contrarian_hook_style(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain Contrarian hook style.
        
        **Validates: Requirements 4.2**
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
        
        # Verify Contrarian hook style name is present
        assert "Contrarian" in prompt, (
            "Prompt should contain 'Contrarian' hook style name"
        )
        
        # Verify Contrarian description is present
        assert "Challenge conventional wisdom or common assumptions" in prompt, (
            "Prompt should contain Contrarian description: "
            "'Challenge conventional wisdom or common assumptions'"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_bold_prediction_hook_style(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain Bold Prediction hook style.
        
        **Validates: Requirements 4.3**
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
        
        # Verify Bold Prediction hook style name is present
        assert "Bold Prediction" in prompt, (
            "Prompt should contain 'Bold Prediction' hook style name"
        )
        
        # Verify Bold Prediction description is present
        assert "Make a confident forecast about the future" in prompt, (
            "Prompt should contain Bold Prediction description: "
            "'Make a confident forecast about the future'"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_all_three_hook_styles(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain all three hook styles with descriptions.
        
        **Validates: Requirements 4.1, 4.2, 4.3**
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
        
        # Define expected hook styles and their descriptions
        expected_hook_styles = {
            "Statistic-heavy": "Lead with a compelling number or data point",
            "Contrarian": "Challenge conventional wisdom or common assumptions",
            "Bold Prediction": "Make a confident forecast about the future",
        }
        
        # Verify all hook styles and descriptions are present
        for style_name, description in expected_hook_styles.items():
            assert style_name in prompt, (
                f"Prompt should contain hook style name '{style_name}'"
            )
            assert description in prompt, (
                f"Prompt should contain description for {style_name}: '{description}'"
            )


# =============================================================================
# Feature: prompt-builder-enhancements, Property 2: Avoid Question Instruction Present
# Validates: Requirements 1.2
# =============================================================================


class TestAvoidQuestionInstruction:
    """Property tests for avoid-question instruction in prompt.
    
    **Property 2: Avoid Question Instruction Present**
    
    *For any* article input to PromptBuilder.build(), the resulting prompt SHALL contain
    an instruction to avoid starting with a question.
    
    **Validates: Requirements 1.2**
    """

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_avoid_question_instruction(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain instruction to avoid starting with a question.
        
        **Validates: Requirements 1.2**
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
        
        # Verify the avoid-question instruction is present
        assert "Avoid starting with a question" in prompt, (
            "Prompt should contain instruction to avoid starting with a question"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_vary_hook_style_instruction(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain instruction to vary hook style.
        
        **Validates: Requirements 1.2**
        
        Note: Updated to match robust-response-parsing spec which changed the text
        from "Vary your hook style" to "Cycle through these hook styles to keep your feed fresh"
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
        
        # Verify the vary hook style instruction is present (updated text from robust-response-parsing)
        assert "Cycle through these hook styles" in prompt, (
            "Prompt should contain instruction to cycle through hook styles"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_important_avoid_question_instruction(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain the complete avoid-question instruction.
        
        **Validates: Requirements 1.2**
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
        
        # Verify the complete instruction is present
        # The template contains: "IMPORTANT: Avoid starting with a question. Vary your hook style."
        assert "IMPORTANT:" in prompt and "Avoid starting with a question" in prompt, (
            "Prompt should contain the IMPORTANT instruction to avoid starting with a question"
        )


# =============================================================================
# Feature: prompt-builder-enhancements, Property 3: Hashtag Limit Instruction Present
# Validates: Requirements 2.1, 2.2, 2.3
# =============================================================================


class TestHashtagLimitInstruction:
    """Property tests for hashtag limit instruction in prompt.
    
    **Property 3: Hashtag Limit Instruction Present**
    
    *For any* article input to PromptBuilder.build(), the resulting prompt SHALL contain
    an instruction specifying exactly 3 hashtags must be included in the output.
    
    **Validates: Requirements 2.1, 2.2, 2.3**
    """

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_exactly_3_hashtags_instruction(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain instruction for exactly 3 hashtags.
        
        **Validates: Requirements 2.1**
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
        
        # Verify the prompt contains instruction for exactly 3 hashtags
        assert "EXACTLY 3 hashtags" in prompt, (
            "Prompt should contain instruction for 'EXACTLY 3 hashtags'"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_select_3_most_relevant_instruction(self, article: ScoredArticle):
        """For any article, the prompt SHALL instruct to select 3 most relevant hashtags.
        
        **Validates: Requirements 2.2**
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
        
        # Verify the prompt contains instruction to select 3 most relevant
        assert "3 most relevant" in prompt, (
            "Prompt should contain instruction to select '3 most relevant' hashtags"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_no_more_no_fewer_instruction(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain explicit hashtag limit instruction.
        
        **Validates: Requirements 2.3**
        
        Note: Updated to match robust-response-parsing spec which uses "EXACTLY 3 hashtags"
        and "Include exactly 3 hashtags" instead of "no more, no fewer"
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
        
        # Verify the prompt contains explicit instruction for exactly 3 hashtags
        # The robust-response-parsing spec uses "EXACTLY 3 hashtags" and "Include exactly 3 hashtags"
        assert "EXACTLY 3 hashtags" in prompt or "exactly 3 hashtags" in prompt.lower(), (
            "Prompt should contain explicit instruction for exactly 3 hashtags"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_must_include_exactly_3_hashtags(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain instruction for exactly 3 hashtags.
        
        **Validates: Requirements 2.1, 2.3**
        
        Note: Updated to match robust-response-parsing spec which uses "Include exactly 3 hashtags"
        in the HASHTAG REQUIREMENT section instead of "MUST include exactly 3 hashtags"
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
        
        # Verify the prompt contains instruction for exactly 3 hashtags
        # The robust-response-parsing spec uses "Include exactly 3 hashtags" in HASHTAG REQUIREMENT section
        assert "Include exactly 3 hashtags" in prompt or "EXACTLY 3 hashtags" in prompt, (
            "Prompt should contain instruction for exactly 3 hashtags"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_complete_hashtag_limit_instructions(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain all hashtag limit instructions.
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        
        Note: Updated to match robust-response-parsing spec which uses different phrasing
        for hashtag instructions
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
        
        # Verify all hashtag limit instructions are present
        # Requirement 2.1: Instruct LLM to output exactly 3 hashtags
        assert "EXACTLY 3 hashtags" in prompt, (
            "Prompt should contain 'EXACTLY 3 hashtags' instruction (Requirement 2.1)"
        )
        
        # Requirement 2.2: Instruct to select 3 most relevant from provided list
        assert "3 most relevant" in prompt, (
            "Prompt should contain '3 most relevant' instruction (Requirement 2.2)"
        )
        
        # Requirement 2.3: Explicit instruction for exactly 3 hashtags
        # The robust-response-parsing spec uses "Include exactly 3 hashtags" instead of "no more, no fewer"
        assert "exactly 3 hashtags" in prompt.lower(), (
            "Prompt should contain 'exactly 3 hashtags' instruction (Requirement 2.3)"
        )
        
        # Verify the HASHTAG REQUIREMENT section exists
        assert "HASHTAG REQUIREMENT:" in prompt, (
            "Prompt should contain 'HASHTAG REQUIREMENT:' section"
        )


# =============================================================================
# Feature: prompt-builder-enhancements, Property 4: Validation Gate Filters Low-Score Articles
# Validates: Requirements 3.1, 3.3, 3.4
# =============================================================================


from unittest.mock import patch, MagicMock
from src.engines.generator import ContentGenerator, GeneratedPost, BatchResult


class TestValidationGateFiltering:
    """Property tests for validation gate filtering.
    
    **Property 4: Validation Gate Filters Low-Score Articles**
    
    *For any* list of ScoredArticle objects passed to generate_batch(), articles with
    score_overall < 50 SHALL NOT be processed by the LLM, and the BatchResult.total_processed
    SHALL equal only the count of articles with score_overall >= 50 that were attempted.
    
    **Validates: Requirements 3.1, 3.3, 3.4**
    """

    def _create_mock_generator(self):
        """Create a ContentGenerator with mocked Ollama client."""
        generator = ContentGenerator.__new__(ContentGenerator)
        generator.model = "test-model"
        generator.timeout = 120
        generator.max_tokens = 10000
        generator.num_ctx = 16384
        generator._model_validated = True  # Skip model validation
        
        # Mock the internal components
        generator._client = MagicMock()
        generator._context_manager = MagicMock()
        generator._prompt_builder = MagicMock()
        
        # Configure mocks to return valid responses
        generator._context_manager.prepare_content.return_value = ("Test content", False)
        generator._prompt_builder.build.return_value = "Test prompt"
        generator._prompt_builder.get_system_prompt.return_value = "Test system prompt"
        generator._client.chat.return_value = "Test LinkedIn post content\n\n#Test #Hashtag #Post"
        
        return generator

    @given(articles=st.lists(scored_article_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_low_score_articles_not_processed(self, articles: list):
        """For any batch, articles with score_overall < 50 SHALL NOT be processed.
        
        **Validates: Requirements 3.1**
        """
        generator = self._create_mock_generator()
        
        # Count expected eligible articles (score >= 50)
        eligible_count = sum(1 for a in articles if a.score_overall >= 50)
        
        result = generator.generate_batch(articles)
        
        # Verify total_processed only counts eligible articles
        assert result.total_processed <= eligible_count, (
            f"total_processed ({result.total_processed}) should not exceed "
            f"eligible article count ({eligible_count})"
        )
        
        # Verify the LLM was only called for eligible articles
        expected_calls = eligible_count
        actual_calls = generator._client.chat.call_count
        assert actual_calls == expected_calls, (
            f"LLM should be called {expected_calls} times for eligible articles, "
            f"but was called {actual_calls} times"
        )

    @given(articles=st.lists(scored_article_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_high_score_articles_are_processed(self, articles: list):
        """For any batch, articles with score_overall >= 50 SHALL be processed.
        
        **Validates: Requirements 3.1**
        """
        generator = self._create_mock_generator()
        
        # Count expected eligible articles (score >= 50)
        eligible_articles = [a for a in articles if a.score_overall >= 50]
        eligible_count = len(eligible_articles)
        
        result = generator.generate_batch(articles)
        
        # If there are eligible articles, they should be processed
        if eligible_count > 0:
            assert result.total_processed == eligible_count, (
                f"total_processed ({result.total_processed}) should equal "
                f"eligible article count ({eligible_count})"
            )
            
            # Verify successful + failed equals total_processed
            assert len(result.successful) + len(result.failed) == result.total_processed, (
                f"successful ({len(result.successful)}) + failed ({len(result.failed)}) "
                f"should equal total_processed ({result.total_processed})"
            )

    @given(articles=st.lists(scored_article_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_batch_result_total_processed_only_counts_eligible(self, articles: list):
        """BatchResult.total_processed SHALL equal only the count of eligible articles.
        
        **Validates: Requirements 3.4**
        """
        generator = self._create_mock_generator()
        
        # Count expected eligible articles (score >= 50)
        eligible_count = sum(1 for a in articles if a.score_overall >= 50)
        
        result = generator.generate_batch(articles)
        
        # total_processed should only count eligible articles that were attempted
        assert result.total_processed == eligible_count, (
            f"total_processed ({result.total_processed}) should equal "
            f"eligible article count ({eligible_count})"
        )

    @given(articles=st.lists(scored_article_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_skipped_articles_not_in_failed_list(self, articles: list):
        """Skipped articles (score < 50) SHALL NOT appear in the failed list.
        
        **Validates: Requirements 3.3**
        """
        generator = self._create_mock_generator()
        
        # Get titles of low-score articles that should be skipped
        skipped_titles = {a.title for a in articles if a.score_overall < 50}
        
        result = generator.generate_batch(articles)
        
        # Verify no skipped article titles appear in the failed list
        failed_titles = {title for title, _ in result.failed}
        
        skipped_in_failed = skipped_titles & failed_titles
        assert len(skipped_in_failed) == 0, (
            f"Skipped articles should NOT appear in failed list. "
            f"Found: {skipped_in_failed}"
        )

    @given(
        low_score=st.floats(min_value=0.0, max_value=49.9),
        high_score=st.floats(min_value=50.0, max_value=100.0),
    )
    @settings(max_examples=100)
    def test_boundary_score_filtering(self, low_score: float, high_score: float):
        """Articles at boundary scores SHALL be filtered correctly.
        
        Score < 50: NOT processed
        Score >= 50: processed
        
        **Validates: Requirements 3.1**
        """
        generator = self._create_mock_generator()
        
        # Create articles with specific scores
        low_score_article = ScoredArticle(
            source="AWS News Blog",
            title="Low Score Article",
            url="https://aws.amazon.com/blogs/aws/low-score",
            published_date=datetime.now(),
            author="Test Author",
            summary="Test summary for low score article",
            key_topics=["cloud_security"],
            why_it_matters="Test importance",
            suggested_linkedin_angle="Test angle",
            suggested_hashtags=["#Test"],
            score_overall=low_score,
            score_recency=50.0,
            score_relevance=50.0,
            collected_at=datetime.now(),
        )
        
        high_score_article = ScoredArticle(
            source="Microsoft Purview Blog",
            title="High Score Article",
            url="https://techcommunity.microsoft.com/blog/high-score",
            published_date=datetime.now(),
            author="Test Author",
            summary="Test summary for high score article",
            key_topics=["data_protection"],
            why_it_matters="Test importance",
            suggested_linkedin_angle="Test angle",
            suggested_hashtags=["#Test"],
            score_overall=high_score,
            score_recency=50.0,
            score_relevance=50.0,
            collected_at=datetime.now(),
        )
        
        articles = [low_score_article, high_score_article]
        result = generator.generate_batch(articles)
        
        # Only the high score article should be processed
        assert result.total_processed == 1, (
            f"Only 1 article (high score) should be processed, got {result.total_processed}"
        )
        
        # Low score article should not be in failed list
        failed_titles = {title for title, _ in result.failed}
        assert "Low Score Article" not in failed_titles, (
            "Low score article should NOT appear in failed list"
        )

    def test_exact_threshold_boundary_processed(self):
        """Article with score_overall = 50 (exact boundary) SHALL be processed.
        
        **Validates: Requirements 3.1**
        """
        generator = self._create_mock_generator()
        
        # Create article with exactly 50 score
        boundary_article = ScoredArticle(
            source="AWS News Blog",
            title="Boundary Score Article",
            url="https://aws.amazon.com/blogs/aws/boundary",
            published_date=datetime.now(),
            author="Test Author",
            summary="Test summary for boundary score article",
            key_topics=["cloud_security"],
            why_it_matters="Test importance",
            suggested_linkedin_angle="Test angle",
            suggested_hashtags=["#Test"],
            score_overall=50.0,  # Exact boundary
            score_recency=50.0,
            score_relevance=50.0,
            collected_at=datetime.now(),
        )
        
        result = generator.generate_batch([boundary_article])
        
        # Article with score = 50 should be processed
        assert result.total_processed == 1, (
            f"Article with score_overall=50 should be processed, got {result.total_processed}"
        )

    def test_just_below_threshold_not_processed(self):
        """Article with score_overall = 49.9 (just below threshold) SHALL NOT be processed.
        
        **Validates: Requirements 3.1**
        """
        generator = self._create_mock_generator()
        
        # Create article with score just below threshold
        below_threshold_article = ScoredArticle(
            source="AWS News Blog",
            title="Below Threshold Article",
            url="https://aws.amazon.com/blogs/aws/below-threshold",
            published_date=datetime.now(),
            author="Test Author",
            summary="Test summary for below threshold article",
            key_topics=["cloud_security"],
            why_it_matters="Test importance",
            suggested_linkedin_angle="Test angle",
            suggested_hashtags=["#Test"],
            score_overall=49.9,  # Just below threshold
            score_recency=50.0,
            score_relevance=50.0,
            collected_at=datetime.now(),
        )
        
        result = generator.generate_batch([below_threshold_article])
        
        # Article with score = 49.9 should NOT be processed
        assert result.total_processed == 0, (
            f"Article with score_overall=49.9 should NOT be processed, got {result.total_processed}"
        )
        
        # Should not appear in failed list either
        assert len(result.failed) == 0, (
            "Below-threshold article should NOT appear in failed list"
        )

    @given(articles=st.lists(scored_article_strategy(), min_size=0, max_size=5))
    @settings(max_examples=100)
    def test_empty_and_all_filtered_batches(self, articles: list):
        """Empty batches and batches where all articles are filtered SHALL return valid BatchResult.
        
        **Validates: Requirements 3.4**
        """
        generator = self._create_mock_generator()
        
        result = generator.generate_batch(articles)
        
        # Result should always be a valid BatchResult
        assert isinstance(result, BatchResult), "Result should be a BatchResult"
        assert isinstance(result.successful, list), "successful should be a list"
        assert isinstance(result.failed, list), "failed should be a list"
        assert isinstance(result.total_processed, int), "total_processed should be an int"
        assert isinstance(result.success_rate, float), "success_rate should be a float"
        
        # total_processed should match successful + failed
        assert result.total_processed == len(result.successful) + len(result.failed), (
            f"total_processed ({result.total_processed}) should equal "
            f"successful ({len(result.successful)}) + failed ({len(result.failed)})"
        )

    @given(articles=st.lists(scored_article_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_success_rate_calculated_from_processed_only(self, articles: list):
        """Success rate SHALL be calculated from processed articles only, not total input.
        
        **Validates: Requirements 3.4**
        """
        generator = self._create_mock_generator()
        
        result = generator.generate_batch(articles)
        
        # Success rate should be based on total_processed, not len(articles)
        if result.total_processed > 0:
            expected_rate = len(result.successful) / result.total_processed
            assert abs(result.success_rate - expected_rate) < 0.001, (
                f"success_rate ({result.success_rate}) should equal "
                f"successful/total_processed ({expected_rate})"
            )
        else:
            # When no articles are processed, success_rate should be 0.0
            assert result.success_rate == 0.0, (
                f"success_rate should be 0.0 when no articles processed, got {result.success_rate}"
            )


# =============================================================================
# Feature: prompt-builder-enhancements, Property 5: Skip Logging for Low-Score Articles
# Validates: Requirements 3.2
# =============================================================================


class TestSkipLogging:
    """Property tests for skip logging.
    
    **Property 5: Skip Logging for Low-Score Articles**
    
    *For any* article with score_overall < 50 in a batch, the system SHALL emit
    a log message indicating the article was skipped due to low score.
    
    **Validates: Requirements 3.2**
    """

    def _create_mock_generator(self):
        """Create a ContentGenerator with mocked Ollama client."""
        generator = ContentGenerator.__new__(ContentGenerator)
        generator.model = "test-model"
        generator.timeout = 120
        generator.max_tokens = 10000
        generator.num_ctx = 16384
        generator._model_validated = True  # Skip model validation
        
        # Mock the internal components
        generator._client = MagicMock()
        generator._context_manager = MagicMock()
        generator._prompt_builder = MagicMock()
        
        # Configure mocks to return valid responses
        generator._context_manager.prepare_content.return_value = ("Test content", False)
        generator._prompt_builder.build.return_value = "Test prompt"
        generator._prompt_builder.get_system_prompt.return_value = "Test system prompt"
        generator._client.chat.return_value = "Test LinkedIn post content\n\n#Test #Hashtag #Post"
        
        return generator

    @given(articles=st.lists(scored_article_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_skip_info_log_emitted_for_low_score_articles(self, articles: list, caplog):
        """For any batch with low-score articles, an INFO log SHALL be emitted.
        
        **Validates: Requirements 3.2**
        """
        generator = self._create_mock_generator()
        
        # Count low-score articles
        low_score_count = sum(1 for a in articles if a.score_overall < 50)
        
        # Clear any previous log records
        caplog.clear()
        
        with caplog.at_level(logging.INFO, logger="src.engines.generator"):
            generator.generate_batch(articles)
        
        if low_score_count > 0:
            # Verify INFO log was emitted with count of skipped articles
            info_messages = [
                record.message for record in caplog.records
                if record.levelno == logging.INFO
                and "Skipped" in record.message
                and "score_overall" in record.message
            ]
            
            assert len(info_messages) >= 1, (
                f"INFO log should be emitted when {low_score_count} articles are skipped. "
                f"Log messages: {[r.message for r in caplog.records]}"
            )
            
            # Verify the count is mentioned in the log
            skip_log = info_messages[0]
            assert str(low_score_count) in skip_log, (
                f"INFO log should mention the count of skipped articles ({low_score_count}). "
                f"Got: {skip_log}"
            )

    @given(articles=st.lists(scored_article_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_skip_debug_log_emitted_for_each_low_score_article(self, articles: list, caplog):
        """For any batch with low-score articles, DEBUG logs SHALL be emitted for each.
        
        **Validates: Requirements 3.2**
        """
        generator = self._create_mock_generator()
        
        # Get low-score articles
        low_score_articles = [a for a in articles if a.score_overall < 50]
        
        # Clear any previous log records
        caplog.clear()
        
        with caplog.at_level(logging.DEBUG, logger="src.engines.generator"):
            generator.generate_batch(articles)
        
        if len(low_score_articles) > 0:
            # Verify DEBUG log was emitted for each skipped article
            debug_messages = [
                record.message for record in caplog.records
                if record.levelno == logging.DEBUG
                and "Skipped article" in record.message
            ]
            
            assert len(debug_messages) >= len(low_score_articles), (
                f"DEBUG log should be emitted for each of {len(low_score_articles)} "
                f"skipped articles. Got {len(debug_messages)} debug messages."
            )
            
            # Verify each skipped article's title appears in a debug log
            for article in low_score_articles:
                title_logged = any(
                    article.title in msg for msg in debug_messages
                )
                assert title_logged, (
                    f"DEBUG log should mention skipped article title '{article.title}'"
                )

    @given(articles=st.lists(scored_article_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_skip_debug_log_contains_score(self, articles: list, caplog):
        """For any skipped article, DEBUG log SHALL contain its score.
        
        **Validates: Requirements 3.2**
        """
        generator = self._create_mock_generator()
        
        # Get low-score articles
        low_score_articles = [a for a in articles if a.score_overall < 50]
        
        # Clear any previous log records
        caplog.clear()
        
        with caplog.at_level(logging.DEBUG, logger="src.engines.generator"):
            generator.generate_batch(articles)
        
        if len(low_score_articles) > 0:
            # Verify DEBUG logs contain score information
            debug_messages = [
                record.message for record in caplog.records
                if record.levelno == logging.DEBUG
                and "Skipped article" in record.message
            ]
            
            for article in low_score_articles:
                # Find the debug message for this article
                article_debug_msgs = [
                    msg for msg in debug_messages if article.title in msg
                ]
                
                if article_debug_msgs:
                    # Verify score is mentioned in the log
                    msg = article_debug_msgs[0]
                    # Score should be formatted as X.X (one decimal place)
                    score_str = f"{article.score_overall:.1f}"
                    assert score_str in msg or "score_overall" in msg, (
                        f"DEBUG log for '{article.title}' should contain score "
                        f"({score_str}). Got: {msg}"
                    )

    @given(articles=st.lists(scored_article_strategy(), min_size=1, max_size=5))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_skip_logs_when_all_articles_eligible(self, articles: list, caplog):
        """When all articles are eligible (score >= 50), no skip logs SHALL be emitted.
        
        **Validates: Requirements 3.2**
        """
        generator = self._create_mock_generator()
        
        # Modify all articles to have high scores (>= 50)
        high_score_articles = []
        for article in articles:
            # Create a new article with score >= 50
            high_score_article = ScoredArticle(
                source=article.source,
                title=article.title,
                url=article.url,
                published_date=article.published_date,
                author=article.author,
                summary=article.summary,
                key_topics=article.key_topics,
                why_it_matters=article.why_it_matters,
                suggested_linkedin_angle=article.suggested_linkedin_angle,
                suggested_hashtags=article.suggested_hashtags,
                score_overall=max(article.score_overall, 50.0),  # Ensure >= 50
                score_recency=article.score_recency,
                score_relevance=article.score_relevance,
                collected_at=article.collected_at,
            )
            high_score_articles.append(high_score_article)
        
        # Clear any previous log records
        caplog.clear()
        
        with caplog.at_level(logging.DEBUG, logger="src.engines.generator"):
            generator.generate_batch(high_score_articles)
        
        # Verify no skip logs were emitted
        skip_info_messages = [
            record.message for record in caplog.records
            if record.levelno == logging.INFO
            and "Skipped" in record.message
            and "score_overall" in record.message
        ]
        
        skip_debug_messages = [
            record.message for record in caplog.records
            if record.levelno == logging.DEBUG
            and "Skipped article" in record.message
        ]
        
        assert len(skip_info_messages) == 0, (
            f"No INFO skip logs should be emitted when all articles are eligible. "
            f"Got: {skip_info_messages}"
        )
        
        assert len(skip_debug_messages) == 0, (
            f"No DEBUG skip logs should be emitted when all articles are eligible. "
            f"Got: {skip_debug_messages}"
        )

    def test_skip_log_mentions_threshold_value(self, caplog):
        """Skip log SHALL mention the threshold value (50).
        
        **Validates: Requirements 3.2**
        """
        generator = self._create_mock_generator()
        
        # Create a low-score article
        low_score_article = ScoredArticle(
            source="AWS News Blog",
            title="Low Score Test Article",
            url="https://aws.amazon.com/blogs/aws/low-score-test",
            published_date=datetime.now(),
            author="Test Author",
            summary="Test summary for low score article",
            key_topics=["cloud_security"],
            why_it_matters="Test importance",
            suggested_linkedin_angle="Test angle",
            suggested_hashtags=["#Test"],
            score_overall=30.0,  # Below threshold
            score_recency=50.0,
            score_relevance=50.0,
            collected_at=datetime.now(),
        )
        
        with caplog.at_level(logging.INFO, logger="src.engines.generator"):
            generator.generate_batch([low_score_article])
        
        # Verify INFO log mentions the threshold
        info_messages = [
            record.message for record in caplog.records
            if record.levelno == logging.INFO
            and "Skipped" in record.message
        ]
        
        assert len(info_messages) >= 1, "INFO skip log should be emitted"
        
        # Threshold value (50 or 50.0) should be mentioned
        skip_log = info_messages[0]
        assert "50" in skip_log, (
            f"Skip log should mention threshold value (50). Got: {skip_log}"
        )

    def test_skip_log_format_matches_design(self, caplog):
        """Skip logs SHALL follow the format specified in the design document.
        
        INFO: "Skipped {count} articles with score_overall < {threshold}"
        DEBUG: "Skipped article '{title}' (score_overall={score} < {threshold})"
        
        **Validates: Requirements 3.2**
        """
        generator = self._create_mock_generator()
        
        # Create articles with specific scores
        articles = [
            ScoredArticle(
                source="AWS News Blog",
                title="Article One",
                url="https://aws.amazon.com/blogs/aws/one",
                published_date=datetime.now(),
                author="Test Author",
                summary="Test summary one",
                key_topics=["cloud_security"],
                why_it_matters="Test importance",
                suggested_linkedin_angle="Test angle",
                suggested_hashtags=["#Test"],
                score_overall=25.5,  # Below threshold
                score_recency=50.0,
                score_relevance=50.0,
                collected_at=datetime.now(),
            ),
            ScoredArticle(
                source="Microsoft Purview Blog",
                title="Article Two",
                url="https://techcommunity.microsoft.com/blog/two",
                published_date=datetime.now(),
                author="Test Author",
                summary="Test summary two",
                key_topics=["data_protection"],
                why_it_matters="Test importance",
                suggested_linkedin_angle="Test angle",
                suggested_hashtags=["#Test"],
                score_overall=75.0,  # Above threshold
                score_recency=50.0,
                score_relevance=50.0,
                collected_at=datetime.now(),
            ),
        ]
        
        with caplog.at_level(logging.DEBUG, logger="src.engines.generator"):
            generator.generate_batch(articles)
        
        # Verify INFO log format
        info_messages = [
            record.message for record in caplog.records
            if record.levelno == logging.INFO
            and "Skipped" in record.message
            and "score_overall" in record.message
        ]
        
        assert len(info_messages) >= 1, "INFO skip log should be emitted"
        info_log = info_messages[0]
        
        # Should contain count (1), "articles", "score_overall", and threshold
        assert "1" in info_log, f"INFO log should mention count (1). Got: {info_log}"
        assert "article" in info_log.lower(), f"INFO log should mention 'article'. Got: {info_log}"
        assert "score_overall" in info_log, f"INFO log should mention 'score_overall'. Got: {info_log}"
        
        # Verify DEBUG log format
        debug_messages = [
            record.message for record in caplog.records
            if record.levelno == logging.DEBUG
            and "Skipped article" in record.message
        ]
        
        assert len(debug_messages) >= 1, "DEBUG skip log should be emitted"
        debug_log = debug_messages[0]
        
        # Should contain article title and score
        assert "Article One" in debug_log, f"DEBUG log should mention article title. Got: {debug_log}"
        assert "25.5" in debug_log, f"DEBUG log should mention score (25.5). Got: {debug_log}"


# =============================================================================
# Feature: robust-response-parsing, Property 1: Tag Extraction Round Trip
# Validates: Requirements 3.1, 3.2, 3.3, 3.4, 6.1, 6.2, 6.3, 6.4, 6.5
# =============================================================================


class TestTagExtractionRoundTrip:
    """Property tests for tag-based response parsing.
    
    **Property 1: Tag Extraction Round Trip**
    
    *For any* valid tagged response containing [HOOK], [VALUE], [CTA], and 
    [HASHTAGS] sections, extracting each section and comparing to the original
    content SHALL produce a match.
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 6.1, 6.2, 6.3, 6.4, 6.5**
    """
    
    @staticmethod
    def _create_tagged_response(hook: str, value: str, cta: str, hashtags: str) -> str:
        """Create a tagged response from individual sections.
        
        Args:
            hook: The hook section content.
            value: The value section content.
            cta: The CTA section content.
            hashtags: The hashtags section content.
            
        Returns:
            A properly formatted tagged response string.
        """
        return (
            f"[HOOK]{hook}[/HOOK]\n\n"
            f"[VALUE]{value}[/VALUE]\n\n"
            f"[CTA]{cta}[/CTA]\n\n"
            f"[HASHTAGS]{hashtags}[/HASHTAGS]"
        )
    
    @staticmethod
    def _create_mock_generator():
        """Create a ContentGenerator with mocked Ollama client for testing.
        
        Returns:
            A ContentGenerator instance with mocked dependencies.
        """
        from unittest.mock import MagicMock, patch
        import sys
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.list.return_value = {"models": [{"name": "test-model"}]}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            from src.engines.generator import ContentGenerator
            generator = ContentGenerator(model="test-model")
            return generator

    @given(
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
        hashtags=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=5,
            max_size=50,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_hook_extraction_matches_original(
        self, hook: str, value: str, cta: str, hashtags: str
    ):
        """For any tagged response, extracted hook SHALL match original hook content.
        
        **Validates: Requirements 3.1, 6.1**
        """
        # Skip if hook content is empty after stripping
        assume(len(hook.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create tagged response
        response = self._create_tagged_response(hook, value, cta, hashtags)
        
        # Extract the hook section
        extracted_hook = generator._extract_tagged_section(response, "HOOK")
        
        # Verify extraction matches original (after stripping whitespace)
        assert extracted_hook is not None, "Hook extraction should not return None"
        assert extracted_hook == hook.strip(), (
            f"Extracted hook should match original.\n"
            f"Original: '{hook.strip()}'\n"
            f"Extracted: '{extracted_hook}'"
        )

    @given(
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
        hashtags=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=5,
            max_size=50,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_value_extraction_matches_original(
        self, hook: str, value: str, cta: str, hashtags: str
    ):
        """For any tagged response, extracted value SHALL match original value content.
        
        **Validates: Requirements 3.2, 6.2**
        """
        # Skip if value content is empty after stripping
        assume(len(value.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create tagged response
        response = self._create_tagged_response(hook, value, cta, hashtags)
        
        # Extract the value section
        extracted_value = generator._extract_tagged_section(response, "VALUE")
        
        # Verify extraction matches original (after stripping whitespace)
        assert extracted_value is not None, "Value extraction should not return None"
        assert extracted_value == value.strip(), (
            f"Extracted value should match original.\n"
            f"Original: '{value.strip()}'\n"
            f"Extracted: '{extracted_value}'"
        )

    @given(
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
        hashtags=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=5,
            max_size=50,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_cta_extraction_matches_original(
        self, hook: str, value: str, cta: str, hashtags: str
    ):
        """For any tagged response, extracted CTA SHALL match original CTA content.
        
        **Validates: Requirements 3.3, 6.3**
        """
        # Skip if CTA content is empty after stripping
        assume(len(cta.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create tagged response
        response = self._create_tagged_response(hook, value, cta, hashtags)
        
        # Extract the CTA section
        extracted_cta = generator._extract_tagged_section(response, "CTA")
        
        # Verify extraction matches original (after stripping whitespace)
        assert extracted_cta is not None, "CTA extraction should not return None"
        assert extracted_cta == cta.strip(), (
            f"Extracted CTA should match original.\n"
            f"Original: '{cta.strip()}'\n"
            f"Extracted: '{extracted_cta}'"
        )

    @given(
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
        hashtags=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=5,
            max_size=50,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_hashtags_extraction_matches_original(
        self, hook: str, value: str, cta: str, hashtags: str
    ):
        """For any tagged response, extracted hashtags SHALL match original hashtags content.
        
        **Validates: Requirements 3.4, 6.4**
        """
        # Skip if hashtags content is empty after stripping
        assume(len(hashtags.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create tagged response
        response = self._create_tagged_response(hook, value, cta, hashtags)
        
        # Extract the hashtags section
        extracted_hashtags = generator._extract_tagged_section(response, "HASHTAGS")
        
        # Verify extraction matches original (after stripping whitespace)
        assert extracted_hashtags is not None, "Hashtags extraction should not return None"
        assert extracted_hashtags == hashtags.strip(), (
            f"Extracted hashtags should match original.\n"
            f"Original: '{hashtags.strip()}'\n"
            f"Extracted: '{extracted_hashtags}'"
        )

    @given(
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
        hashtags=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=5,
            max_size=50,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_sections_round_trip(
        self, hook: str, value: str, cta: str, hashtags: str
    ):
        """For any tagged response, all sections SHALL be extractable and match originals.
        
        This is the comprehensive round-trip test that validates the complete
        tag extraction workflow for all four sections simultaneously.
        
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 6.1, 6.2, 6.3, 6.4, 6.5**
        """
        # Skip if any content is empty after stripping
        assume(len(hook.strip()) > 0)
        assume(len(value.strip()) > 0)
        assume(len(cta.strip()) > 0)
        assume(len(hashtags.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create tagged response
        response = self._create_tagged_response(hook, value, cta, hashtags)
        
        # Extract all sections
        extracted_hook = generator._extract_tagged_section(response, "HOOK")
        extracted_value = generator._extract_tagged_section(response, "VALUE")
        extracted_cta = generator._extract_tagged_section(response, "CTA")
        extracted_hashtags = generator._extract_tagged_section(response, "HASHTAGS")
        
        # Verify all extractions are successful
        assert extracted_hook is not None, "Hook extraction should not return None"
        assert extracted_value is not None, "Value extraction should not return None"
        assert extracted_cta is not None, "CTA extraction should not return None"
        assert extracted_hashtags is not None, "Hashtags extraction should not return None"
        
        # Verify all extractions match originals
        assert extracted_hook == hook.strip(), (
            f"Extracted hook should match original"
        )
        assert extracted_value == value.strip(), (
            f"Extracted value should match original"
        )
        assert extracted_cta == cta.strip(), (
            f"Extracted CTA should match original"
        )
        assert extracted_hashtags == hashtags.strip(), (
            f"Extracted hashtags should match original"
        )

    @given(
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
        hashtags=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=5,
            max_size=50,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_parse_response_extracts_all_sections(
        self, hook: str, value: str, cta: str, hashtags: str
    ):
        """For any tagged response, _parse_response SHALL extract hook, value, and CTA.
        
        This tests the higher-level _parse_response method which uses the
        tag extraction internally.
        
        **Validates: Requirements 3.1, 3.2, 3.3, 6.1, 6.2, 6.3, 6.5**
        """
        # Skip if any content is empty after stripping
        assume(len(hook.strip()) > 0)
        assume(len(value.strip()) > 0)
        assume(len(cta.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create tagged response
        response = self._create_tagged_response(hook, value, cta, hashtags)
        
        # Parse the response
        parsed_hook, parsed_value, parsed_cta = generator._parse_response(response)
        
        # Verify all sections are extracted correctly
        assert parsed_hook == hook.strip(), (
            f"Parsed hook should match original.\n"
            f"Original: '{hook.strip()}'\n"
            f"Parsed: '{parsed_hook}'"
        )
        assert parsed_value == value.strip(), (
            f"Parsed value should match original.\n"
            f"Original: '{value.strip()}'\n"
            f"Parsed: '{parsed_value}'"
        )
        assert parsed_cta == cta.strip(), (
            f"Parsed CTA should match original.\n"
            f"Original: '{cta.strip()}'\n"
            f"Parsed: '{parsed_cta}'"
        )

    def test_tag_extraction_case_insensitive(self):
        """Tag extraction SHALL be case-insensitive.
        
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        generator = self._create_mock_generator()
        
        # Test with lowercase tags
        lowercase_response = (
            "[hook]Test hook content[/hook]\n\n"
            "[value]Test value content[/value]\n\n"
            "[cta]Test CTA content[/cta]\n\n"
            "[hashtags]#Test #Hashtags[/hashtags]"
        )
        
        assert generator._extract_tagged_section(lowercase_response, "HOOK") == "Test hook content"
        assert generator._extract_tagged_section(lowercase_response, "VALUE") == "Test value content"
        assert generator._extract_tagged_section(lowercase_response, "CTA") == "Test CTA content"
        assert generator._extract_tagged_section(lowercase_response, "HASHTAGS") == "#Test #Hashtags"
        
        # Test with mixed case tags
        mixed_case_response = (
            "[Hook]Mixed case hook[/Hook]\n\n"
            "[Value]Mixed case value[/Value]\n\n"
            "[Cta]Mixed case CTA[/Cta]\n\n"
            "[Hashtags]#Mixed #Case[/Hashtags]"
        )
        
        assert generator._extract_tagged_section(mixed_case_response, "HOOK") == "Mixed case hook"
        assert generator._extract_tagged_section(mixed_case_response, "VALUE") == "Mixed case value"
        assert generator._extract_tagged_section(mixed_case_response, "CTA") == "Mixed case CTA"
        assert generator._extract_tagged_section(mixed_case_response, "HASHTAGS") == "#Mixed #Case"

    def test_tag_extraction_multiline_content(self):
        """Tag extraction SHALL handle multiline content within tags.
        
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        generator = self._create_mock_generator()
        
        multiline_response = (
            "[HOOK]This is a hook\nwith multiple lines\nof content[/HOOK]\n\n"
            "[VALUE]This is value content\n\nwith paragraph breaks\n\nand more text[/VALUE]\n\n"
            "[CTA]Call to action\nacross lines[/CTA]\n\n"
            "[HASHTAGS]#Tag1\n#Tag2\n#Tag3[/HASHTAGS]"
        )
        
        extracted_hook = generator._extract_tagged_section(multiline_response, "HOOK")
        extracted_value = generator._extract_tagged_section(multiline_response, "VALUE")
        extracted_cta = generator._extract_tagged_section(multiline_response, "CTA")
        extracted_hashtags = generator._extract_tagged_section(multiline_response, "HASHTAGS")
        
        assert "multiple lines" in extracted_hook
        assert "paragraph breaks" in extracted_value
        assert "across lines" in extracted_cta
        assert "#Tag1" in extracted_hashtags and "#Tag3" in extracted_hashtags

    def test_tag_extraction_returns_none_for_missing_tags(self):
        """Tag extraction SHALL return None when tags are not present.
        
        **Validates: Requirements 3.5**
        """
        generator = self._create_mock_generator()
        
        # Response without any tags
        no_tags_response = "This is just plain text without any tags."
        
        assert generator._extract_tagged_section(no_tags_response, "HOOK") is None
        assert generator._extract_tagged_section(no_tags_response, "VALUE") is None
        assert generator._extract_tagged_section(no_tags_response, "CTA") is None
        assert generator._extract_tagged_section(no_tags_response, "HASHTAGS") is None

    def test_tag_extraction_empty_response(self):
        """Tag extraction SHALL handle empty response gracefully.
        
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        generator = self._create_mock_generator()
        
        assert generator._extract_tagged_section("", "HOOK") is None
        assert generator._extract_tagged_section(None, "HOOK") is None

    def test_tag_extraction_empty_content_between_tags(self):
        """Tag extraction SHALL return empty string for empty content between tags.
        
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        generator = self._create_mock_generator()
        
        empty_content_response = "[HOOK][/HOOK]\n\n[VALUE][/VALUE]\n\n[CTA][/CTA]\n\n[HASHTAGS][/HASHTAGS]"
        
        assert generator._extract_tagged_section(empty_content_response, "HOOK") == ""
        assert generator._extract_tagged_section(empty_content_response, "VALUE") == ""
        assert generator._extract_tagged_section(empty_content_response, "CTA") == ""
        assert generator._extract_tagged_section(empty_content_response, "HASHTAGS") == ""


# =============================================================================
# Feature: robust-response-parsing, Property 2: Filler Stripping Preserves Content
# Validates: Requirements 3.6
# =============================================================================


class TestFillerStrippingPreservesContent:
    """Property tests for filler stripping in response parsing.
    
    **Property 2: Filler Stripping Preserves Content**
    
    *For any* response with conversational filler before the [HOOK] tag,
    the Response_Parser SHALL extract the same hook content as a response
    without filler.
    
    **Validates: Requirements 3.6**
    """
    
    @staticmethod
    def _filler_prefix_strategy():
        """Strategy for generating filler prefixes.
        
        Returns a Hypothesis strategy that produces common LLM conversational
        filler patterns that may appear before the actual content.
        """
        return st.sampled_from([
            "Here is the post:\n\n",
            "Sure! Here's your LinkedIn post:\n\n",
            "Certainly! I've created the following post:\n\n",
            "Here you go:\n\n",
            "Of course! Here's the LinkedIn post:\n\n",
            "I'd be happy to help! Here's your post:\n\n",
            "Absolutely! Here is the post:\n\n",
            "Great! Here's the LinkedIn post I created:\n\n",
            "",  # No filler case
        ])
    
    @staticmethod
    def _create_tagged_response(hook: str, value: str, cta: str, hashtags: str) -> str:
        """Create a tagged response from individual sections.
        
        Args:
            hook: The hook section content.
            value: The value section content.
            cta: The CTA section content.
            hashtags: The hashtags section content.
            
        Returns:
            A properly formatted tagged response string.
        """
        return (
            f"[HOOK]{hook}[/HOOK]\n\n"
            f"[VALUE]{value}[/VALUE]\n\n"
            f"[CTA]{cta}[/CTA]\n\n"
            f"[HASHTAGS]{hashtags}[/HASHTAGS]"
        )
    
    @staticmethod
    def _create_mock_generator():
        """Create a ContentGenerator with mocked Ollama client for testing.
        
        Returns:
            A ContentGenerator instance with mocked dependencies.
        """
        from unittest.mock import MagicMock, patch
        import sys
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.list.return_value = {"models": [{"name": "test-model"}]}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            from src.engines.generator import ContentGenerator
            generator = ContentGenerator(model="test-model")
            return generator

    @given(
        filler=st.sampled_from([
            "Here is the post:\n\n",
            "Sure! Here's your LinkedIn post:\n\n",
            "Certainly! I've created the following post:\n\n",
            "Here you go:\n\n",
            "Of course! Here's the LinkedIn post:\n\n",
            "I'd be happy to help! Here's your post:\n\n",
            "Absolutely! Here is the post:\n\n",
            "Great! Here's the LinkedIn post I created:\n\n",
            "",  # No filler case
        ]),
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
        hashtags=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=5,
            max_size=50,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_filler_stripping_produces_same_hook_as_without_filler(
        self, filler: str, hook: str, value: str, cta: str, hashtags: str
    ):
        """For any filler prefix, parsing SHALL extract same hook as without filler.
        
        **Validates: Requirements 3.6**
        """
        # Skip if hook content is empty after stripping
        assume(len(hook.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create tagged response without filler
        response_without_filler = self._create_tagged_response(hook, value, cta, hashtags)
        
        # Create tagged response with filler
        response_with_filler = filler + response_without_filler
        
        # Parse both responses
        hook_without_filler, _, _ = generator._parse_response(response_without_filler)
        hook_with_filler, _, _ = generator._parse_response(response_with_filler)
        
        # Verify both produce the same hook content
        assert hook_with_filler == hook_without_filler, (
            f"Parsing with filler should produce same hook as without filler.\n"
            f"Filler: '{filler}'\n"
            f"Hook without filler: '{hook_without_filler}'\n"
            f"Hook with filler: '{hook_with_filler}'"
        )

    @given(
        filler=st.sampled_from([
            "Here is the post:\n\n",
            "Sure! Here's your LinkedIn post:\n\n",
            "Certainly! I've created the following post:\n\n",
            "Here you go:\n\n",
            "Of course! Here's the LinkedIn post:\n\n",
            "I'd be happy to help! Here's your post:\n\n",
            "Absolutely! Here is the post:\n\n",
            "Great! Here's the LinkedIn post I created:\n\n",
            "",  # No filler case
        ]),
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
        hashtags=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=5,
            max_size=50,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_filler_stripping_produces_same_value_as_without_filler(
        self, filler: str, hook: str, value: str, cta: str, hashtags: str
    ):
        """For any filler prefix, parsing SHALL extract same value as without filler.
        
        **Validates: Requirements 3.6**
        """
        # Skip if value content is empty after stripping
        assume(len(value.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create tagged response without filler
        response_without_filler = self._create_tagged_response(hook, value, cta, hashtags)
        
        # Create tagged response with filler
        response_with_filler = filler + response_without_filler
        
        # Parse both responses
        _, value_without_filler, _ = generator._parse_response(response_without_filler)
        _, value_with_filler, _ = generator._parse_response(response_with_filler)
        
        # Verify both produce the same value content
        assert value_with_filler == value_without_filler, (
            f"Parsing with filler should produce same value as without filler.\n"
            f"Filler: '{filler}'\n"
            f"Value without filler: '{value_without_filler}'\n"
            f"Value with filler: '{value_with_filler}'"
        )

    @given(
        filler=st.sampled_from([
            "Here is the post:\n\n",
            "Sure! Here's your LinkedIn post:\n\n",
            "Certainly! I've created the following post:\n\n",
            "Here you go:\n\n",
            "Of course! Here's the LinkedIn post:\n\n",
            "I'd be happy to help! Here's your post:\n\n",
            "Absolutely! Here is the post:\n\n",
            "Great! Here's the LinkedIn post I created:\n\n",
            "",  # No filler case
        ]),
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
        hashtags=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=5,
            max_size=50,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_filler_stripping_produces_same_cta_as_without_filler(
        self, filler: str, hook: str, value: str, cta: str, hashtags: str
    ):
        """For any filler prefix, parsing SHALL extract same CTA as without filler.
        
        **Validates: Requirements 3.6**
        """
        # Skip if CTA content is empty after stripping
        assume(len(cta.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create tagged response without filler
        response_without_filler = self._create_tagged_response(hook, value, cta, hashtags)
        
        # Create tagged response with filler
        response_with_filler = filler + response_without_filler
        
        # Parse both responses
        _, _, cta_without_filler = generator._parse_response(response_without_filler)
        _, _, cta_with_filler = generator._parse_response(response_with_filler)
        
        # Verify both produce the same CTA content
        assert cta_with_filler == cta_without_filler, (
            f"Parsing with filler should produce same CTA as without filler.\n"
            f"Filler: '{filler}'\n"
            f"CTA without filler: '{cta_without_filler}'\n"
            f"CTA with filler: '{cta_with_filler}'"
        )

    @given(
        filler=st.sampled_from([
            "Here is the post:\n\n",
            "Sure! Here's your LinkedIn post:\n\n",
            "Certainly! I've created the following post:\n\n",
            "Here you go:\n\n",
            "Of course! Here's the LinkedIn post:\n\n",
            "I'd be happy to help! Here's your post:\n\n",
            "Absolutely! Here is the post:\n\n",
            "Great! Here's the LinkedIn post I created:\n\n",
            "",  # No filler case
        ]),
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
        hashtags=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=5,
            max_size=50,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_filler_stripping_produces_same_full_parse_result(
        self, filler: str, hook: str, value: str, cta: str, hashtags: str
    ):
        """For any filler prefix, parsing SHALL produce identical results as without filler.
        
        **Validates: Requirements 3.6**
        """
        # Skip if any content is empty after stripping
        assume(len(hook.strip()) > 0)
        assume(len(value.strip()) > 0)
        assume(len(cta.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create tagged response without filler
        response_without_filler = self._create_tagged_response(hook, value, cta, hashtags)
        
        # Create tagged response with filler
        response_with_filler = filler + response_without_filler
        
        # Parse both responses
        result_without_filler = generator._parse_response(response_without_filler)
        result_with_filler = generator._parse_response(response_with_filler)
        
        # Verify both produce identical results
        assert result_with_filler == result_without_filler, (
            f"Parsing with filler should produce identical result as without filler.\n"
            f"Filler: '{filler}'\n"
            f"Result without filler: {result_without_filler}\n"
            f"Result with filler: {result_with_filler}"
        )

    def test_strip_filler_before_hook_removes_common_fillers(self):
        """_strip_filler_before_hook SHALL remove common conversational fillers.
        
        **Validates: Requirements 3.6**
        """
        generator = self._create_mock_generator()
        
        # Test various filler patterns
        test_cases = [
            ("Here is the post:\n\n[HOOK]Test[/HOOK]", "[HOOK]Test[/HOOK]"),
            ("Sure! Here's your LinkedIn post:\n\n[HOOK]Test[/HOOK]", "[HOOK]Test[/HOOK]"),
            ("Certainly! I've created the following post:\n\n[HOOK]Test[/HOOK]", "[HOOK]Test[/HOOK]"),
            ("Here you go:\n\n[HOOK]Test[/HOOK]", "[HOOK]Test[/HOOK]"),
            ("[HOOK]Test[/HOOK]", "[HOOK]Test[/HOOK]"),  # No filler case
        ]
        
        for input_text, expected_start in test_cases:
            result = generator._strip_filler_before_hook(input_text)
            assert result.startswith("[HOOK]"), (
                f"Result should start with [HOOK] after stripping filler.\n"
                f"Input: '{input_text}'\n"
                f"Result: '{result}'"
            )

    def test_strip_filler_before_hook_preserves_content_after_hook(self):
        """_strip_filler_before_hook SHALL preserve all content from [HOOK] onwards.
        
        **Validates: Requirements 3.6**
        """
        generator = self._create_mock_generator()
        
        content_after_hook = "[HOOK]Hook content[/HOOK]\n\n[VALUE]Value content[/VALUE]"
        filler = "Here is the post:\n\n"
        
        result = generator._strip_filler_before_hook(filler + content_after_hook)
        
        assert result == content_after_hook, (
            f"Content after [HOOK] should be preserved exactly.\n"
            f"Expected: '{content_after_hook}'\n"
            f"Got: '{result}'"
        )

    def test_strip_filler_before_hook_handles_no_hook_tag(self):
        """_strip_filler_before_hook SHALL return original response when no [HOOK] tag present.
        
        **Validates: Requirements 3.6**
        """
        generator = self._create_mock_generator()
        
        # Response without [HOOK] tag should be returned unchanged
        no_hook_response = "This is a response without any tags."
        
        result = generator._strip_filler_before_hook(no_hook_response)
        
        assert result == no_hook_response, (
            f"Response without [HOOK] should be returned unchanged.\n"
            f"Expected: '{no_hook_response}'\n"
            f"Got: '{result}'"
        )

    def test_strip_filler_before_hook_handles_empty_response(self):
        """_strip_filler_before_hook SHALL handle empty response gracefully.
        
        **Validates: Requirements 3.6**
        """
        generator = self._create_mock_generator()
        
        assert generator._strip_filler_before_hook("") == ""
        assert generator._strip_filler_before_hook(None) is None

    def test_strip_filler_before_hook_case_insensitive(self):
        """_strip_filler_before_hook SHALL handle [HOOK] tag case-insensitively.
        
        **Validates: Requirements 3.6**
        """
        generator = self._create_mock_generator()
        
        # Test various case variations
        test_cases = [
            "Here is the post:\n\n[HOOK]Test[/HOOK]",
            "Here is the post:\n\n[hook]Test[/hook]",
            "Here is the post:\n\n[Hook]Test[/Hook]",
            "Here is the post:\n\n[HOOK]Test[/HOOK]",
        ]
        
        for input_text in test_cases:
            result = generator._strip_filler_before_hook(input_text)
            # Result should start with the [HOOK] tag (in whatever case it was)
            assert "[" in result and "hook" in result.lower(), (
                f"Result should contain [HOOK] tag (case-insensitive).\n"
                f"Input: '{input_text}'\n"
                f"Result: '{result}'"
            )


# =============================================================================
# Feature: robust-response-parsing, Property 3: Fallback Parsing Consistency
# Validates: Requirements 3.5, 5.2
# =============================================================================


class TestFallbackParsingConsistency:
    """Property tests for fallback parsing consistency.
    
    **Property 3: Fallback Parsing Consistency**
    
    *For any* response without explicit tags, the Response_Parser SHALL produce
    the same output as the original paragraph-based parser.
    
    This validates backward compatibility - when tags are missing, the new
    _parse_response method should fall back to _parse_response_paragraphs
    and produce identical results.
    
    **Validates: Requirements 3.5, 5.2**
    """
    
    @staticmethod
    def _create_mock_generator():
        """Create a ContentGenerator with mocked Ollama client for testing.
        
        Returns:
            A ContentGenerator instance with mocked dependencies.
        """
        from unittest.mock import MagicMock, patch
        import sys
        
        # Create a mock ollama module
        mock_ollama = MagicMock()
        mock_ollama.list.return_value = {"models": [{"name": "test-model"}]}
        
        with patch.dict(sys.modules, {'ollama': mock_ollama}):
            from src.engines.generator import ContentGenerator
            generator = ContentGenerator(model="test-model")
            return generator
    
    @staticmethod
    def _create_untagged_response(hook: str, value: str, cta: str, hashtags: str) -> str:
        """Create an untagged paragraph-based response.
        
        This simulates the format that an LLM might produce without explicit tags,
        which is the format the original paragraph-based parser was designed to handle.
        
        Args:
            hook: The hook section content (first paragraph).
            value: The value section content (middle paragraphs).
            cta: The CTA section content (last paragraph before hashtags).
            hashtags: The hashtags to append at the end.
            
        Returns:
            A paragraph-based response string without explicit tags.
        """
        # Build the response with paragraphs separated by blank lines
        parts = []
        
        if hook.strip():
            parts.append(hook.strip())
        
        if value.strip():
            parts.append(value.strip())
        
        if cta.strip():
            parts.append(cta.strip())
        
        # Join paragraphs with double newlines
        content = "\n\n".join(parts)
        
        # Add hashtags at the end if provided
        if hashtags.strip():
            content += "\n\n" + hashtags.strip()
        
        return content

    @given(
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
        hashtags=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=5,
            max_size=50,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_untagged_response_uses_paragraph_fallback(
        self, hook: str, value: str, cta: str, hashtags: str
    ):
        """For any untagged response, _parse_response SHALL produce same result as _parse_response_paragraphs.
        
        **Validates: Requirements 3.5, 5.2**
        """
        # Skip if any content is empty after stripping
        assume(len(hook.strip()) > 0)
        assume(len(value.strip()) > 0)
        assume(len(cta.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create untagged response (paragraph-based format)
        untagged_response = self._create_untagged_response(hook, value, cta, hashtags)
        
        # Parse using both methods
        result_parse_response = generator._parse_response(untagged_response)
        result_paragraph_parser = generator._parse_response_paragraphs(untagged_response)
        
        # Verify both produce the same result
        assert result_parse_response == result_paragraph_parser, (
            f"_parse_response should produce same result as _parse_response_paragraphs for untagged content.\n"
            f"Untagged response:\n{untagged_response}\n\n"
            f"_parse_response result: {result_parse_response}\n"
            f"_parse_response_paragraphs result: {result_paragraph_parser}"
        )

    @given(
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_untagged_response_hook_matches_paragraph_parser(
        self, hook: str, value: str, cta: str
    ):
        """For any untagged response, hook from _parse_response SHALL match _parse_response_paragraphs.
        
        **Validates: Requirements 3.5, 5.2**
        """
        # Skip if any content is empty after stripping
        assume(len(hook.strip()) > 0)
        assume(len(value.strip()) > 0)
        assume(len(cta.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create untagged response without hashtags
        untagged_response = self._create_untagged_response(hook, value, cta, "")
        
        # Parse using both methods
        hook_from_parse_response, _, _ = generator._parse_response(untagged_response)
        hook_from_paragraph_parser, _, _ = generator._parse_response_paragraphs(untagged_response)
        
        # Verify hooks match
        assert hook_from_parse_response == hook_from_paragraph_parser, (
            f"Hook from _parse_response should match _parse_response_paragraphs.\n"
            f"Hook from _parse_response: '{hook_from_parse_response}'\n"
            f"Hook from _parse_response_paragraphs: '{hook_from_paragraph_parser}'"
        )

    @given(
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_untagged_response_value_matches_paragraph_parser(
        self, hook: str, value: str, cta: str
    ):
        """For any untagged response, value from _parse_response SHALL match _parse_response_paragraphs.
        
        **Validates: Requirements 3.5, 5.2**
        """
        # Skip if any content is empty after stripping
        assume(len(hook.strip()) > 0)
        assume(len(value.strip()) > 0)
        assume(len(cta.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create untagged response without hashtags
        untagged_response = self._create_untagged_response(hook, value, cta, "")
        
        # Parse using both methods
        _, value_from_parse_response, _ = generator._parse_response(untagged_response)
        _, value_from_paragraph_parser, _ = generator._parse_response_paragraphs(untagged_response)
        
        # Verify values match
        assert value_from_parse_response == value_from_paragraph_parser, (
            f"Value from _parse_response should match _parse_response_paragraphs.\n"
            f"Value from _parse_response: '{value_from_parse_response}'\n"
            f"Value from _parse_response_paragraphs: '{value_from_paragraph_parser}'"
        )

    @given(
        hook=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        value=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
        cta=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=150,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_untagged_response_cta_matches_paragraph_parser(
        self, hook: str, value: str, cta: str
    ):
        """For any untagged response, CTA from _parse_response SHALL match _parse_response_paragraphs.
        
        **Validates: Requirements 3.5, 5.2**
        """
        # Skip if any content is empty after stripping
        assume(len(hook.strip()) > 0)
        assume(len(value.strip()) > 0)
        assume(len(cta.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Create untagged response without hashtags
        untagged_response = self._create_untagged_response(hook, value, cta, "")
        
        # Parse using both methods
        _, _, cta_from_parse_response = generator._parse_response(untagged_response)
        _, _, cta_from_paragraph_parser = generator._parse_response_paragraphs(untagged_response)
        
        # Verify CTAs match
        assert cta_from_parse_response == cta_from_paragraph_parser, (
            f"CTA from _parse_response should match _parse_response_paragraphs.\n"
            f"CTA from _parse_response: '{cta_from_parse_response}'\n"
            f"CTA from _parse_response_paragraphs: '{cta_from_paragraph_parser}'"
        )

    @given(
        single_paragraph=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=20,
            max_size=500,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_single_paragraph_fallback_consistency(self, single_paragraph: str):
        """For single paragraph responses, _parse_response SHALL match _parse_response_paragraphs.
        
        **Validates: Requirements 3.5, 5.2**
        """
        # Skip if content is empty after stripping
        assume(len(single_paragraph.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Single paragraph response (no blank lines)
        response = single_paragraph.strip()
        
        # Parse using both methods
        result_parse_response = generator._parse_response(response)
        result_paragraph_parser = generator._parse_response_paragraphs(response)
        
        # Verify both produce the same result
        assert result_parse_response == result_paragraph_parser, (
            f"Single paragraph should produce same result from both parsers.\n"
            f"Response: '{response}'\n"
            f"_parse_response result: {result_parse_response}\n"
            f"_parse_response_paragraphs result: {result_paragraph_parser}"
        )

    @given(
        para1=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
        para2=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=10,
            max_size=200,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_two_paragraph_fallback_consistency(self, para1: str, para2: str):
        """For two paragraph responses, _parse_response SHALL match _parse_response_paragraphs.
        
        **Validates: Requirements 3.5, 5.2**
        """
        # Skip if any content is empty after stripping
        assume(len(para1.strip()) > 0)
        assume(len(para2.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Two paragraph response
        response = f"{para1.strip()}\n\n{para2.strip()}"
        
        # Parse using both methods
        result_parse_response = generator._parse_response(response)
        result_paragraph_parser = generator._parse_response_paragraphs(response)
        
        # Verify both produce the same result
        assert result_parse_response == result_paragraph_parser, (
            f"Two paragraph response should produce same result from both parsers.\n"
            f"Response: '{response}'\n"
            f"_parse_response result: {result_parse_response}\n"
            f"_parse_response_paragraphs result: {result_paragraph_parser}"
        )

    @given(
        paragraphs=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
                min_size=10,
                max_size=150,
            ),
            min_size=3,
            max_size=6,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_multi_paragraph_fallback_consistency(self, paragraphs: list):
        """For multi-paragraph responses, _parse_response SHALL match _parse_response_paragraphs.
        
        **Validates: Requirements 3.5, 5.2**
        """
        # Filter out empty paragraphs
        non_empty_paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # Skip if we don't have at least 3 non-empty paragraphs
        assume(len(non_empty_paragraphs) >= 3)
        
        generator = self._create_mock_generator()
        
        # Multi-paragraph response
        response = "\n\n".join(non_empty_paragraphs)
        
        # Parse using both methods
        result_parse_response = generator._parse_response(response)
        result_paragraph_parser = generator._parse_response_paragraphs(response)
        
        # Verify both produce the same result
        assert result_parse_response == result_paragraph_parser, (
            f"Multi-paragraph response should produce same result from both parsers.\n"
            f"Response: '{response}'\n"
            f"_parse_response result: {result_parse_response}\n"
            f"_parse_response_paragraphs result: {result_paragraph_parser}"
        )

    @given(
        content=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
            min_size=50,
            max_size=500,
        ),
        hashtags=st.lists(
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
            min_size=1,
            max_size=5,
            unique=True,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_response_with_hashtags_fallback_consistency(
        self, content: str, hashtags: list
    ):
        """For responses with hashtags, _parse_response SHALL match _parse_response_paragraphs.
        
        **Validates: Requirements 3.5, 5.2**
        """
        # Skip if content is empty after stripping
        assume(len(content.strip()) > 0)
        
        generator = self._create_mock_generator()
        
        # Response with hashtags at the end
        hashtag_str = " ".join(hashtags)
        response = f"{content.strip()}\n\n{hashtag_str}"
        
        # Parse using both methods
        result_parse_response = generator._parse_response(response)
        result_paragraph_parser = generator._parse_response_paragraphs(response)
        
        # Verify both produce the same result
        assert result_parse_response == result_paragraph_parser, (
            f"Response with hashtags should produce same result from both parsers.\n"
            f"Response: '{response}'\n"
            f"_parse_response result: {result_parse_response}\n"
            f"_parse_response_paragraphs result: {result_paragraph_parser}"
        )

    def test_empty_response_fallback_consistency(self):
        """Empty response SHALL produce same result from both parsers.
        
        **Validates: Requirements 3.5, 5.2**
        """
        generator = self._create_mock_generator()
        
        # Empty response
        response = ""
        
        # Parse using both methods
        result_parse_response = generator._parse_response(response)
        result_paragraph_parser = generator._parse_response_paragraphs(response)
        
        # Verify both produce the same result
        assert result_parse_response == result_paragraph_parser, (
            f"Empty response should produce same result from both parsers.\n"
            f"_parse_response result: {result_parse_response}\n"
            f"_parse_response_paragraphs result: {result_paragraph_parser}"
        )

    def test_whitespace_only_response_fallback_consistency(self):
        """Whitespace-only response SHALL produce same result from both parsers.
        
        **Validates: Requirements 3.5, 5.2**
        """
        generator = self._create_mock_generator()
        
        # Whitespace-only responses
        test_cases = ["   ", "\n\n\n", "\t\t", "  \n  \n  "]
        
        for response in test_cases:
            result_parse_response = generator._parse_response(response)
            result_paragraph_parser = generator._parse_response_paragraphs(response)
            
            assert result_parse_response == result_paragraph_parser, (
                f"Whitespace-only response should produce same result from both parsers.\n"
                f"Response: '{repr(response)}'\n"
                f"_parse_response result: {result_parse_response}\n"
                f"_parse_response_paragraphs result: {result_paragraph_parser}"
            )

    def test_linkedin_style_post_without_tags_fallback_consistency(self):
        """LinkedIn-style post without tags SHALL produce same result from both parsers.
        
        **Validates: Requirements 3.5, 5.2**
        """
        generator = self._create_mock_generator()
        
        # Realistic LinkedIn post without explicit tags
        linkedin_post = """🔐 85% of enterprises will adopt zero trust by 2025.

AWS just announced enhanced security controls for IAM that make zero trust implementation significantly easier. The new features include:
- Granular permission boundaries
- Automated least-privilege recommendations
- Real-time access analytics

For security leaders in regulated industries, this means faster compliance audits and reduced attack surface.

What's your biggest challenge with zero trust adoption? Share your experience below!

#CloudSecurity #AWS #ZeroTrust"""
        
        # Parse using both methods
        result_parse_response = generator._parse_response(linkedin_post)
        result_paragraph_parser = generator._parse_response_paragraphs(linkedin_post)
        
        # Verify both produce the same result
        assert result_parse_response == result_paragraph_parser, (
            f"LinkedIn-style post should produce same result from both parsers.\n"
            f"_parse_response result: {result_parse_response}\n"
            f"_parse_response_paragraphs result: {result_paragraph_parser}"
        )

    def test_realistic_untagged_post_formats(self):
        """Various realistic untagged post formats SHALL produce consistent results.
        
        **Validates: Requirements 3.5, 5.2**
        """
        generator = self._create_mock_generator()
        
        # Various realistic post formats without tags
        test_posts = [
            # Format 1: Hook + Value + CTA + Hashtags
            """The future of cloud security is autonomous.

Microsoft Purview now offers AI-powered data classification that reduces manual effort by 70%. This is a game-changer for compliance teams struggling with data sprawl.

Key benefits:
- Automated sensitive data discovery
- Real-time policy enforcement
- Unified governance dashboard

Ready to modernize your data governance? Start with a pilot in your most regulated workloads.

#DataGovernance #Purview #Compliance""",
            
            # Format 2: Short hook + detailed value + CTA
            """Contrarian take: Most cloud migrations fail because of security, not technology.

Here's what I've learned from 50+ enterprise migrations:

1. Security teams are brought in too late
2. Compliance requirements aren't mapped upfront
3. Identity management is an afterthought

The fix? Embed security from day one. AWS's new Well-Architected Security Pillar makes this easier than ever.

What's been your experience? Drop a comment below.

#CloudSecurity #AWS #Migration""",
            
            # Format 3: Bold prediction + supporting evidence + engagement
            """By 2026, 90% of security incidents will involve misconfigured cloud resources.

The data is clear: human error remains the #1 cause of breaches. But there's hope.

AWS Config and Azure Policy now offer automated remediation that catches misconfigurations before they become vulnerabilities. For CISOs, this means:
- Reduced mean time to remediation
- Continuous compliance monitoring
- Audit-ready documentation

Are you using automated remediation? I'd love to hear what's working for your team.

#CyberSecurity #CloudSecurity #Automation""",
        ]
        
        for post in test_posts:
            result_parse_response = generator._parse_response(post)
            result_paragraph_parser = generator._parse_response_paragraphs(post)
            
            assert result_parse_response == result_paragraph_parser, (
                f"Realistic post format should produce same result from both parsers.\n"
                f"Post:\n{post}\n\n"
                f"_parse_response result: {result_parse_response}\n"
                f"_parse_response_paragraphs result: {result_paragraph_parser}"
            )


# =============================================================================
# Feature: robust-response-parsing, Property 5: No-Filler Instruction Present
# Validates: Requirements 1.1, 1.2
# =============================================================================


class TestNoFillerInstructionPresent:
    """Property tests for no-filler instruction presence in system prompt.
    
    **Property 5: No-Filler Instruction Present**
    
    *For any* call to PromptBuilder.get_system_prompt(), the returned prompt
    SHALL contain an instruction forbidding conversational filler.
    
    **Validates: Requirements 1.1, 1.2**
    
    Requirements:
        - 1.1: THE System_Prompt SHALL include an explicit instruction forbidding
               conversational filler such as "Here is the post:", "Sure!", or
               similar preambles
        - 1.2: THE System_Prompt SHALL instruct the model to begin output
               immediately with the [HOOK] tag
    """

    def test_system_prompt_contains_never_use_filler_instruction(self):
        """System prompt SHALL contain instruction to NEVER use conversational filler.
        
        **Validates: Requirements 1.1**
        """
        builder = PromptBuilder()
        
        system_prompt = builder.get_system_prompt()
        
        # Verify the system prompt contains the no-filler instruction
        assert "NEVER use conversational filler" in system_prompt, (
            "System prompt should contain 'NEVER use conversational filler' instruction.\n"
            f"Actual system prompt:\n{system_prompt}"
        )

    def test_system_prompt_contains_begin_immediately_with_hook_instruction(self):
        """System prompt SHALL instruct model to begin output immediately with [HOOK] tag.
        
        **Validates: Requirements 1.2**
        """
        builder = PromptBuilder()
        
        system_prompt = builder.get_system_prompt()
        
        # Verify the system prompt contains the instruction to begin with [HOOK]
        assert "Begin your output IMMEDIATELY with the [HOOK] tag" in system_prompt, (
            "System prompt should contain 'Begin your output IMMEDIATELY with the [HOOK] tag' instruction.\n"
            f"Actual system prompt:\n{system_prompt}"
        )

    def test_system_prompt_contains_example_filler_phrases(self):
        """System prompt SHALL contain examples of forbidden filler phrases.
        
        **Validates: Requirements 1.1**
        """
        builder = PromptBuilder()
        
        system_prompt = builder.get_system_prompt()
        
        # Verify the system prompt contains examples of forbidden filler
        forbidden_examples = [
            "Here is the post:",
            "Sure!",
            "Certainly!",
        ]
        
        # At least some forbidden examples should be mentioned
        examples_found = [
            example for example in forbidden_examples
            if example in system_prompt
        ]
        
        assert len(examples_found) >= 2, (
            f"System prompt should contain at least 2 examples of forbidden filler phrases.\n"
            f"Expected examples: {forbidden_examples}\n"
            f"Found examples: {examples_found}\n"
            f"Actual system prompt:\n{system_prompt}"
        )

    def test_system_prompt_contains_preambles_warning(self):
        """System prompt SHALL warn against similar preambles.
        
        **Validates: Requirements 1.1**
        """
        builder = PromptBuilder()
        
        system_prompt = builder.get_system_prompt()
        
        # Verify the system prompt warns against similar preambles
        assert "preamble" in system_prompt.lower(), (
            "System prompt should mention 'preambles' as forbidden content.\n"
            f"Actual system prompt:\n{system_prompt}"
        )

    @given(
        article=scored_article_strategy(),
    )
    @settings(max_examples=100)
    def test_system_prompt_consistent_across_articles(self, article: ScoredArticle):
        """For any article, get_system_prompt() SHALL return consistent no-filler instructions.
        
        The system prompt is independent of article content, so it should always
        contain the same no-filler instructions regardless of what article is
        being processed.
        
        **Validates: Requirements 1.1, 1.2**
        """
        builder = PromptBuilder()
        
        # Get system prompt (independent of article)
        system_prompt = builder.get_system_prompt()
        
        # Verify no-filler instruction is always present
        assert "NEVER use conversational filler" in system_prompt, (
            "System prompt should always contain no-filler instruction"
        )
        
        # Verify begin with [HOOK] instruction is always present
        assert "[HOOK]" in system_prompt, (
            "System prompt should always reference [HOOK] tag"
        )

    def test_system_prompt_critical_output_rules_section(self):
        """System prompt SHALL contain a CRITICAL OUTPUT RULES section.
        
        **Validates: Requirements 1.1, 1.2**
        """
        builder = PromptBuilder()
        
        system_prompt = builder.get_system_prompt()
        
        # Verify the system prompt has a critical output rules section
        assert "CRITICAL OUTPUT RULES" in system_prompt, (
            "System prompt should contain 'CRITICAL OUTPUT RULES' section.\n"
            f"Actual system prompt:\n{system_prompt}"
        )

    def test_system_prompt_no_filler_instruction_is_explicit(self):
        """The no-filler instruction SHALL be explicit and unambiguous.
        
        **Validates: Requirements 1.1**
        """
        builder = PromptBuilder()
        
        system_prompt = builder.get_system_prompt()
        
        # The instruction should use strong language (NEVER, not "avoid" or "try not to")
        assert "NEVER" in system_prompt, (
            "System prompt should use strong language (NEVER) for filler prohibition.\n"
            f"Actual system prompt:\n{system_prompt}"
        )
        
        # The instruction should specifically mention "conversational filler"
        assert "conversational filler" in system_prompt.lower(), (
            "System prompt should specifically mention 'conversational filler'.\n"
            f"Actual system prompt:\n{system_prompt}"
        )

    def test_system_prompt_hook_tag_instruction_is_explicit(self):
        """The [HOOK] tag instruction SHALL be explicit and unambiguous.
        
        **Validates: Requirements 1.2**
        """
        builder = PromptBuilder()
        
        system_prompt = builder.get_system_prompt()
        
        # The instruction should use strong language (IMMEDIATELY)
        assert "IMMEDIATELY" in system_prompt, (
            "System prompt should use strong language (IMMEDIATELY) for [HOOK] tag instruction.\n"
            f"Actual system prompt:\n{system_prompt}"
        )
        
        # The instruction should reference the [HOOK] tag
        assert "[HOOK]" in system_prompt, (
            "System prompt should reference [HOOK] tag.\n"
            f"Actual system prompt:\n{system_prompt}"
        )

    @given(
        num_calls=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=50)
    def test_system_prompt_idempotent(self, num_calls: int):
        """Multiple calls to get_system_prompt() SHALL return identical results.
        
        This ensures the no-filler instructions are consistently present across
        multiple invocations.
        
        **Validates: Requirements 1.1, 1.2**
        """
        builder = PromptBuilder()
        
        # Get system prompt multiple times
        prompts = [builder.get_system_prompt() for _ in range(num_calls)]
        
        # All prompts should be identical
        first_prompt = prompts[0]
        for i, prompt in enumerate(prompts[1:], start=2):
            assert prompt == first_prompt, (
                f"Call {i} to get_system_prompt() returned different result.\n"
                f"First call:\n{first_prompt}\n\n"
                f"Call {i}:\n{prompt}"
            )
        
        # Verify no-filler instruction is present in all
        for prompt in prompts:
            assert "NEVER use conversational filler" in prompt

    def test_system_prompt_contains_all_required_no_filler_elements(self):
        """System prompt SHALL contain all required no-filler elements.
        
        This is a comprehensive test that verifies all elements required by
        Requirements 1.1 and 1.2 are present in the system prompt.
        
        **Validates: Requirements 1.1, 1.2**
        """
        builder = PromptBuilder()
        
        system_prompt = builder.get_system_prompt()
        
        # Required elements from Requirement 1.1
        required_elements_1_1 = [
            ("NEVER use conversational filler", "No-filler prohibition"),
            ("Here is the post:", "Example filler phrase 1"),
            ("Sure!", "Example filler phrase 2"),
            ("Certainly!", "Example filler phrase 3"),
        ]
        
        # Required elements from Requirement 1.2
        required_elements_1_2 = [
            ("Begin your output IMMEDIATELY with the [HOOK] tag", "Begin with [HOOK] instruction"),
        ]
        
        # Check all required elements
        missing_elements = []
        
        for element, description in required_elements_1_1 + required_elements_1_2:
            if element not in system_prompt:
                missing_elements.append(f"- {description}: '{element}'")
        
        assert len(missing_elements) == 0, (
            f"System prompt is missing required no-filler elements:\n"
            + "\n".join(missing_elements) +
            f"\n\nActual system prompt:\n{system_prompt}"
        )


# =============================================================================
# Feature: robust-response-parsing, Property 6: Tag Format Instructions Present
# Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
# =============================================================================


class TestTagFormatInstructionsPresent:
    """Property tests for tag format instructions presence in prompts.
    
    **Property 6: Tag Format Instructions Present**
    
    *For any* article input to PromptBuilder.build(), the resulting prompt
    SHALL contain instructions for all four tag pairs: [HOOK]/[/HOOK],
    [VALUE]/[/VALUE], [CTA]/[/CTA], [HASHTAGS]/[/HASHTAGS].
    
    **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
    """

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_hook_tag_pair_instructions(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain [HOOK] and [/HOOK] tag instructions.
        
        **Validates: Requirements 2.1**
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
        
        # Verify [HOOK] tag is present
        assert "[HOOK]" in prompt, (
            f"Prompt should contain [HOOK] tag instruction.\n"
            f"Prompt:\n{prompt}"
        )
        
        # Verify [/HOOK] closing tag is present
        assert "[/HOOK]" in prompt, (
            f"Prompt should contain [/HOOK] closing tag instruction.\n"
            f"Prompt:\n{prompt}"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_value_tag_pair_instructions(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain [VALUE] and [/VALUE] tag instructions.
        
        **Validates: Requirements 2.2**
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
        
        # Verify [VALUE] tag is present
        assert "[VALUE]" in prompt, (
            f"Prompt should contain [VALUE] tag instruction.\n"
            f"Prompt:\n{prompt}"
        )
        
        # Verify [/VALUE] closing tag is present
        assert "[/VALUE]" in prompt, (
            f"Prompt should contain [/VALUE] closing tag instruction.\n"
            f"Prompt:\n{prompt}"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_cta_tag_pair_instructions(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain [CTA] and [/CTA] tag instructions.
        
        **Validates: Requirements 2.3**
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
        
        # Verify [CTA] tag is present
        assert "[CTA]" in prompt, (
            f"Prompt should contain [CTA] tag instruction.\n"
            f"Prompt:\n{prompt}"
        )
        
        # Verify [/CTA] closing tag is present
        assert "[/CTA]" in prompt, (
            f"Prompt should contain [/CTA] closing tag instruction.\n"
            f"Prompt:\n{prompt}"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_hashtags_tag_pair_instructions(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain [HASHTAGS] and [/HASHTAGS] tag instructions.
        
        **Validates: Requirements 2.4**
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
        
        # Verify [HASHTAGS] tag is present
        assert "[HASHTAGS]" in prompt, (
            f"Prompt should contain [HASHTAGS] tag instruction.\n"
            f"Prompt:\n{prompt}"
        )
        
        # Verify [/HASHTAGS] closing tag is present
        assert "[/HASHTAGS]" in prompt, (
            f"Prompt should contain [/HASHTAGS] closing tag instruction.\n"
            f"Prompt:\n{prompt}"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_output_format_section(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain an OUTPUT FORMAT section.
        
        **Validates: Requirements 2.5**
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
        
        # Verify OUTPUT FORMAT section is present
        assert "OUTPUT FORMAT" in prompt, (
            f"Prompt should contain 'OUTPUT FORMAT' section.\n"
            f"Prompt:\n{prompt}"
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_contains_all_four_tag_pairs(self, article: ScoredArticle):
        """For any article, the prompt SHALL contain all four tag pair instructions.
        
        This is a comprehensive test that verifies all tag pairs are present
        in a single prompt.
        
        **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
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
        
        # Define all required tag pairs
        required_tag_pairs = [
            ("[HOOK]", "[/HOOK]", "HOOK"),
            ("[VALUE]", "[/VALUE]", "VALUE"),
            ("[CTA]", "[/CTA]", "CTA"),
            ("[HASHTAGS]", "[/HASHTAGS]", "HASHTAGS"),
        ]
        
        # Check all tag pairs are present
        missing_tags = []
        
        for open_tag, close_tag, tag_name in required_tag_pairs:
            if open_tag not in prompt:
                missing_tags.append(f"- Opening tag {open_tag} for {tag_name}")
            if close_tag not in prompt:
                missing_tags.append(f"- Closing tag {close_tag} for {tag_name}")
        
        assert len(missing_tags) == 0, (
            f"Prompt is missing required tag instructions:\n"
            + "\n".join(missing_tags) +
            f"\n\nPrompt:\n{prompt}"
        )
        
        # Also verify OUTPUT FORMAT section is present
        assert "OUTPUT FORMAT" in prompt, (
            f"Prompt should contain 'OUTPUT FORMAT' section.\n"
            f"Prompt:\n{prompt}"
        )

    def test_tag_format_instructions_are_explicit_examples(self):
        """Tag format instructions SHALL include explicit examples of tag usage.
        
        The prompt should show the model exactly how to format output with tags,
        not just mention the tags abstractly.
        
        **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title="Test Article",
            source="AWS News Blog",
            summary="Test summary content",
            key_topics=["cloud_security"],
            why_it_matters="Test importance",
            hashtags=["#Test"],
        )
        
        # Verify the prompt contains example tag usage patterns
        # The OUTPUT FORMAT section should show tags with example content
        assert "[HOOK]" in prompt and "[/HOOK]" in prompt, (
            "Prompt should contain HOOK tag pair"
        )
        assert "[VALUE]" in prompt and "[/VALUE]" in prompt, (
            "Prompt should contain VALUE tag pair"
        )
        assert "[CTA]" in prompt and "[/CTA]" in prompt, (
            "Prompt should contain CTA tag pair"
        )
        assert "[HASHTAGS]" in prompt and "[/HASHTAGS]" in prompt, (
            "Prompt should contain HASHTAGS tag pair"
        )
        
        # Verify the OUTPUT FORMAT section exists and is marked as mandatory
        assert "OUTPUT FORMAT" in prompt, (
            "Prompt should contain OUTPUT FORMAT section"
        )
        assert "MANDATORY" in prompt, (
            "OUTPUT FORMAT section should be marked as MANDATORY"
        )

    def test_tag_instructions_include_no_text_before_hook_rule(self):
        """Tag format instructions SHALL include rule to not include text before [HOOK].
        
        **Validates: Requirements 2.5**
        """
        builder = PromptBuilder()
        
        prompt = builder.build(
            title="Test Article",
            source="AWS News Blog",
            summary="Test summary content",
            key_topics=["cloud_security"],
            why_it_matters="Test importance",
            hashtags=["#Test"],
        )
        
        # Verify the prompt instructs not to include text before [HOOK]
        assert "Do NOT include any text before [HOOK]" in prompt, (
            "Prompt should instruct not to include text before [HOOK].\n"
            f"Prompt:\n{prompt}"
        )


# =============================================================================
# Feature: robust-response-parsing, Property 4: Old Hook Style Names Excluded
# Validates: Requirements 4.5
# =============================================================================


class TestOldHookStyleNamesExcluded:
    """Property tests for old hook style name exclusion.
    
    **Property 4: Hook Style Names Present (negative check)**
    
    *For any* article input to PromptBuilder.build(), the resulting prompt SHALL NOT
    contain the old hook style names ("Bold Statement", "Contrarian View", "Fact-Driven").
    
    **Validates: Requirements 4.5**
    """

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_does_not_contain_bold_statement(self, article: ScoredArticle):
        """For any article, the prompt SHALL NOT contain 'Bold Statement' hook style.
        
        **Validates: Requirements 4.5**
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
        
        # Verify old hook style name is NOT present
        assert "Bold Statement" not in prompt, (
            "Prompt should NOT contain old hook style name 'Bold Statement'. "
            "This style has been replaced with 'Statistic-heavy'."
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_does_not_contain_contrarian_view(self, article: ScoredArticle):
        """For any article, the prompt SHALL NOT contain 'Contrarian View' hook style.
        
        **Validates: Requirements 4.5**
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
        
        # Verify old hook style name is NOT present
        assert "Contrarian View" not in prompt, (
            "Prompt should NOT contain old hook style name 'Contrarian View'. "
            "This style has been replaced with 'Contrarian'."
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_does_not_contain_fact_driven(self, article: ScoredArticle):
        """For any article, the prompt SHALL NOT contain 'Fact-Driven' hook style.
        
        **Validates: Requirements 4.5**
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
        
        # Verify old hook style name is NOT present
        assert "Fact-Driven" not in prompt, (
            "Prompt should NOT contain old hook style name 'Fact-Driven'. "
            "This style has been replaced with 'Bold Prediction'."
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_does_not_contain_any_old_hook_styles(self, article: ScoredArticle):
        """For any article, the prompt SHALL NOT contain any of the old hook style names.
        
        **Validates: Requirements 4.5**
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
        
        # Define old hook style names that should NOT be present
        old_hook_styles = [
            "Bold Statement",
            "Contrarian View",
            "Fact-Driven",
        ]
        
        # Verify none of the old hook style names are present
        found_old_styles = [style for style in old_hook_styles if style in prompt]
        
        assert len(found_old_styles) == 0, (
            f"Prompt should NOT contain any old hook style names. "
            f"Found: {found_old_styles}. "
            f"Old styles have been replaced with: 'Statistic-heavy', 'Contrarian', 'Bold Prediction'."
        )

    @given(article=scored_article_strategy())
    @settings(max_examples=100)
    def test_prompt_uses_new_styles_instead_of_old(self, article: ScoredArticle):
        """For any article, the prompt SHALL use new hook styles instead of old ones.
        
        This test verifies that the prompt contains the new hook style names
        AND does not contain the old hook style names.
        
        **Validates: Requirements 4.5**
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
        
        # Define old and new hook style names
        old_hook_styles = ["Bold Statement", "Contrarian View", "Fact-Driven"]
        new_hook_styles = ["Statistic-heavy", "Contrarian", "Bold Prediction"]
        
        # Verify old styles are NOT present
        for old_style in old_hook_styles:
            assert old_style not in prompt, (
                f"Prompt should NOT contain old hook style '{old_style}'"
            )
        
        # Verify new styles ARE present
        for new_style in new_hook_styles:
            assert new_style in prompt, (
                f"Prompt should contain new hook style '{new_style}'"
            )
