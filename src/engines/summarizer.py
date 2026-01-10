"""Summarizer engine for generating LinkedIn-ready article metadata.

This module provides functions to generate summaries, "why it matters" statements,
LinkedIn angles, hashtags, and extract key topics from normalized articles.
"""

import re
from typing import Optional

from src.engines.article_normalizer import NormalizedArticle


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences.
    
    Uses a simple regex-based approach that handles common sentence endings.
    
    Args:
        text: Text to split into sentences
        
    Returns:
        List of sentences
    """
    if not text:
        return []
    
    # Split on sentence-ending punctuation followed by space or end of string
    # This handles ., !, ? followed by space or end
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    # Filter out empty strings and strip whitespace
    sentences = [s.strip() for s in sentences if s.strip()]
    
    return sentences


def _count_sentences(text: str) -> int:
    """Count the number of sentences in text.
    
    Args:
        text: Text to count sentences in
        
    Returns:
        Number of sentences
    """
    return len(_split_sentences(text))


def generate_summary(article: NormalizedArticle) -> str:
    """Generate a 1-3 sentence summary from article content.
    
    Extracts the first 1-3 sentences from the article's summary_text.
    If no summary_text is available, generates a basic summary from the title.
    
    Args:
        article: The normalized article to summarize
        
    Returns:
        A 1-3 sentence summary string
        
    Example:
        >>> article = NormalizedArticle(
        ...     source="AWS News Blog",
        ...     title="New Security Feature",
        ...     canonical_url="https://aws.amazon.com/blog/security",
        ...     summary_text="AWS announces new security feature. It helps protect data. Easy to configure."
        ... )
        >>> summary = generate_summary(article)
        >>> 1 <= _count_sentences(summary) <= 3
        True
    """
    # Use summary_text if available
    if article.summary_text:
        sentences = _split_sentences(article.summary_text)
        if sentences:
            # Take up to 3 sentences
            selected = sentences[:3]
            return ' '.join(selected)
    
    # Fallback: generate from title
    title = article.title or "Article"
    return f"{title}."


def extract_key_topics(
    article: NormalizedArticle,
    keywords: dict[str, list[str]]
) -> list[str]:
    """Extract key topics that match configured keyword themes.
    
    Searches the article's title and summary_text for keywords from each theme.
    Returns the theme names that have at least one keyword match.
    
    Args:
        article: The normalized article to analyze
        keywords: Dictionary mapping theme names to lists of keywords
        
    Returns:
        List of matching theme names (e.g., ["cloud_security", "identity_and_access"])
        
    Example:
        >>> article = NormalizedArticle(
        ...     source="AWS",
        ...     title="New IAM Security Feature",
        ...     canonical_url="https://aws.amazon.com/blog",
        ...     summary_text="Enhanced authentication and access management."
        ... )
        >>> keywords = {"identity_and_access": ["IAM", "authentication", "access management"]}
        >>> topics = extract_key_topics(article, keywords)
        >>> "identity_and_access" in topics
        True
    """
    if not keywords:
        return []
    
    # Combine title and summary for searching
    search_text = ""
    if article.title:
        search_text += article.title + " "
    if article.summary_text:
        search_text += article.summary_text
    
    search_text_lower = search_text.lower()
    
    matched_topics = []
    for theme, theme_keywords in keywords.items():
        for keyword in theme_keywords:
            if keyword.lower() in search_text_lower:
                matched_topics.append(theme)
                break  # Only add theme once
    
    return matched_topics


def generate_why_it_matters(
    article: NormalizedArticle,
    topics: list[str]
) -> str:
    """Generate a "why it matters" statement with security-first framing.
    
    Creates a 1-2 sentence statement explaining the security and compliance
    implications of the article content.
    
    Args:
        article: The normalized article
        topics: List of matched topic themes
        
    Returns:
        A security-first "why it matters" statement
        
    Example:
        >>> article = NormalizedArticle(
        ...     source="AWS",
        ...     title="New IAM Feature",
        ...     canonical_url="https://aws.amazon.com/blog"
        ... )
        >>> statement = generate_why_it_matters(article, ["identity_and_access"])
        >>> len(statement) > 0
        True
    """
    title = article.title or "This update"
    
    # Map topics to security-focused framing
    topic_framings = {
        "cloud_security": "strengthens your cloud security posture",
        "identity_and_access": "improves identity and access controls",
        "governance_and_compliance": "supports governance and compliance requirements",
        "data_protection": "enhances data protection capabilities",
        "auditing_and_retention": "improves audit and monitoring capabilities",
        "devsecops": "enables security automation in your DevOps pipeline",
    }
    
    if topics:
        # Use the first matched topic for framing
        primary_topic = topics[0]
        framing = topic_framings.get(
            primary_topic,
            "helps organizations improve their security posture"
        )
        return f"{title} {framing}. Security teams should evaluate this for their environment."
    
    # Default framing when no topics match
    return f"{title} may impact your cloud security strategy. Review for potential benefits."


def generate_linkedin_angle(article: NormalizedArticle) -> str:
    """Generate a suggested LinkedIn angle (1 sentence).
    
    Creates a single sentence suggestion for how to frame the article
    in a LinkedIn post.
    
    Args:
        article: The normalized article
        
    Returns:
        A single sentence LinkedIn angle suggestion
        
    Example:
        >>> article = NormalizedArticle(
        ...     source="AWS News Blog",
        ...     title="New Security Feature",
        ...     canonical_url="https://aws.amazon.com/blog"
        ... )
        >>> angle = generate_linkedin_angle(article)
        >>> _count_sentences(angle) == 1
        True
    """
    title = article.title or "This article"
    source = article.source or "the cloud provider"
    
    # Strip trailing punctuation from title to avoid creating multiple sentences
    # when the title is embedded in the angle sentence
    title = title.rstrip('.!?')
    
    # Generate a professional LinkedIn-style angle
    angles = [
        f"Share how {title} from {source} can benefit your organization's security strategy.",
        f"Discuss the practical implications of {title} for enterprise security teams.",
        f"Highlight key takeaways from {title} that security leaders should know.",
    ]
    
    # Use title length to deterministically select an angle
    index = len(title) % len(angles)
    return angles[index]


def generate_hashtags(topics: list[str]) -> list[str]:
    """Generate relevant hashtags from matched topics.
    
    Converts topic theme names into appropriate hashtags for LinkedIn.
    
    Args:
        topics: List of matched topic themes
        
    Returns:
        List of hashtag strings (without # prefix)
        
    Example:
        >>> hashtags = generate_hashtags(["cloud_security", "identity_and_access"])
        >>> "CloudSecurity" in hashtags
        True
    """
    if not topics:
        return []
    
    # Map topics to hashtags
    topic_hashtags = {
        "cloud_security": ["CloudSecurity", "CyberSecurity", "InfoSec"],
        "identity_and_access": ["IAM", "IdentityManagement", "ZeroTrust"],
        "governance_and_compliance": ["Compliance", "GRC", "RiskManagement"],
        "data_protection": ["DataProtection", "DataSecurity", "DLP"],
        "auditing_and_retention": ["Audit", "SecurityMonitoring", "Logging"],
        "devsecops": ["DevSecOps", "SecurityAutomation", "ShiftLeft"],
    }
    
    hashtags = []
    seen = set()
    
    for topic in topics:
        topic_tags = topic_hashtags.get(topic, [])
        for tag in topic_tags:
            if tag not in seen:
                hashtags.append(tag)
                seen.add(tag)
    
    return hashtags
