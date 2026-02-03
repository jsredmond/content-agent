# Design Document: Prompt Builder Enhancements

## Overview

This design document describes enhancements to the PromptBuilder class and ContentGenerator in `src/engines/generator.py`. The changes improve LinkedIn post quality by:

1. Instructing the LLM to use varied hook styles instead of defaulting to questions
2. Limiting hashtag output to exactly 3 high-relevance tags
3. Adding a validation gate to skip low-scoring articles (score_overall < 50)
4. Updating the default model from "qwen3-coder:30b" to "llama4:scout" for better creative writing

## Architecture

The enhancements modify two existing classes in `src/engines/generator.py`:

```
┌─────────────────────────────────────────────────────────────┐
│                    ContentGenerator                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ DEFAULT_MODEL = "llama4:scout"  (changed)           │    │
│  │ MIN_SCORE_THRESHOLD = 50        (new)               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  generate_batch(articles) ──► Filter by score_overall >= 50 │
│                           ──► Process remaining articles     │
│                           ──► Return BatchResult             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    PromptBuilder                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ HOOK_VALUE_CTA_TEMPLATE (updated)                   │    │
│  │   - Hook styles: Bold Statement, Contrarian View,   │    │
│  │     Fact-Driven                                     │    │
│  │   - Instruction to avoid question-only hooks        │    │
│  │   - Hashtag limit: exactly 3                        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### PromptBuilder Changes

The `HOOK_VALUE_CTA_TEMPLATE` class attribute will be updated to include:

```python
HOOK_VALUE_CTA_TEMPLATE: str = """Create a LinkedIn post about the following article using the Hook-Value-CTA framework:

ARTICLE INFORMATION:
- Title: {title}
- Source: {source}
- Summary: {summary}
- Key Topics: {key_topics}
- Why It Matters: {why_it_matters}

FRAMEWORK REQUIREMENTS:

1. HOOK (1-2 sentences): Start with ONE of these attention-grabbing techniques:
   - Bold Statement: A confident, declarative opening
   - Contrarian View: Challenge conventional wisdom
   - Fact-Driven: Lead with a compelling statistic or data point
   
   IMPORTANT: Avoid starting with a question. Vary your hook style.

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

HASHTAG REQUIREMENT:
You MUST include exactly 3 hashtags - no more, no fewer. Choose the 3 most relevant hashtags from the provided list.

{security_framing}
OUTPUT FORMAT:
Return ONLY the post text, ready to copy-paste to LinkedIn."""
```

### ContentGenerator Changes

#### New Class Constant

```python
class ContentGenerator:
    DEFAULT_MODEL: str = "llama4:scout"  # Changed from "qwen3-coder:30b"
    MIN_SCORE_THRESHOLD: float = 50.0    # New constant
```

#### Updated generate_batch Method

```python
def generate_batch(
    self,
    articles: list["ScoredArticle"],
    continue_on_error: bool = True,
) -> BatchResult:
    """Generate posts for multiple articles.
    
    Articles with score_overall below MIN_SCORE_THRESHOLD (50) are skipped
    and not included in the results.
    """
    # Validate model availability
    self._validate_model()
    
    # Filter articles by score threshold
    eligible_articles = [
        article for article in articles 
        if article.score_overall >= self.MIN_SCORE_THRESHOLD
    ]
    
    skipped_count = len(articles) - len(eligible_articles)
    if skipped_count > 0:
        logger.info(
            f"Skipped {skipped_count} articles with score_overall < {self.MIN_SCORE_THRESHOLD}"
        )
        for article in articles:
            if article.score_overall < self.MIN_SCORE_THRESHOLD:
                logger.debug(
                    f"Skipped article '{article.title}' "
                    f"(score_overall={article.score_overall:.1f} < {self.MIN_SCORE_THRESHOLD})"
                )
    
    # Process eligible articles (rest of existing logic)
    # ...
```

## Data Models

No new data models are required. The existing `BatchResult` dataclass remains unchanged but will only reflect articles that were actually processed (not skipped).

```python
@dataclass
class BatchResult:
    successful: list[GeneratedPost]
    failed: list[tuple[str, str]]  # (article_title, error_message)
    total_processed: int           # Only counts articles that were attempted
    success_rate: float            # successful / total_processed
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Hook Styles Present in Prompt

*For any* article input to PromptBuilder.build(), the resulting prompt SHALL contain all three hook style names ("Bold Statement", "Contrarian View", "Fact-Driven") with their corresponding descriptions ("A confident, declarative opening", "Challenge conventional wisdom", "Lead with a compelling statistic or data point").

**Validates: Requirements 1.1, 1.3, 1.4, 1.5**

### Property 2: Avoid Question Instruction Present

*For any* article input to PromptBuilder.build(), the resulting prompt SHALL contain an instruction to avoid starting with a question.

**Validates: Requirements 1.2**

### Property 3: Hashtag Limit Instruction Present

*For any* article input to PromptBuilder.build(), the resulting prompt SHALL contain an instruction specifying exactly 3 hashtags must be included in the output.

**Validates: Requirements 2.1, 2.2, 2.3**

### Property 4: Validation Gate Filters Low-Score Articles

*For any* list of ScoredArticle objects passed to generate_batch(), articles with score_overall < 50 SHALL NOT be processed by the LLM, and the BatchResult.total_processed SHALL equal only the count of articles with score_overall >= 50 that were attempted.

**Validates: Requirements 3.1, 3.3, 3.4**

### Property 5: Skip Logging for Low-Score Articles

*For any* article with score_overall < 50 in a batch, the system SHALL emit a log message indicating the article was skipped due to low score.

**Validates: Requirements 3.2**

## Error Handling

### Validation Gate Behavior

- Articles below the score threshold are silently filtered before processing
- Skipped articles are logged at DEBUG level with their score
- A summary count of skipped articles is logged at INFO level
- Skipped articles do NOT appear in `BatchResult.failed`
- `BatchResult.total_processed` only counts articles that were actually sent to the LLM

### Existing Error Handling (Unchanged)

- `OllamaConnectionError`: Raised immediately, stops batch processing
- `ModelNotAvailableError`: Raised immediately, stops batch processing
- `GenerationError`: Per-article, logged and added to `failed` list
- `TimeoutError`: Per-article, logged and added to `failed` list

## Testing Strategy

### Property-Based Tests (Hypothesis)

Each correctness property will be implemented as a property-based test with minimum 100 iterations:

| Property | Test Class | Description |
|----------|------------|-------------|
| 1 | `TestHookStylesPresent` | Verify all hook styles and descriptions in prompt |
| 2 | `TestAvoidQuestionInstruction` | Verify avoid-question instruction in prompt |
| 3 | `TestHashtagLimitInstruction` | Verify exactly-3-hashtags instruction in prompt |
| 4 | `TestValidationGateFiltering` | Verify low-score articles are filtered |
| 5 | `TestSkipLogging` | Verify log messages for skipped articles |

### Unit Tests

Unit tests will cover specific examples and edge cases:

- Default model is "llama4:scout"
- Custom model configuration still works
- Boundary case: article with score_overall = 50 (should be processed)
- Boundary case: article with score_overall = 49.9 (should be skipped)
- Empty article list handling
- All articles below threshold handling

### Test Configuration

```python
from hypothesis import given, settings, strategies as st

@given(article=scored_article_strategy())
@settings(max_examples=100)
def test_property_name(self, article):
    """Feature: prompt-builder-enhancements, Property N: Property Title
    
    **Validates: Requirements X.Y**
    """
    # Test implementation
```
