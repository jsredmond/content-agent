# Requirements Document

## Introduction

This feature improves the LinkedIn post generator's response parsing by introducing explicit output tags and updating hook style names. The current paragraph-based parsing is fragile and can fail when the LLM adds conversational filler like "Here is the post:". This update introduces explicit tags ([HOOK], [VALUE], [CTA], [HASHTAGS]) for reliable parsing and updates hook styles to "Statistic-heavy", "Contrarian", and "Bold Prediction" for feed variety.

## Glossary

- **Generator**: The ContentGenerator class in `src/engines/generator.py` that produces LinkedIn posts from article content
- **PromptBuilder**: The class responsible for constructing prompts sent to the LLM
- **System_Prompt**: The base instructions sent to the LLM defining audience, tone, and output format
- **Response_Parser**: The `_parse_response` method that extracts structured sections from LLM output
- **Hook**: The attention-grabbing opening section of a LinkedIn post
- **Value**: The core insight or takeaway section of a LinkedIn post
- **CTA**: The call-to-action section that prompts engagement
- **Explicit_Tags**: Structured markers ([HOOK], [VALUE], [CTA], [HASHTAGS]) used to delimit output sections
- **Conversational_Filler**: Unwanted preamble text like "Here is the post:" that the LLM may add

## Requirements

### Requirement 1: Forbid Conversational Filler in System Prompt

**User Story:** As a content creator, I want the LLM to output only the post content without conversational filler, so that parsing is reliable and consistent.

#### Acceptance Criteria

1. THE System_Prompt SHALL include an explicit instruction forbidding conversational filler such as "Here is the post:", "Sure!", or similar preambles
2. THE System_Prompt SHALL instruct the model to begin output immediately with the [HOOK] tag
3. WHEN the Generator sends a prompt to the LLM, THE prompt SHALL contain the no-filler instruction

### Requirement 2: Explicit Tag Format in Output

**User Story:** As a developer, I want the LLM output to use explicit tags for each section, so that parsing is deterministic and robust.

#### Acceptance Criteria

1. THE System_Prompt SHALL instruct the model to wrap the hook section with [HOOK] and [/HOOK] tags
2. THE System_Prompt SHALL instruct the model to wrap the value section with [VALUE] and [/VALUE] tags
3. THE System_Prompt SHALL instruct the model to wrap the CTA section with [CTA] and [/CTA] tags
4. THE System_Prompt SHALL instruct the model to wrap hashtags with [HASHTAGS] and [/HASHTAGS] tags
5. THE PromptBuilder SHALL include the tag format instructions in every generated prompt

### Requirement 3: Regex-Based Response Parsing

**User Story:** As a developer, I want the response parser to use regex extraction instead of paragraph splitting, so that parsing is reliable regardless of LLM formatting variations.

#### Acceptance Criteria

1. WHEN the Response_Parser receives LLM output, THE Response_Parser SHALL extract the hook section using regex to find content between [HOOK] and [/HOOK] tags
2. WHEN the Response_Parser receives LLM output, THE Response_Parser SHALL extract the value section using regex to find content between [VALUE] and [/VALUE] tags
3. WHEN the Response_Parser receives LLM output, THE Response_Parser SHALL extract the CTA section using regex to find content between [CTA] and [/CTA] tags
4. WHEN the Response_Parser receives LLM output, THE Response_Parser SHALL extract hashtags using regex to find content between [HASHTAGS] and [/HASHTAGS] tags
5. IF a tag is missing from the response, THEN THE Response_Parser SHALL fall back to the existing paragraph-based parsing for that section
6. THE Response_Parser SHALL strip any conversational filler that appears before the first [HOOK] tag

### Requirement 4: Updated Hook Style Names

**User Story:** As a content creator, I want the hook styles to be named "Statistic-heavy", "Contrarian", and "Bold Prediction", so that the feed stays fresh with varied opening techniques.

#### Acceptance Criteria

1. THE PromptBuilder SHALL include "Statistic-heavy" as a hook style with description "Lead with a compelling number or data point"
2. THE PromptBuilder SHALL include "Contrarian" as a hook style with description "Challenge conventional wisdom or common assumptions"
3. THE PromptBuilder SHALL include "Bold Prediction" as a hook style with description "Make a confident forecast about the future"
4. THE PromptBuilder SHALL instruct the model to cycle through these three hook styles to maintain variety
5. THE System_Prompt SHALL NOT include the old hook style names ("Bold Statement", "Contrarian View", "Fact-Driven")

### Requirement 5: Backward Compatibility

**User Story:** As a developer, I want the updated parser to maintain backward compatibility with existing tests and integrations, so that the system continues to work correctly.

#### Acceptance Criteria

1. THE GeneratedPost dataclass SHALL maintain its existing field structure (full_text, hook, value, cta, hashtags, model_used, generated_at, source_url, character_count)
2. WHEN the Response_Parser encounters output without explicit tags, THE Response_Parser SHALL fall back to paragraph-based parsing
3. THE Generator SHALL continue to return valid GeneratedPost objects regardless of whether tags are present in the response
4. WHEN parsing succeeds, THE Generator SHALL produce output that passes existing property-based tests for post structure

### Requirement 6: Property Tests for Tag-Based Parsing

**User Story:** As a developer, I want property-based tests that validate the tag-based parsing logic, so that I can ensure correctness across many input variations.

#### Acceptance Criteria

1. WHEN a response contains valid [HOOK]...[/HOOK] tags, THE Response_Parser SHALL extract the exact content between the tags
2. WHEN a response contains valid [VALUE]...[/VALUE] tags, THE Response_Parser SHALL extract the exact content between the tags
3. WHEN a response contains valid [CTA]...[/CTA] tags, THE Response_Parser SHALL extract the exact content between the tags
4. WHEN a response contains valid [HASHTAGS]...[/HASHTAGS] tags, THE Response_Parser SHALL extract the exact content between the tags
5. FOR ALL valid tagged responses, parsing then reconstructing the full text SHALL preserve the original content sections
