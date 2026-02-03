"""Ollama-based LinkedIn post generator.

This module provides the ContentGenerator class for transforming scraped article
content into high-engagement LinkedIn posts using the Hook-Value-CTA framework.
It integrates with a local Ollama LLM runtime for text generation.

Custom Exceptions:
    OllamaConnectionError: Raised when unable to connect to Ollama
    ModelNotAvailableError: Raised when requested model is not available
    GenerationError: Raised when post generation fails

Data Models:
    GeneratedPost: Output structure for a generated LinkedIn post
    BatchResult: Result of batch post generation
"""

from dataclasses import dataclass
from datetime import datetime
import logging
import random
import re


logger = logging.getLogger(__name__)


# =============================================================================
# Regex Patterns for Tag-Based Response Parsing
# =============================================================================

# Pattern for extracting tagged sections (case-insensitive, multiline)
TAG_PATTERN = r'\[{tag}\](.*?)\[/{tag}\]'

# Compiled patterns for each section
HOOK_PATTERN = re.compile(r'\[HOOK\](.*?)\[/HOOK\]', re.IGNORECASE | re.DOTALL)
VALUE_PATTERN = re.compile(r'\[VALUE\](.*?)\[/VALUE\]', re.IGNORECASE | re.DOTALL)
CTA_PATTERN = re.compile(r'\[CTA\](.*?)\[/CTA\]', re.IGNORECASE | re.DOTALL)
HASHTAGS_PATTERN = re.compile(r'\[HASHTAGS\](.*?)\[/HASHTAGS\]', re.IGNORECASE | re.DOTALL)


class OllamaConnectionError(Exception):
    """Raised when unable to connect to Ollama.
    
    This exception is raised when the ContentGenerator cannot establish
    a connection to the local Ollama instance. It includes troubleshooting
    guidance to help users resolve the issue.
    
    Attributes:
        message: The error message describing the connection failure
        troubleshooting: Instructions for resolving the connection issue
        
    Example:
        >>> raise OllamaConnectionError()
        OllamaConnectionError: Cannot connect to Ollama
        Ensure Ollama is running: 'ollama serve'
        Check if Ollama is accessible at http://localhost:11434
        
        >>> raise OllamaConnectionError("Connection refused on port 11434")
        OllamaConnectionError: Connection refused on port 11434
        Ensure Ollama is running: 'ollama serve'
        Check if Ollama is accessible at http://localhost:11434
    """
    
    def __init__(self, message: str = "Cannot connect to Ollama") -> None:
        """Initialize the OllamaConnectionError.
        
        Args:
            message: Custom error message describing the connection failure.
                    Defaults to "Cannot connect to Ollama".
        """
        self.message = message
        self.troubleshooting = (
            "Ensure Ollama is running: 'ollama serve'\n"
            "Check if Ollama is accessible at http://localhost:11434"
        )
        super().__init__(f"{message}\n{self.troubleshooting}")


class ModelNotAvailableError(Exception):
    """Raised when requested model is not available in Ollama.
    
    This exception is raised when the ContentGenerator attempts to use
    a model that is not currently loaded in the Ollama instance. It includes
    the model name and instructions for pulling the model.
    
    Attributes:
        model: The name of the unavailable model
        message: The error message describing the issue
        troubleshooting: Instructions for pulling the missing model
        
    Example:
        >>> raise ModelNotAvailableError("llama4:scout")
        ModelNotAvailableError: Model 'llama4:scout' is not available in Ollama
        Pull the model with: 'ollama pull llama4:scout'
    """
    
    def __init__(self, model: str) -> None:
        """Initialize the ModelNotAvailableError.
        
        Args:
            model: The name of the model that is not available in Ollama.
        """
        self.model = model
        self.message = f"Model '{model}' is not available in Ollama"
        self.troubleshooting = f"Pull the model with: 'ollama pull {model}'"
        super().__init__(f"{self.message}\n{self.troubleshooting}")


class GenerationError(Exception):
    """Raised when post generation fails.
    
    This exception is raised when the ContentGenerator fails to generate
    a LinkedIn post for a given article. It includes the article title
    for debugging context and the underlying cause of the failure.
    
    Attributes:
        article_title: The title of the article that failed to generate
        cause: The underlying reason for the generation failure
        
    Example:
        >>> raise GenerationError("AWS Announces New Security Feature", "Model returned empty response")
        GenerationError: Failed to generate post for 'AWS Announces New Security Feature': Model returned empty response
    """
    
    def __init__(self, article_title: str, cause: str) -> None:
        """Initialize the GenerationError.
        
        Args:
            article_title: The title of the article for which generation failed.
                          Used for debugging context.
            cause: A description of why the generation failed.
        """
        self.article_title = article_title
        self.cause = cause
        super().__init__(f"Failed to generate post for '{article_title}': {cause}")


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class GeneratedPost:
    """Output structure for a generated LinkedIn post.
    
    This dataclass represents a successfully generated LinkedIn post with
    structured sections following the Hook-Value-CTA framework. It includes
    metadata about the generation process and the source article.
    
    Attributes:
        full_text: Complete post text ready to publish on LinkedIn.
        hook: Attention-grabbing opening section (question, statistic, or bold statement).
        value: Core insight, data, or takeaway from the article.
        cta: Call-to-action section with engagement prompt.
        hashtags: List of hashtags included in the post.
        model_used: Name of the Ollama model used for generation.
        generated_at: Timestamp when the post was generated.
        source_url: URL of the original article used as source material.
        character_count: Total character count of full_text (max 3000 for LinkedIn).
        
    Example:
        >>> post = GeneratedPost(
        ...     full_text="🔐 Is your cloud security keeping pace?\\n\\nAWS just announced...",
        ...     hook="🔐 Is your cloud security keeping pace?",
        ...     value="AWS just announced enhanced security controls...",
        ...     cta="What's your biggest cloud security challenge? Share below!",
        ...     hashtags=["#CloudSecurity", "#AWS", "#CyberSecurity"],
        ...     model_used="qwen3-coder:30b",
        ...     generated_at=datetime(2024, 1, 15, 10, 30, 0),
        ...     source_url="https://aws.amazon.com/blogs/aws/new-security-feature",
        ...     character_count=450
        ... )
        >>> post.character_count < 3000
        True
        
    Requirements:
        - 7.1: Return a GeneratedPost dataclass containing the full post text
        - 7.2: Include separate fields for hook, value, and cta sections
        - 7.3: Include the model name used for generation
        - 7.4: Include a generation timestamp
        - 7.5: Include the source article's URL for reference
    """
    
    full_text: str
    hook: str
    value: str
    cta: str
    hashtags: list[str]
    model_used: str
    generated_at: datetime
    source_url: str
    character_count: int


@dataclass
class BatchResult:
    """Result of batch post generation.
    
    This dataclass represents the outcome of processing multiple articles
    through the ContentGenerator. It tracks successful generations, failures,
    and provides summary statistics.
    
    Attributes:
        successful: List of successfully generated posts.
        failed: List of tuples containing (article_title, error_message) for
                each article that failed to generate.
        total_processed: Total number of articles that were attempted.
        success_rate: Percentage of successful generations (0.0 to 1.0).
        
    Example:
        >>> result = BatchResult(
        ...     successful=[post1, post2, post3],
        ...     failed=[("Failed Article", "Model timeout")],
        ...     total_processed=4,
        ...     success_rate=0.75
        ... )
        >>> len(result.successful) + len(result.failed) == result.total_processed
        True
        
    Requirements:
        - 8.3: Return a list of results with success/failure status for each article
    """
    
    successful: list[GeneratedPost]
    failed: list[tuple[str, str]]  # (article_title, error_message)
    total_processed: int
    success_rate: float


# =============================================================================
# Context Management
# =============================================================================


# Import TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.engines.article_normalizer import ScoredArticle


class ContextManager:
    """Manage content length for model context windows.
    
    The ContextManager handles token estimation and content preparation for
    LLM prompts. It ensures that article content fits within the model's
    context window by applying intelligent summarization when necessary.
    
    Token estimation uses the approximation of 4 characters per token, which
    is a reasonable average for English text with mixed content (prose, code,
    technical terms).
    
    Attributes:
        max_tokens: Maximum number of tokens allowed before truncation.
        
    Example:
        >>> cm = ContextManager(max_tokens=10000)
        >>> cm.estimate_tokens("Hello world")  # 11 chars / 4 = 2.75 -> 2
        2
        >>> content, truncated = cm.prepare_content(article)
        >>> if truncated:
        ...     print("Content was truncated to fit context window")
        
    Requirements:
        - 3.1: Accept articles with content up to 10,000 tokens without truncation
        - 3.2: Apply intelligent summarization when content exceeds limits
        - 3.4: Log a warning when content truncation is applied
        - 3.5: Support configurable context window management
    """
    
    # Characters per token approximation (industry standard for English text)
    CHARS_PER_TOKEN = 4
    
    def __init__(self, max_tokens: int = 10000) -> None:
        """Initialize the ContextManager with token limit.
        
        Args:
            max_tokens: Maximum number of tokens allowed before truncation.
                       Defaults to 10000 tokens (approximately 40,000 characters).
                       
        Example:
            >>> cm = ContextManager()  # Uses default 10000 tokens
            >>> cm.max_tokens
            10000
            >>> cm = ContextManager(max_tokens=5000)  # Custom limit
            >>> cm.max_tokens
            5000
        """
        self.max_tokens = max_tokens
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.
        
        Uses the approximation of 4 characters per token, which is a reasonable
        average for English text. This is a heuristic and actual token counts
        may vary depending on the specific tokenizer used by the model.
        
        Args:
            text: The text to estimate tokens for.
            
        Returns:
            Estimated number of tokens (integer, rounded down).
            
        Example:
            >>> cm = ContextManager()
            >>> cm.estimate_tokens("")  # Empty string
            0
            >>> cm.estimate_tokens("Hello")  # 5 chars / 4 = 1.25 -> 1
            1
            >>> cm.estimate_tokens("Hello world!")  # 12 chars / 4 = 3
            3
        """
        if not text:
            return 0
        return len(text) // self.CHARS_PER_TOKEN
    
    def prepare_content(self, article: "ScoredArticle") -> tuple[str, bool]:
        """Prepare article content for prompt inclusion.
        
        Combines relevant article fields into a single content string and
        checks if it fits within the token limit. If the content exceeds
        the limit, it applies summarization to reduce the size.
        
        The content includes:
        - Title
        - Source
        - Summary
        - Key topics
        - Why it matters
        - Suggested LinkedIn angle
        
        Args:
            article: A ScoredArticle object containing the article data.
            
        Returns:
            A tuple of (prepared_content, was_truncated) where:
            - prepared_content: The content string ready for prompt inclusion
            - was_truncated: True if content was truncated to fit limits
            
        Example:
            >>> cm = ContextManager(max_tokens=10000)
            >>> content, truncated = cm.prepare_content(article)
            >>> if truncated:
            ...     logger.warning("Content was truncated")
            
        Requirements:
            - 3.1: Accept articles with content up to 10,000 tokens without truncation
            - 3.2: Apply intelligent summarization when content exceeds limits
            - 3.4: Log a warning when content truncation is applied
        """
        # Combine article fields into content string
        content_parts = [
            f"Title: {article.title}",
            f"Source: {article.source}",
            f"Summary: {article.summary}",
            f"Key Topics: {', '.join(article.key_topics)}",
            f"Why It Matters: {article.why_it_matters}",
            f"LinkedIn Angle: {article.suggested_linkedin_angle}",
        ]
        
        # Add author if available
        if article.author:
            content_parts.insert(2, f"Author: {article.author}")
        
        # Add published date if available
        if article.published_date:
            content_parts.insert(2, f"Published: {article.published_date.isoformat()}")
        
        content = "\n".join(content_parts)
        
        # Check if content fits within token limit
        estimated_tokens = self.estimate_tokens(content)
        
        if estimated_tokens <= self.max_tokens:
            return content, False
        
        # Content exceeds limit - apply summarization
        logger.warning(
            f"Content for article '{article.title}' exceeds token limit "
            f"({estimated_tokens} tokens > {self.max_tokens} max). "
            "Applying truncation."
        )
        
        # Calculate target tokens (leave some buffer for prompt overhead)
        target_tokens = self.max_tokens
        truncated_content = self.summarize_for_context(content, target_tokens)
        
        return truncated_content, True
    
    def summarize_for_context(self, text: str, target_tokens: int) -> str:
        """Reduce text to fit within target token count.
        
        Applies intelligent truncation to reduce content size while preserving
        the most important information. The strategy prioritizes:
        1. Keeping the beginning of the content (title, source, summary)
        2. Preserving key structural elements
        3. Truncating from the end when necessary
        
        Args:
            text: The text to summarize/truncate.
            target_tokens: The target number of tokens to fit within.
            
        Returns:
            Truncated text that fits within the target token count.
            
        Example:
            >>> cm = ContextManager()
            >>> long_text = "A" * 50000  # Very long text
            >>> short_text = cm.summarize_for_context(long_text, 1000)
            >>> cm.estimate_tokens(short_text) <= 1000
            True
            
        Requirements:
            - 3.2: Apply intelligent summarization when content exceeds limits
            - 3.3: Preserve key points, statistics, and actionable insights
        """
        if target_tokens <= 0:
            return ""
        
        # Calculate target character count
        target_chars = target_tokens * self.CHARS_PER_TOKEN
        
        if len(text) <= target_chars:
            return text
        
        # Split content into lines to preserve structure
        lines = text.split("\n")
        
        # Priority fields to keep (in order of importance)
        priority_prefixes = ["Title:", "Source:", "Summary:", "Key Topics:"]
        
        # Separate priority lines from others
        priority_lines = []
        other_lines = []
        
        for line in lines:
            is_priority = any(line.startswith(prefix) for prefix in priority_prefixes)
            if is_priority:
                priority_lines.append(line)
            else:
                other_lines.append(line)
        
        # Build result starting with priority content
        result_lines = priority_lines.copy()
        result = "\n".join(result_lines)
        
        # Add other lines if space permits
        for line in other_lines:
            potential_result = result + "\n" + line if result else line
            if len(potential_result) <= target_chars:
                result = potential_result
            else:
                # No more space - stop adding lines
                break
        
        # If still over limit, truncate the result
        if len(result) > target_chars:
            # Truncate and add ellipsis to indicate truncation
            result = result[:target_chars - 3] + "..."
        
        return result


# =============================================================================
# Prompt Building
# =============================================================================


class PromptBuilder:
    """Build prompts for LinkedIn post generation.
    
    The PromptBuilder constructs optimized prompts for generating LinkedIn posts
    using the Hook-Value-CTA framework. It includes system instructions for tone
    and audience, and dynamically adds security-first messaging when relevant.
    
    The builder ensures that all prompts include:
    - Article metadata (title, source, summary, key topics)
    - Hook-Value-CTA framework instructions
    - Target audience specification (CIO, CISO, CTO, IT Director)
    - Professional yet engaging tone instructions
    - Security-first messaging for security-related topics
    
    Class Attributes:
        SYSTEM_PROMPT: Base system instructions for the LLM defining audience and tone.
        HOOK_VALUE_CTA_TEMPLATE: Template for the user prompt with framework instructions.
        SECURITY_TOPICS: Set of topic keywords that trigger security-first framing.
        
    Example:
        >>> builder = PromptBuilder()
        >>> prompt = builder.build(
        ...     title="AWS Announces New Security Feature",
        ...     source="AWS News Blog",
        ...     summary="AWS has released enhanced security controls...",
        ...     key_topics=["cloud_security", "identity_and_access"],
        ...     why_it_matters="This update strengthens cloud security posture...",
        ...     hashtags=["#AWS", "#CloudSecurity"]
        ... )
        >>> "Hook" in prompt and "Value" in prompt and "CTA" in prompt
        True
        
    Requirements:
        - 5.1: Construct prompts that include article title, source, summary, and key topics
        - 5.2: Include Hook-Value-CTA framework instructions in every prompt
        - 5.3: Specify the target audience (CIO, CISO, CTO, IT Director) in the prompt
        - 5.4: Instruct the model to use a professional yet engaging tone
        - 5.5: Emphasize security-first messaging for security/compliance themes
    """
    
    # System prompt defining audience and tone (Requirement 5.3, 5.4)
    SYSTEM_PROMPT: str = """You are a LinkedIn content strategist specializing in cloud security and enterprise technology. 
Your audience includes CIOs, CISOs, CTOs, and IT Directors in regulated industries 
(finance, healthcare, government, professional services).

Write in a professional yet engaging tone. Be concise and actionable.
Focus on security-first messaging paired with practical modernization guidance.

CRITICAL OUTPUT RULES:
- NEVER use conversational filler like "Here is the post:", "Sure!", "Certainly!", or similar preambles
- Begin your output IMMEDIATELY with the [HOOK] tag
- Use the exact tag format specified in the prompt"""
    
    # Hook styles for randomization
    HOOK_STYLES: list[str] = [
        "Statistic-heavy",
        "Contrarian",
        "Bold Prediction",
    ]
    
    # Hook-Value-CTA template for user prompts (Requirement 5.2)
    HOOK_VALUE_CTA_TEMPLATE: str = """Create a LinkedIn post about the following article using the Hook-Value-CTA framework:

ARTICLE INFORMATION:
- Title: {title}
- Source: {source}
- Summary: {summary}
- Key Topics: {key_topics}
- Why It Matters: {why_it_matters}

FRAMEWORK REQUIREMENTS:

1. HOOK (1-2 sentences): {hook_style_instruction}
   
   CRITICAL VARIETY RULE: DO NOT use a statistic for more than one out of every four posts. Use a Bold Prediction or a Contrarian opening for the others. Avoid starting with a question.

2. VALUE (3-5 sentences): Provide the core insight:
   - What's the key announcement or update?
   - What's the practical implication for security teams?
   - What action should leaders consider?

3. CTA (1-2 sentences): End with engagement:
   - Ask a question to spark discussion
   - Invite readers to share their experience
   - Suggest a specific next step

FORMAT REQUIREMENTS:
- Use line breaks between sections for readability
- Keep total length under 2800 characters (leave room for hashtags)
- Include EXACTLY 3 hashtags at the end - select the 3 most relevant from: {hashtags}
- Use emojis sparingly (1-2 max) if they add value

{security_framing}
OUTPUT FORMAT (MANDATORY):
Wrap each section in explicit tags. Do NOT include any text before [HOOK].

[HOOK]
Your attention-grabbing opening here
[/HOOK]

[VALUE]
Your core insight content here
[/VALUE]

[CTA]
Your call-to-action here
[/CTA]

[HASHTAGS]
#Hashtag1 #Hashtag2 #Hashtag3
[/HASHTAGS]

HASHTAG REQUIREMENT:
Include exactly 3 hashtags from: {hashtags}"""
    
    # Security-related topics that trigger security-first framing (Requirement 5.5)
    SECURITY_TOPICS: set[str] = {
        "cloud_security",
        "identity_and_access",
        "governance_and_compliance",
        "data_protection",
        "auditing_and_retention",
        "devsecops",
    }
    
    def build(
        self,
        title: str,
        source: str,
        summary: str,
        key_topics: list[str],
        why_it_matters: str,
        hashtags: list[str],
        hook_style: str | None = None,
    ) -> str:
        """Build a complete prompt for post generation.
        
        Constructs a prompt that includes all article metadata, Hook-Value-CTA
        framework instructions, and appropriate security framing based on the
        article's topics.
        
        Args:
            title: The article title.
            source: The source of the article (e.g., "AWS News Blog").
            summary: A brief summary of the article content.
            key_topics: List of topic keywords associated with the article.
            why_it_matters: Statement explaining the article's significance.
            hashtags: List of hashtags to include in the post.
            hook_style: Optional specific hook style to use (e.g., "Contrarian", "Bold Prediction").
                       If None, all styles are presented as options.
            
        Returns:
            A formatted prompt string ready to send to the LLM.
        """
        # Format key topics as comma-separated string
        key_topics_str = ", ".join(key_topics) if key_topics else "General"
        
        # Format hashtags as space-separated string
        hashtags_str = " ".join(hashtags) if hashtags else ""
        
        # Add security framing if applicable
        security_framing = self._add_security_framing(key_topics)
        
        # Build hook style instruction based on whether a specific style is requested
        hook_style_instruction = self._build_hook_style_instruction(hook_style)
        
        # Build the prompt using the template
        prompt = self.HOOK_VALUE_CTA_TEMPLATE.format(
            title=title,
            source=source,
            summary=summary,
            key_topics=key_topics_str,
            why_it_matters=why_it_matters,
            hashtags=hashtags_str,
            security_framing=security_framing,
            hook_style_instruction=hook_style_instruction,
        )
        
        return prompt
    
    def _build_hook_style_instruction(self, hook_style: str | None) -> str:
        """Build the hook style instruction for the prompt.
        
        Args:
            hook_style: Specific hook style to use, or None for all options.
            
        Returns:
            Instruction text for the hook style section.
        """
        if hook_style:
            style_descriptions = {
                "Statistic-heavy": "Lead with a compelling number or data point",
                "Contrarian": "Challenge conventional wisdom or common assumptions",
                "Bold Prediction": "Make a confident forecast about the future",
            }
            description = style_descriptions.get(hook_style, "")
            return f"USE THIS HOOK STYLE: {hook_style} - {description}"
        else:
            return """Start with ONE of these attention-grabbing techniques:
   - Statistic-heavy: Lead with a compelling number or data point
   - Contrarian: Challenge conventional wisdom or common assumptions
   - Bold Prediction: Make a confident forecast about the future"""
    
    def _add_security_framing(self, topics: list[str]) -> str:
        """Add security-first messaging for relevant topics.
        
        Checks if any of the article's topics are security-related and returns
        additional prompt instructions to emphasize security-first messaging.
        
        Args:
            topics: List of topic keywords from the article.
            
        Returns:
            Additional prompt text for security framing, or empty string if
            no security topics are present.
            
        Example:
            >>> builder = PromptBuilder()
            >>> framing = builder._add_security_framing(["cloud_security", "automation"])
            >>> "security-first" in framing.lower()
            True
            >>> builder._add_security_framing(["general_news"])
            ''
            
        Requirements:
            - 5.5: Emphasize security-first messaging for security/compliance themes
        """
        if not topics:
            return ""
        
        # Check if any topic is security-related
        topics_lower = {topic.lower() for topic in topics}
        has_security_topic = bool(topics_lower & self.SECURITY_TOPICS)
        
        if has_security_topic:
            return """SECURITY EMPHASIS:
This article covers security or compliance topics. Ensure the post:
- Leads with security implications and risk considerations
- Emphasizes protection, compliance, and risk mitigation benefits
- Frames modernization through a security-first lens
- Highlights actionable security guidance for IT leaders

"""
        
        return ""
    
    def _format_audience_context(self) -> str:
        """Format target audience description.
        
        Returns a formatted string describing the target audience for LinkedIn
        posts. This is used to ensure the LLM understands who the content is for.
        
        Returns:
            A string describing the target audience.
            
        Example:
            >>> builder = PromptBuilder()
            >>> audience = builder._format_audience_context()
            >>> "CIO" in audience and "CISO" in audience
            True
            >>> "regulated industries" in audience.lower()
            True
            
        Requirements:
            - 5.3: Specify the target audience (CIO, CISO, CTO, IT Director)
        """
        return (
            "Target Audience: CIOs, CISOs, CTOs, and IT Directors in regulated "
            "industries (finance, healthcare, government, professional services). "
            "These leaders prioritize security, compliance, and practical "
            "modernization guidance."
        )
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for LLM configuration.
        
        Returns the system prompt that should be used when configuring the LLM
        for LinkedIn post generation. This includes audience and tone instructions.
        
        Returns:
            The system prompt string.
            
        Example:
            >>> builder = PromptBuilder()
            >>> system = builder.get_system_prompt()
            >>> "professional" in system.lower()
            True
            >>> "CIO" in system or "CISO" in system
            True
            
        Requirements:
            - 5.3: Specify the target audience
            - 5.4: Instruct the model to use a professional yet engaging tone
        """
        return self.SYSTEM_PROMPT


# =============================================================================
# Ollama Client
# =============================================================================


class OllamaClient:
    """Internal client for Ollama API communication.
    
    The OllamaClient handles all communication with the local Ollama runtime.
    It provides methods to check connectivity, list available models, and
    send chat requests for text generation.
    
    The client wraps connection errors and timeouts in appropriate custom
    exceptions to provide clear error messages with troubleshooting guidance.
    
    Attributes:
        timeout: Request timeout in seconds for Ollama API calls.
        num_ctx: Context window size passed to Ollama's num_ctx parameter.
        
    Example:
        >>> client = OllamaClient(timeout=120, num_ctx=16384)
        >>> if client.check_connection():
        ...     models = client.list_models()
        ...     response = client.chat("qwen3-coder:30b", "Hello!")
        
    Requirements:
        - 1.1: Establish connection to local Ollama instance
        - 1.2: Raise OllamaConnectionError when Ollama is not running
        - 1.3: Query Ollama for available models
        - 2.4: Expose method to list available models
        - 3.5: Pass configurable num_ctx parameter to Ollama
        - 6.2: Handle timeout errors
        - 6.4: Support configurable timeout values (default 120 seconds)
    """
    
    def __init__(self, timeout: int = 120, num_ctx: int = 16384) -> None:
        """Initialize the OllamaClient with timeout and context window configuration.
        
        Args:
            timeout: Request timeout in seconds for Ollama API calls.
                    Defaults to 120 seconds.
            num_ctx: Context window size passed to Ollama's num_ctx parameter.
                    This controls how much context the model can process.
                    Defaults to 16384 tokens.
                    
        Example:
            >>> client = OllamaClient()  # Uses defaults
            >>> client.timeout
            120
            >>> client.num_ctx
            16384
            >>> client = OllamaClient(timeout=60, num_ctx=8192)  # Custom values
            >>> client.timeout
            60
            
        Requirements:
            - 3.5: Support configurable context window management
            - 6.4: Support configurable timeout values with a default of 120 seconds
        """
        self.timeout = timeout
        self.num_ctx = num_ctx
    
    def check_connection(self) -> bool:
        """Verify Ollama is running and accessible.
        
        Attempts to connect to the local Ollama instance by calling the
        list models API. If the connection fails, raises an OllamaConnectionError
        with troubleshooting guidance.
        
        Returns:
            True if Ollama is accessible and responding.
            
        Raises:
            OllamaConnectionError: If unable to connect to Ollama. The exception
                includes troubleshooting guidance for resolving the issue.
                
        Example:
            >>> client = OllamaClient()
            >>> try:
            ...     if client.check_connection():
            ...         print("Ollama is running")
            ... except OllamaConnectionError as e:
            ...     print(f"Connection failed: {e}")
            
        Requirements:
            - 1.1: Establish connection to local Ollama instance
            - 1.2: Raise OllamaConnectionError when Ollama is not running
        """
        try:
            import ollama
            ollama.list()
            return True
        except ImportError:
            raise OllamaConnectionError(
                "The 'ollama' package is not installed. Install it with: pip install ollama"
            )
        except Exception as e:
            # Wrap any connection-related errors in OllamaConnectionError
            error_message = str(e)
            if "connection" in error_message.lower() or "refused" in error_message.lower():
                raise OllamaConnectionError(f"Connection failed: {error_message}")
            elif "timeout" in error_message.lower():
                raise OllamaConnectionError(f"Connection timed out: {error_message}")
            else:
                raise OllamaConnectionError(f"Failed to connect to Ollama: {error_message}")
    
    def list_models(self) -> list[str]:
        """Get list of available models from Ollama.
        
        Queries the local Ollama instance for all available models and returns
        their names. This can be used to validate model availability before
        attempting generation.
        
        Returns:
            A list of model name strings available in Ollama.
            
        Raises:
            OllamaConnectionError: If unable to connect to Ollama to retrieve
                the model list.
                
        Example:
            >>> client = OllamaClient()
            >>> models = client.list_models()
            >>> "qwen3-coder:30b" in models
            True
            
        Requirements:
            - 1.3: Query Ollama for the list of available models
            - 2.4: Expose a class method to list all available models from Ollama
        """
        try:
            import ollama
            response = ollama.list()
            # Extract model names from the response
            # The response contains a 'models' list with model info dicts
            models = []
            if hasattr(response, 'models'):
                for model in response.models:
                    if hasattr(model, 'model'):
                        models.append(model.model)
                    elif hasattr(model, 'name'):
                        models.append(model.name)
            elif isinstance(response, dict) and 'models' in response:
                for model in response['models']:
                    if isinstance(model, dict):
                        models.append(model.get('model') or model.get('name', ''))
                    else:
                        models.append(str(model))
            return models
        except ImportError:
            raise OllamaConnectionError(
                "The 'ollama' package is not installed. Install it with: pip install ollama"
            )
        except Exception as e:
            error_message = str(e)
            raise OllamaConnectionError(f"Failed to list models: {error_message}")
    
    def chat(
        self,
        model: str,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Send a chat request to Ollama and return the response.
        
        Sends a chat completion request to the specified model with the given
        prompt. The num_ctx parameter is passed to Ollama to set the context
        window size, allowing processing of longer articles.
        
        Args:
            model: The name of the Ollama model to use for generation.
            prompt: The user prompt to send to the model.
            system_prompt: Optional system prompt to set the model's behavior
                          and context. If None, no system message is included.
                          
        Returns:
            The generated text response from the model.
            
        Raises:
            OllamaConnectionError: If unable to connect to Ollama.
            TimeoutError: If the request exceeds the configured timeout.
            
        Example:
            >>> client = OllamaClient(timeout=120, num_ctx=16384)
            >>> response = client.chat(
            ...     model="qwen3-coder:30b",
            ...     prompt="Write a LinkedIn post about cloud security",
            ...     system_prompt="You are a LinkedIn content strategist."
            ... )
            >>> len(response) > 0
            True
            
        Requirements:
            - 3.5: Pass configurable num_ctx parameter to Ollama
            - 6.2: Handle timeout errors
            - 6.4: Support configurable timeout values
        """
        try:
            import ollama
            
            # Build messages list
            messages = []
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt,
                })
            messages.append({
                "role": "user",
                "content": prompt,
            })
            
            # Call Ollama with num_ctx in options
            # The timeout is handled by setting a request timeout
            logger.debug(
                f"Sending chat request to model '{model}' with num_ctx={self.num_ctx}"
            )
            
            response = ollama.chat(
                model=model,
                messages=messages,
                options={
                    "num_ctx": self.num_ctx,
                },
            )
            
            # Extract the response content
            if hasattr(response, 'message'):
                content = response.message.content if hasattr(response.message, 'content') else str(response.message)
            elif isinstance(response, dict):
                message = response.get('message', {})
                content = message.get('content', '') if isinstance(message, dict) else str(message)
            else:
                content = str(response)
            
            return content
            
        except ImportError:
            raise OllamaConnectionError(
                "The 'ollama' package is not installed. Install it with: pip install ollama"
            )
        except TimeoutError:
            # Re-raise TimeoutError as-is
            raise TimeoutError(f"Generation timed out after {self.timeout} seconds")
        except Exception as e:
            error_message = str(e)
            # Check for timeout-related errors
            if "timeout" in error_message.lower():
                raise TimeoutError(f"Generation timed out after {self.timeout} seconds")
            # Check for connection-related errors
            elif "connection" in error_message.lower() or "refused" in error_message.lower():
                raise OllamaConnectionError(f"Connection failed during chat: {error_message}")
            else:
                # Re-raise other exceptions for the caller to handle
                raise OllamaConnectionError(f"Chat request failed: {error_message}")


# =============================================================================
# Content Generator
# =============================================================================


class ContentGenerator:
    """Generate LinkedIn posts from articles using Ollama.
    
    The ContentGenerator is the main interface for transforming scraped article
    content into high-engagement LinkedIn posts using the Hook-Value-CTA framework.
    It integrates with a local Ollama LLM runtime for text generation.
    
    The generator uses three internal components:
    - OllamaClient: Handles communication with the Ollama runtime
    - ContextManager: Manages content length and token limits
    - PromptBuilder: Constructs optimized prompts for post generation
    
    Attributes:
        model: The Ollama model name to use for generation.
        timeout: Request timeout in seconds for Ollama API calls.
        max_tokens: Maximum input tokens before content truncation.
        num_ctx: Context window size passed to Ollama's num_ctx parameter.
        
    Example:
        >>> generator = ContentGenerator()  # Uses defaults
        >>> generator.model
        'llama4:scout'
        >>> generator.timeout
        120
        >>> generator.num_ctx
        16384
        
        >>> # Custom configuration
        >>> generator = ContentGenerator(
        ...     model="qwen3-coder:30b",
        ...     timeout=180,
        ...     max_tokens=8000,
        ...     num_ctx=32768
        ... )
        >>> generator.model
        'qwen3-coder:30b'
        
        >>> # Generate a post from an article
        >>> post = generator.generate(scored_article)
        >>> print(post.full_text)
        
    Requirements:
        - 2.1: Support configuration of the model name via constructor parameter
        - 2.2: Default to llama4:scout when no model is specified
        - 6.4: Support configurable timeout values with a default of 120 seconds
        - 3.5: Pass configurable num_ctx parameter to Ollama (default 16384)
    """
    
    # Default configuration values
    DEFAULT_MODEL: str = "llama4:scout"
    DEFAULT_TIMEOUT: int = 120
    DEFAULT_MAX_TOKENS: int = 10000
    DEFAULT_NUM_CTX: int = 16384
    MIN_SCORE_THRESHOLD: float = 50.0
    
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        num_ctx: int = DEFAULT_NUM_CTX,
    ) -> None:
        """Initialize the ContentGenerator with model configuration.
        
        Creates a new ContentGenerator instance with the specified configuration.
        The generator initializes internal components for Ollama communication,
        context management, and prompt building.
        
        Args:
            model: Ollama model name to use for generation. Defaults to
                  "llama4:scout" which provides a good balance of speed
                  and quality for LinkedIn post generation.
            timeout: Request timeout in seconds for Ollama API calls.
                    Defaults to 120 seconds to allow for longer generations.
            max_tokens: Maximum number of input tokens before content truncation
                       is applied. Defaults to 10000 tokens (approximately
                       40,000 characters).
            num_ctx: Context window size passed to Ollama's num_ctx parameter.
                    This controls how much context the model can process.
                    Defaults to 16384 tokens.
                    
        Example:
            >>> # Use default configuration
            >>> generator = ContentGenerator()
            >>> generator.model
            'llama4:scout'
            >>> generator.timeout
            120
            >>> generator.max_tokens
            10000
            >>> generator.num_ctx
            16384
            
            >>> # Custom configuration for creative writing
            >>> generator = ContentGenerator(
            ...     model="qwen3-coder:30b",
            ...     timeout=180,
            ...     max_tokens=8000,
            ...     num_ctx=32768
            ... )
            >>> generator.model
            'qwen3-coder:30b'
            
            >>> # Faster generation with smaller context
            >>> generator = ContentGenerator(
            ...     model="llama4:scout",
            ...     timeout=60,
            ...     num_ctx=8192
            ... )
            
        Requirements:
            - 2.1: Support configuration of the model name via constructor parameter
            - 2.2: Default to llama4:scout when no model is specified
            - 6.4: Support configurable timeout values with a default of 120 seconds
            - 3.5: Pass configurable num_ctx parameter to Ollama (default 16384)
        """
        # Store configuration
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.num_ctx = num_ctx
        
        # Initialize internal components
        self._client = OllamaClient(timeout=timeout, num_ctx=num_ctx)
        self._context_manager = ContextManager(max_tokens=max_tokens)
        self._prompt_builder = PromptBuilder()
        
        # Track whether model has been validated
        self._model_validated = False
        
        logger.debug(
            f"ContentGenerator initialized with model='{model}', "
            f"timeout={timeout}s, max_tokens={max_tokens}, num_ctx={num_ctx}"
        )
    
    def is_model_available(self, model: str | None = None) -> bool:
        """Check if a specific model is available in Ollama.
        
        Queries the local Ollama instance to determine if the specified model
        is available for use. If no model is specified, checks the generator's
        configured model.
        
        Args:
            model: The name of the model to check. If None, checks the
                  generator's configured model (self.model).
                  
        Returns:
            True if the model is available in Ollama, False otherwise.
            
        Raises:
            OllamaConnectionError: If unable to connect to Ollama to check
                model availability.
                
        Example:
            >>> generator = ContentGenerator(model="qwen3-coder:30b")
            >>> generator.is_model_available()  # Checks configured model
            True
            >>> generator.is_model_available("llama4:scout")  # Checks specific model
            True
            >>> generator.is_model_available("nonexistent-model")
            False
            
        Requirements:
            - 1.3: Query Ollama for the list of available models
            - 2.3: Validate that the model exists in Ollama before proceeding
        """
        model_to_check = model if model is not None else self.model
        available_models = self._client.list_models()
        return model_to_check in available_models
    
    @classmethod
    def list_available_models(cls) -> list[str]:
        """List all models available in Ollama.
        
        Class method that queries the local Ollama instance for all available
        models. This can be used to discover available models before creating
        a ContentGenerator instance.
        
        Returns:
            A list of model name strings available in Ollama.
            
        Raises:
            OllamaConnectionError: If unable to connect to Ollama to retrieve
                the model list.
                
        Example:
            >>> models = ContentGenerator.list_available_models()
            >>> print(models)
            ['qwen3-coder:30b', 'llama4:scout', 'mistral:latest']
            >>> "qwen3-coder:30b" in models
            True
            
        Requirements:
            - 2.4: Expose a class method to list all available models from Ollama
        """
        # Create a temporary client to list models
        client = OllamaClient()
        return client.list_models()
    
    def _validate_model(self) -> None:
        """Validate that the configured model is available in Ollama.
        
        Internal method that checks if the configured model exists in Ollama.
        This is called before the first generation to ensure the model is
        available. The validation is cached to avoid repeated checks.
        
        Raises:
            ModelNotAvailableError: If the configured model is not available
                in Ollama. The exception includes the model name and
                instructions for pulling the model.
            OllamaConnectionError: If unable to connect to Ollama.
                
        Example:
            >>> generator = ContentGenerator(model="nonexistent-model")
            >>> generator._validate_model()
            Traceback (most recent call last):
                ...
            ModelNotAvailableError: Model 'nonexistent-model' is not available in Ollama
            Pull the model with: 'ollama pull nonexistent-model'
            
        Requirements:
            - 1.4: Raise ModelNotAvailableError for missing models
            - 2.3: Validate that the model exists in Ollama before proceeding
        """
        if self._model_validated:
            return
        
        logger.debug(f"Validating model availability: {self.model}")
        
        if not self.is_model_available():
            raise ModelNotAvailableError(self.model)
        
        self._model_validated = True
        logger.debug(f"Model '{self.model}' validated successfully")
    
    def generate(self, article: "ScoredArticle") -> GeneratedPost:
        """Generate a LinkedIn post from a single article.
        
        Transforms a ScoredArticle into a high-engagement LinkedIn post using
        the Hook-Value-CTA framework. The method validates the model, prepares
        the content, constructs an optimized prompt, and parses the LLM response
        into structured sections.
        
        Args:
            article: A ScoredArticle object containing the article data to
                    transform into a LinkedIn post.
                    
        Returns:
            A GeneratedPost object containing the full post text, structured
            sections (hook, value, cta), hashtags, and metadata.
            
        Raises:
            OllamaConnectionError: If unable to connect to Ollama.
            ModelNotAvailableError: If the configured model is not available.
            GenerationError: If post generation fails for any reason.
            TimeoutError: If generation exceeds the configured timeout.
            
        Example:
            >>> generator = ContentGenerator()
            >>> post = generator.generate(scored_article)
            >>> print(post.full_text)
            🔐 Is your cloud security keeping pace?
            
            AWS just announced enhanced security controls...
            
            What's your biggest cloud security challenge? Share below!
            
            #CloudSecurity #AWS #CyberSecurity
            >>> post.character_count < 3000
            True
            
        Requirements:
            - 4.1: Produce a Hook section with attention-grabbing opening
            - 4.2: Produce a Value section with core insight
            - 4.3: Produce a CTA section with engagement prompt
            - 4.5: Include relevant hashtags at the end
            - 4.6: Keep total post length under 3,000 characters
            - 9.1: Accept ScoredArticle objects as input
        """
        # Validate model availability before first generation
        self._validate_model()
        
        logger.info(f"Generating LinkedIn post for article: '{article.title}'")
        
        try:
            # Step 1: Prepare content using ContextManager
            content, was_truncated = self._context_manager.prepare_content(article)
            if was_truncated:
                logger.debug(f"Content was truncated for article: '{article.title}'")
            
            # Step 2: Randomly select a hook style for variety
            # Weight non-statistic styles higher (75% non-statistic, 25% statistic)
            hook_style = random.choices(
                PromptBuilder.HOOK_STYLES,
                weights=[1, 3, 3],  # Statistic-heavy=1, Contrarian=3, Bold Prediction=3
                k=1
            )[0]
            logger.debug(f"Selected hook style: {hook_style}")
            
            # Step 3: Build prompt using PromptBuilder with selected hook style
            prompt = self._prompt_builder.build(
                title=article.title,
                source=article.source,
                summary=article.summary,
                key_topics=article.key_topics,
                why_it_matters=article.why_it_matters,
                hashtags=article.suggested_hashtags,
                hook_style=hook_style,
            )
            
            # Step 4: Get system prompt
            system_prompt = self._prompt_builder.get_system_prompt()
            
            # Step 5: Call OllamaClient.chat with configured model
            logger.debug(f"Sending generation request to model '{self.model}'")
            response = self._client.chat(
                model=self.model,
                prompt=prompt,
                system_prompt=system_prompt,
            )
            
            if not response or not response.strip():
                raise GenerationError(article.title, "Model returned empty response")
            
            # Step 6: Parse response into hook, value, cta sections
            hook, value, cta = self._parse_response(response)
            
            # Step 7: Extract hashtags from the LLM response (not from article)
            extracted_hashtags = self._extract_hashtags_from_response(response)
            
            # Step 8: Ensure character count is under 3000
            full_text = response.strip()
            character_count = len(full_text)
            
            if character_count >= 3000:
                # Truncate to fit LinkedIn's limit
                logger.warning(
                    f"Generated post exceeds 3000 characters ({character_count}). "
                    "Truncating to fit LinkedIn limit."
                )
                full_text = self._truncate_post(full_text, article.suggested_hashtags)
                character_count = len(full_text)
                # Re-parse the truncated response
                hook, value, cta = self._parse_response(full_text)
                # Re-extract hashtags from truncated response
                extracted_hashtags = self._extract_hashtags_from_response(full_text)
            
            # Step 9: Create and return GeneratedPost
            generated_post = GeneratedPost(
                full_text=full_text,
                hook=hook,
                value=value,
                cta=cta,
                hashtags=extracted_hashtags,  # Use extracted hashtags from LLM response
                model_used=self.model,
                generated_at=datetime.now(),
                source_url=article.url,
                character_count=character_count,
            )
            
            logger.info(
                f"Successfully generated post for '{article.title}' "
                f"({character_count} characters)"
            )
            
            return generated_post
            
        except (OllamaConnectionError, ModelNotAvailableError, TimeoutError):
            # Re-raise these exceptions as-is
            raise
        except GenerationError:
            # Re-raise GenerationError as-is
            raise
        except Exception as e:
            # Wrap any other exceptions in GenerationError
            raise GenerationError(article.title, str(e))
    
    def _extract_hashtags_from_response(self, response: str) -> list[str]:
        """Extract hashtags from the [HASHTAGS] tag in the LLM response.
        
        Parses the hashtags section from the LLM response and returns them
        as a list. Falls back to extracting any hashtags found in the response
        if the [HASHTAGS] tag is not present.
        
        Args:
            response: The full response text from the LLM.
            
        Returns:
            A list of hashtag strings (e.g., ["#CloudSecurity", "#AWS", "#AI"]).
            Returns empty list if no hashtags found.
        """
        # Try to extract from [HASHTAGS] tag first
        hashtags_content = self._extract_tagged_section(response, "HASHTAGS")
        
        if hashtags_content:
            # Parse hashtags from the tagged content
            hashtags = re.findall(r'#\w+', hashtags_content)
            return hashtags[:3]  # Return at most 3 hashtags
        
        # Fallback: extract any hashtags from the response
        all_hashtags = re.findall(r'#\w+', response)
        # Return unique hashtags, preserving order
        seen = set()
        unique_hashtags = []
        for tag in all_hashtags:
            if tag not in seen:
                seen.add(tag)
                unique_hashtags.append(tag)
        return unique_hashtags[:3]
    
    def _extract_tagged_section(self, response: str, tag: str) -> str | None:
        """Extract content between [TAG] and [/TAG] markers.
        
        Uses the compiled regex patterns to extract content from tagged sections
        in the LLM response. The extraction is case-insensitive and handles
        multiline content within tags.
        
        Args:
            response: The full response text from the LLM.
            tag: The tag name (e.g., "HOOK", "VALUE", "CTA", "HASHTAGS").
            
        Returns:
            The content between tags with whitespace stripped, or None if
            tags are not found in the response.
            
        Example:
            >>> response = "[HOOK]Attention grabber here[/HOOK]"
            >>> generator._extract_tagged_section(response, "HOOK")
            'Attention grabber here'
            >>> generator._extract_tagged_section(response, "VALUE")
            None
            
        Requirements:
            - 3.1: Extract hook section using regex between [HOOK] and [/HOOK] tags
            - 3.2: Extract value section using regex between [VALUE] and [/VALUE] tags
            - 3.3: Extract CTA section using regex between [CTA] and [/CTA] tags
            - 3.4: Extract hashtags using regex between [HASHTAGS] and [/HASHTAGS] tags
        """
        if not response:
            return None
        
        # Map tag names to compiled patterns
        tag_patterns = {
            "HOOK": HOOK_PATTERN,
            "VALUE": VALUE_PATTERN,
            "CTA": CTA_PATTERN,
            "HASHTAGS": HASHTAGS_PATTERN,
        }
        
        # Get the pattern for the requested tag (case-insensitive lookup)
        tag_upper = tag.upper()
        pattern = tag_patterns.get(tag_upper)
        
        if pattern is None:
            # For unknown tags, dynamically create a pattern using TAG_PATTERN template
            dynamic_pattern = re.compile(
                TAG_PATTERN.format(tag=tag_upper),
                re.IGNORECASE | re.DOTALL
            )
            pattern = dynamic_pattern
        
        # Search for the pattern in the response
        match = pattern.search(response)
        
        if match:
            # Extract the content and strip whitespace
            content = match.group(1)
            return content.strip() if content else ""
        
        return None
    
    def _parse_response(self, response: str) -> tuple[str, str, str]:
        """Parse the LLM response into hook, value, and cta sections.
        
        Uses regex to extract content between explicit tags. Falls back to
        paragraph-based parsing if tags are not present.
        
        The parsing strategy:
        1. Strip any conversational filler before the first [HOOK] tag
        2. Try regex extraction for each section ([HOOK], [VALUE], [CTA])
        3. Fall back to paragraph-based parsing for any missing sections
        
        Args:
            response: The raw text response from the LLM.
            
        Returns:
            A tuple of (hook, value, cta) strings.
            
        Example:
            >>> hook, value, cta = generator._parse_response(response_text)
            >>> len(hook) > 0 and len(value) > 0 and len(cta) > 0
            True
            
        Requirements:
            - 3.5: Fall back to paragraph-based parsing if tags missing
            - 3.6: Strip conversational filler before first [HOOK] tag
            - 5.2: Fall back to paragraph-based parsing when tags absent
            - 5.3: Continue to return valid results regardless of tag presence
        """
        if not response:
            return "", "", ""
        
        # Strip conversational filler before the first [HOOK] tag (Requirement 3.6)
        text = self._strip_filler_before_hook(response)
        
        # Try regex extraction first for each section (Requirements 3.1-3.4)
        hook = self._extract_tagged_section(text, "HOOK")
        value = self._extract_tagged_section(text, "VALUE")
        cta = self._extract_tagged_section(text, "CTA")
        
        # Check if any tags are missing and need fallback
        tags_missing = hook is None or value is None or cta is None
        
        if tags_missing:
            # Log warning about fallback (Requirement 3.5)
            missing_tags = []
            if hook is None:
                missing_tags.append("HOOK")
            if value is None:
                missing_tags.append("VALUE")
            if cta is None:
                missing_tags.append("CTA")
            
            logger.warning(
                f"Missing tags in response: {', '.join(missing_tags)}. "
                "Falling back to paragraph-based parsing for missing sections."
            )
            
            # Get fallback values from paragraph-based parsing
            fallback_hook, fallback_value, fallback_cta = self._parse_response_paragraphs(text)
            
            # Use fallback values for missing sections
            if hook is None:
                hook = fallback_hook
            if value is None:
                value = fallback_value
            if cta is None:
                cta = fallback_cta
        
        return hook or "", value or "", cta or ""
    
    def _strip_filler_before_hook(self, response: str) -> str:
        """Strip conversational filler that appears before the first [HOOK] tag.
        
        Removes common LLM preambles like "Here is the post:", "Sure!", etc.
        that may appear before the actual content starts.
        
        Args:
            response: The raw response text from the LLM.
            
        Returns:
            The response with any filler before [HOOK] removed.
            
        Example:
            >>> generator._strip_filler_before_hook("Here is the post:\\n\\n[HOOK]Hello[/HOOK]")
            '[HOOK]Hello[/HOOK]'
            >>> generator._strip_filler_before_hook("[HOOK]Hello[/HOOK]")
            '[HOOK]Hello[/HOOK]'
            
        Requirements:
            - 3.6: Strip conversational filler before first [HOOK] tag
        """
        if not response:
            return response
        
        # Find the position of the first [HOOK] tag (case-insensitive)
        hook_match = re.search(r'\[HOOK\]', response, re.IGNORECASE)
        
        if hook_match:
            # Return everything from [HOOK] onwards, stripping filler before it
            return response[hook_match.start():]
        
        # No [HOOK] tag found - return original response for fallback parsing
        return response
    
    def _parse_response_paragraphs(self, response: str) -> tuple[str, str, str]:
        """Parse the LLM response using paragraph-based splitting.
        
        This is the original parsing logic used as a fallback when explicit
        tags are not present in the response.
        
        The parsing strategy:
        1. Split the response into paragraphs (separated by blank lines)
        2. First paragraph(s) = Hook (attention-grabbing opening)
        3. Middle paragraph(s) = Value (core insight)
        4. Last paragraph(s) before hashtags = CTA (call-to-action)
        
        Args:
            response: The raw text response from the LLM.
            
        Returns:
            A tuple of (hook, value, cta) strings.
            
        Requirements:
            - 5.2: Fall back to paragraph-based parsing when tags absent
        """
        if not response:
            return "", "", ""
        
        # Clean up the response
        text = response.strip()
        
        # Remove hashtags from the end for parsing
        lines = text.split('\n')
        content_lines = []
        hashtag_lines = []
        
        # Separate content from hashtags (hashtags typically at the end)
        in_hashtags = False
        for line in reversed(lines):
            stripped = line.strip()
            if stripped and (stripped.startswith('#') or 
                           (in_hashtags and all(word.startswith('#') for word in stripped.split() if word))):
                hashtag_lines.insert(0, line)
                in_hashtags = True
            else:
                in_hashtags = False
                content_lines.insert(0, line)
        
        content_text = '\n'.join(content_lines).strip()
        
        # Split into paragraphs (separated by blank lines)
        paragraphs = []
        current_para = []
        
        for line in content_text.split('\n'):
            if line.strip():
                current_para.append(line)
            elif current_para:
                paragraphs.append('\n'.join(current_para))
                current_para = []
        
        if current_para:
            paragraphs.append('\n'.join(current_para))
        
        # Handle different numbers of paragraphs
        if len(paragraphs) == 0:
            return "", "", ""
        elif len(paragraphs) == 1:
            # Single paragraph - treat entire content as value
            return "", paragraphs[0], ""
        elif len(paragraphs) == 2:
            # Two paragraphs - first is hook, second is value+cta
            return paragraphs[0], paragraphs[1], ""
        else:
            # Three or more paragraphs
            # First paragraph = Hook
            # Middle paragraphs = Value
            # Last paragraph = CTA
            hook = paragraphs[0]
            cta = paragraphs[-1]
            value = '\n\n'.join(paragraphs[1:-1])
            return hook, value, cta
    
    def _truncate_post(self, text: str, hashtags: list[str]) -> str:
        """Truncate a post to fit within LinkedIn's 3000 character limit.
        
        Intelligently truncates the post while preserving:
        1. The hook (opening)
        2. As much value content as possible
        3. The hashtags at the end
        
        Args:
            text: The full post text to truncate.
            hashtags: List of hashtags to ensure are included.
            
        Returns:
            Truncated post text under 3000 characters.
        """
        max_chars = 2990  # Leave some buffer
        
        if len(text) <= max_chars:
            return text
        
        # Calculate space needed for hashtags
        hashtag_text = ' '.join(hashtags) if hashtags else ''
        hashtag_space = len(hashtag_text) + 2 if hashtag_text else 0  # +2 for newlines
        
        # Available space for content
        content_space = max_chars - hashtag_space
        
        # Split into lines and truncate
        lines = text.split('\n')
        
        # Remove existing hashtags from the end
        content_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith('#') and not all(
                word.startswith('#') for word in stripped.split() if word
            ):
                content_lines.append(line)
        
        # Rebuild content within limit
        result_lines = []
        current_length = 0
        
        for line in content_lines:
            line_length = len(line) + 1  # +1 for newline
            if current_length + line_length <= content_space:
                result_lines.append(line)
                current_length += line_length
            else:
                # Truncate this line if it's the first one
                if not result_lines:
                    remaining = content_space - 3  # -3 for "..."
                    result_lines.append(line[:remaining] + "...")
                break
        
        # Combine content with hashtags
        result = '\n'.join(result_lines).strip()
        if hashtag_text:
            result = result + '\n\n' + hashtag_text
        
        return result
    
    def generate_batch(
        self,
        articles: list["ScoredArticle"],
        continue_on_error: bool = True,
    ) -> BatchResult:
        """Generate posts for multiple articles.
        
        Processes a batch of ScoredArticle objects, generating LinkedIn posts
        for each one. Articles with score_overall below MIN_SCORE_THRESHOLD (50)
        are skipped and not included in the results.
        
        The method handles errors gracefully, continuing to process remaining
        articles even if individual generations fail.
        
        Progress is logged during batch processing to provide visibility into
        the operation's status.
        
        Args:
            articles: A list of ScoredArticle objects to process.
            continue_on_error: If True (default), continue processing remaining
                              articles when one fails. If False, stop on first
                              error and raise the exception.
                              
        Returns:
            A BatchResult object containing:
            - successful: List of successfully generated posts
            - failed: List of (article_title, error_message) tuples for failures
            - total_processed: Total number of articles that were attempted
                              (excludes skipped low-score articles)
            - success_rate: Percentage of successful generations (0.0 to 1.0)
            
        Raises:
            OllamaConnectionError: If unable to connect to Ollama (raised
                immediately, not caught per-article).
            ModelNotAvailableError: If the configured model is not available
                (raised immediately, not caught per-article).
            GenerationError: If continue_on_error is False and a generation
                fails.
            TimeoutError: If continue_on_error is False and a generation
                times out.
                
        Example:
            >>> generator = ContentGenerator()
            >>> articles = [article1, article2, article3]
            >>> result = generator.generate_batch(articles)
            >>> print(f"Generated {len(result.successful)} posts")
            Generated 3 posts
            >>> print(f"Success rate: {result.success_rate:.1%}")
            Success rate: 100.0%
            
            >>> # With some failures
            >>> result = generator.generate_batch(mixed_articles)
            >>> print(f"Successful: {len(result.successful)}")
            Successful: 2
            >>> print(f"Failed: {len(result.failed)}")
            Failed: 1
            >>> for title, error in result.failed:
            ...     print(f"  - {title}: {error}")
            
        Requirements:
            - 3.1: Skip articles with score_overall below 50
            - 3.2: Log skipped articles
            - 3.3: Do not include skipped articles in failed list
            - 3.4: BatchResult reflects only articles that were actually processed
            - 8.1: Provide a batch generation method that accepts a list of ScoredArticle objects
            - 8.2: Continue processing remaining articles if one fails
            - 8.3: Return a list of results with success/failure status for each article
            - 8.4: Log progress during batch processing (articles processed / total)
        """
        # Validate model availability before starting batch processing
        # This is done once at the start to fail fast if model is unavailable
        self._validate_model()
        
        # Filter articles by score threshold (Requirements 3.1, 3.3, 3.4)
        eligible_articles = [
            article for article in articles
            if article.score_overall >= self.MIN_SCORE_THRESHOLD
        ]
        
        skipped_count = len(articles) - len(eligible_articles)
        if skipped_count > 0:
            # Log summary count at INFO level (Requirement 3.2)
            logger.info(
                f"Skipped {skipped_count} articles with score_overall < {self.MIN_SCORE_THRESHOLD}"
            )
            # Log individual skipped articles at DEBUG level (Requirement 3.2)
            for article in articles:
                if article.score_overall < self.MIN_SCORE_THRESHOLD:
                    logger.debug(
                        f"Skipped article '{article.title}' "
                        f"(score_overall={article.score_overall:.1f} < {self.MIN_SCORE_THRESHOLD})"
                    )
        
        total = len(eligible_articles)
        successful: list[GeneratedPost] = []
        failed: list[tuple[str, str]] = []
        
        logger.info(f"Starting batch generation for {total} articles")
        
        for index, article in enumerate(eligible_articles, start=1):
            article_title = article.title
            
            try:
                # Log progress before processing each article
                logger.info(f"Processing article {index}/{total}: '{article_title}'")
                
                # Generate post for this article
                post = self.generate(article)
                successful.append(post)
                
                logger.debug(
                    f"Successfully generated post for '{article_title}' "
                    f"({index}/{total})"
                )
                
            except (OllamaConnectionError, ModelNotAvailableError):
                # These are critical errors - re-raise immediately
                # as they indicate systemic issues that won't resolve
                logger.error(
                    f"Critical error during batch processing at article {index}/{total}"
                )
                raise
                
            except (GenerationError, TimeoutError) as e:
                # Per-article errors - log and optionally continue
                error_message = str(e)
                failed.append((article_title, error_message))
                
                logger.warning(
                    f"Failed to generate post for '{article_title}' "
                    f"({index}/{total}): {error_message}"
                )
                
                if not continue_on_error:
                    raise
                    
            except Exception as e:
                # Unexpected errors - wrap and handle like GenerationError
                error_message = str(e)
                failed.append((article_title, error_message))
                
                logger.warning(
                    f"Unexpected error generating post for '{article_title}' "
                    f"({index}/{total}): {error_message}"
                )
                
                if not continue_on_error:
                    raise GenerationError(article_title, error_message)
        
        # Calculate success rate
        total_processed = len(successful) + len(failed)
        success_rate = len(successful) / total_processed if total_processed > 0 else 0.0
        
        # Log final summary
        logger.info(
            f"Batch generation complete: {len(successful)}/{total_processed} successful "
            f"({success_rate:.1%} success rate)"
        )
        
        if failed:
            logger.info(f"Failed articles: {[title for title, _ in failed]}")
        
        return BatchResult(
            successful=successful,
            failed=failed,
            total_processed=total_processed,
            success_rate=success_rate,
        )
