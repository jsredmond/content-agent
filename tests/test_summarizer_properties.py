"""Property-based tests for summarizer engine.

Feature: content-agent
Tests Properties 14, 15, 16, and 17 from the design document.
"""

import re
from hypothesis import given, settings, strategies as st, assume

from src.engines.article_normalizer import NormalizedArticle
from src.engines.summarizer import (
    generate_summary,
    generate_linkedin_angle,
    generate_hashtags,
    extract_key_topics,
    _count_sentences,
)
from src.config.settings import DEFAULT_KEYWORDS


# Strategy for generating normalized articles
@st.composite
def normalized_article_strategy(draw):
    """Generate a NormalizedArticle for testing."""
    source = draw(st.sampled_from([
        "AWS News Blog",
        "Microsoft Purview Blog",
        "Test Source",
    ]))
    
    title = draw(st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
        min_size=5,
        max_size=100
    ))
    
    canonical_url = draw(st.sampled_from([
        "https://aws.amazon.com/blogs/news/article",
        "https://techcommunity.microsoft.com/blog/post",
        "https://example.com/article",
    ]))
    
    # Generate summary text with 1-5 sentences
    num_sentences = draw(st.integers(min_value=1, max_value=5))
    sentences = []
    for _ in range(num_sentences):
        sentence = draw(st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'Z')),
            min_size=10,
            max_size=50
        ))
        # Ensure sentence ends with period
        sentence = sentence.strip()
        if sentence and not sentence.endswith('.'):
            sentence += '.'
        if sentence:
            sentences.append(sentence)
    
    summary_text = ' '.join(sentences) if sentences else None
    
    return NormalizedArticle(
        source=source,
        title=title,
        canonical_url=canonical_url,
        summary_text=summary_text,
    )


@st.composite
def article_with_keywords_strategy(draw):
    """Generate a NormalizedArticle that contains keywords from configured themes."""
    # Pick a theme and keyword to include
    theme = draw(st.sampled_from(list(DEFAULT_KEYWORDS.keys())))
    keyword = draw(st.sampled_from(DEFAULT_KEYWORDS[theme]))
    
    source = draw(st.sampled_from([
        "AWS News Blog",
        "Microsoft Purview Blog",
    ]))
    
    # Include the keyword in title or summary
    include_in_title = draw(st.booleans())
    
    if include_in_title:
        title = f"New {keyword} Feature Announced"
        summary_text = "This is a test summary about cloud features."
    else:
        title = "New Feature Announced"
        summary_text = f"This article discusses {keyword} and related topics."
    
    return NormalizedArticle(
        source=source,
        title=title,
        canonical_url="https://example.com/article",
        summary_text=summary_text,
    ), theme


# Feature: content-agent, Property 14: Summary Sentence Count
# Validates: Requirements 5.1
class TestSummarySentenceCount:
    """Property tests for summary sentence count.
    
    For any generated summary, it SHALL contain between 1 and 3 sentences (inclusive).
    """

    @given(article=normalized_article_strategy())
    @settings(max_examples=100)
    def test_summary_has_1_to_3_sentences(self, article: NormalizedArticle):
        """For any generated summary, it SHALL contain between 1 and 3 sentences."""
        summary = generate_summary(article)
        
        assert summary is not None
        assert len(summary) > 0
        
        sentence_count = _count_sentences(summary)
        assert 1 <= sentence_count <= 3, (
            f"Summary has {sentence_count} sentences, expected 1-3: '{summary}'"
        )

    @given(
        num_sentences=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_summary_truncates_long_content(self, num_sentences: int):
        """For any article with more than 3 sentences, summary SHALL have at most 3."""
        # Create article with specified number of sentences
        sentences = [f"Sentence number {i}." for i in range(num_sentences)]
        summary_text = ' '.join(sentences)
        
        article = NormalizedArticle(
            source="Test",
            title="Test Article",
            canonical_url="https://example.com",
            summary_text=summary_text,
        )
        
        summary = generate_summary(article)
        sentence_count = _count_sentences(summary)
        
        assert sentence_count <= 3, (
            f"Summary has {sentence_count} sentences, expected at most 3"
        )

    def test_summary_with_no_summary_text_uses_title(self):
        """When no summary_text is available, summary SHALL be generated from title."""
        article = NormalizedArticle(
            source="Test",
            title="Important Security Update",
            canonical_url="https://example.com",
            summary_text=None,
        )
        
        summary = generate_summary(article)
        
        assert summary is not None
        assert len(summary) > 0
        assert _count_sentences(summary) >= 1

    def test_summary_with_empty_summary_text_uses_title(self):
        """When summary_text is empty, summary SHALL be generated from title."""
        article = NormalizedArticle(
            source="Test",
            title="Important Security Update",
            canonical_url="https://example.com",
            summary_text="",
        )
        
        summary = generate_summary(article)
        
        assert summary is not None
        assert len(summary) > 0


# Feature: content-agent, Property 15: LinkedIn Angle Sentence Count
# Validates: Requirements 5.3
class TestLinkedInAngleSentenceCount:
    """Property tests for LinkedIn angle sentence count.
    
    For any generated LinkedIn angle, it SHALL contain exactly 1 sentence.
    """

    @given(article=normalized_article_strategy())
    @settings(max_examples=100)
    def test_linkedin_angle_has_exactly_1_sentence(self, article: NormalizedArticle):
        """For any generated LinkedIn angle, it SHALL contain exactly 1 sentence."""
        angle = generate_linkedin_angle(article)
        
        assert angle is not None
        assert len(angle) > 0
        
        sentence_count = _count_sentences(angle)
        assert sentence_count == 1, (
            f"LinkedIn angle has {sentence_count} sentences, expected 1: '{angle}'"
        )

    @given(
        title=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'Z')),
            min_size=5,
            max_size=100
        ),
        source=st.sampled_from(["AWS News Blog", "Microsoft Purview Blog", "Test"]),
    )
    @settings(max_examples=100)
    def test_linkedin_angle_varies_by_title(self, title: str, source: str):
        """LinkedIn angle generation SHALL be deterministic based on title."""
        article = NormalizedArticle(
            source=source,
            title=title,
            canonical_url="https://example.com",
        )
        
        angle1 = generate_linkedin_angle(article)
        angle2 = generate_linkedin_angle(article)
        
        # Same input should produce same output
        assert angle1 == angle2


# Feature: content-agent, Property 16: Hashtag Generation
# Validates: Requirements 5.4
class TestHashtagGeneration:
    """Property tests for hashtag generation.
    
    For any article with at least one matching topic, the generated hashtags
    list SHALL be non-empty.
    """

    @given(data=article_with_keywords_strategy())
    @settings(max_examples=100)
    def test_hashtags_non_empty_when_topics_match(self, data):
        """For any article with matching topics, hashtags SHALL be non-empty."""
        article, expected_theme = data
        
        # Extract topics first
        topics = extract_key_topics(article, DEFAULT_KEYWORDS)
        
        # Only test if topics were found
        assume(len(topics) > 0)
        
        hashtags = generate_hashtags(topics)
        
        assert len(hashtags) > 0, (
            f"Expected non-empty hashtags for topics {topics}"
        )

    @given(
        topics=st.lists(
            st.sampled_from(list(DEFAULT_KEYWORDS.keys())),
            min_size=1,
            max_size=3,
            unique=True,
        )
    )
    @settings(max_examples=100)
    def test_hashtags_generated_for_known_topics(self, topics: list[str]):
        """For any known topic themes, hashtags SHALL be generated."""
        hashtags = generate_hashtags(topics)
        
        assert len(hashtags) > 0, (
            f"Expected hashtags for topics {topics}"
        )

    def test_hashtags_empty_for_no_topics(self):
        """When no topics match, hashtags SHALL be empty."""
        hashtags = generate_hashtags([])
        
        assert hashtags == []

    @given(
        topics=st.lists(
            st.sampled_from(list(DEFAULT_KEYWORDS.keys())),
            min_size=1,
            max_size=6,
        )
    )
    @settings(max_examples=100)
    def test_hashtags_are_unique(self, topics: list[str]):
        """Generated hashtags SHALL not contain duplicates."""
        hashtags = generate_hashtags(topics)
        
        assert len(hashtags) == len(set(hashtags)), (
            f"Duplicate hashtags found: {hashtags}"
        )


# Feature: content-agent, Property 17: Topic Extraction
# Validates: Requirements 5.5
class TestTopicExtraction:
    """Property tests for topic extraction.
    
    For any article containing configured keywords, the extracted key_topics
    SHALL include at least one matching theme.
    """

    @given(data=article_with_keywords_strategy())
    @settings(max_examples=100)
    def test_topics_extracted_when_keywords_present(self, data):
        """For any article with keywords, at least one topic SHALL be extracted."""
        article, expected_theme = data
        
        topics = extract_key_topics(article, DEFAULT_KEYWORDS)
        
        assert len(topics) > 0, (
            f"Expected at least one topic for article with keyword from theme '{expected_theme}'"
        )
        assert expected_theme in topics, (
            f"Expected theme '{expected_theme}' in topics {topics}"
        )

    @given(
        theme=st.sampled_from(list(DEFAULT_KEYWORDS.keys())),
    )
    @settings(max_examples=100)
    def test_specific_theme_extracted(self, theme: str):
        """For any article containing a theme's keyword, that theme SHALL be extracted."""
        # Pick a keyword from the theme
        keyword = DEFAULT_KEYWORDS[theme][0]
        
        article = NormalizedArticle(
            source="Test",
            title=f"Article about {keyword}",
            canonical_url="https://example.com",
        )
        
        topics = extract_key_topics(article, DEFAULT_KEYWORDS)
        
        assert theme in topics, (
            f"Expected theme '{theme}' in topics {topics} for keyword '{keyword}'"
        )

    def test_no_topics_when_no_keywords_match(self):
        """When no keywords match, topics SHALL be empty."""
        article = NormalizedArticle(
            source="Test",
            title="Unrelated Article About Cooking",
            canonical_url="https://example.com",
            summary_text="This article is about recipes and food preparation.",
        )
        
        topics = extract_key_topics(article, DEFAULT_KEYWORDS)
        
        assert topics == []

    def test_no_topics_when_empty_keywords(self):
        """When keywords dict is empty, topics SHALL be empty."""
        article = NormalizedArticle(
            source="Test",
            title="Security Article",
            canonical_url="https://example.com",
        )
        
        topics = extract_key_topics(article, {})
        
        assert topics == []

    @given(
        themes=st.lists(
            st.sampled_from(list(DEFAULT_KEYWORDS.keys())),
            min_size=2,
            max_size=4,
            unique=True,
        )
    )
    @settings(max_examples=100)
    def test_multiple_themes_extracted(self, themes: list[str]):
        """When multiple theme keywords are present, all matching themes SHALL be extracted."""
        # Build title with keywords from multiple themes
        keywords = [DEFAULT_KEYWORDS[theme][0] for theme in themes]
        title = "Article about " + " and ".join(keywords)
        
        article = NormalizedArticle(
            source="Test",
            title=title,
            canonical_url="https://example.com",
        )
        
        topics = extract_key_topics(article, DEFAULT_KEYWORDS)
        
        for theme in themes:
            assert theme in topics, (
                f"Expected theme '{theme}' in topics {topics}"
            )

    def test_case_insensitive_matching(self):
        """Keyword matching SHALL be case-insensitive."""
        article = NormalizedArticle(
            source="Test",
            title="CLOUD SECURITY Best Practices",
            canonical_url="https://example.com",
        )
        
        topics = extract_key_topics(article, DEFAULT_KEYWORDS)
        
        assert "cloud_security" in topics
