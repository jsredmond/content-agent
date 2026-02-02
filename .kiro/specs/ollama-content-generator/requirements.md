# Requirements Document

## Introduction

This feature adds an Ollama-based local LLM module to transform scraped content into high-engagement LinkedIn posts. The module integrates with the existing Content Agent pipeline, taking normalized article data and generating polished LinkedIn posts using the Hook-Value-CTA framework. It supports multiple Ollama models (qwen3-coder:30b for speed/logic, llama4:scout for creative writing) and handles long-form articles up to 10k tokens.

## Glossary

- **Content_Generator**: The main class that interfaces with Ollama to generate LinkedIn posts from article content
- **Ollama**: A local LLM runtime that hosts and serves language models
- **Hook_Value_CTA**: A LinkedIn post framework consisting of Hook (attention-grabbing opening), Value (core insight), and CTA (call-to-action)
- **Model_Selector**: Component that chooses between available Ollama models based on configuration
- **Context_Window**: The maximum number of tokens a model can process in a single request
- **Scored_Article**: The existing data model containing article metadata, scores, and summaries
- **Generated_Post**: The output data structure containing the formatted LinkedIn post and metadata

## Requirements

### Requirement 1: Ollama Client Integration

**User Story:** As a content creator, I want to connect to a local Ollama instance, so that I can generate LinkedIn posts without relying on external APIs.

#### Acceptance Criteria

1. WHEN the Content_Generator is initialized, THE Content_Generator SHALL establish a connection to the local Ollama instance
2. WHEN the Ollama service is not running, THE Content_Generator SHALL raise a descriptive OllamaConnectionError with troubleshooting guidance
3. WHEN checking model availability, THE Content_Generator SHALL query Ollama for the list of available models
4. IF a requested model is not loaded in Ollama, THEN THE Content_Generator SHALL raise a ModelNotAvailableError with the model name and instructions to pull it

### Requirement 2: Model Selection and Configuration

**User Story:** As a content creator, I want to choose between different LLM models, so that I can optimize for speed or creativity based on my needs.

#### Acceptance Criteria

1. THE Content_Generator SHALL support configuration of the model name via constructor parameter
2. THE Content_Generator SHALL default to qwen3-coder:30b when no model is specified
3. WHEN a model name is provided, THE Content_Generator SHALL validate that the model exists in Ollama before proceeding
4. THE Content_Generator SHALL expose a class method to list all available models from Ollama

### Requirement 3: Context Window Management

**User Story:** As a content creator, I want to process long-form articles without losing important content, so that the generated posts capture the full value of the source material.

#### Acceptance Criteria

1. THE Content_Generator SHALL accept articles with content up to 10,000 tokens without truncation
2. WHEN article content exceeds the model's context window, THE Content_Generator SHALL apply intelligent summarization to fit within limits
3. THE Content_Generator SHALL preserve the article's key points, statistics, and actionable insights during any content reduction
4. THE Content_Generator SHALL log a warning when content truncation is applied
5. THE Content_Generator SHALL pass a configurable num_ctx parameter to Ollama to set the context window size (default 16384)

### Requirement 4: Hook-Value-CTA Post Generation

**User Story:** As a content creator, I want LinkedIn posts structured with Hook-Value-CTA framework, so that my posts maximize engagement and provide clear value.

#### Acceptance Criteria

1. WHEN generating a post, THE Content_Generator SHALL produce a Hook section with an attention-grabbing opening (question, statistic, or bold statement)
2. WHEN generating a post, THE Content_Generator SHALL produce a Value section containing the core insight, data, or takeaway from the article
3. WHEN generating a post, THE Content_Generator SHALL produce a CTA section with an engagement prompt (question, share request, or action item)
4. THE Content_Generator SHALL format the post with clear visual separation between Hook, Value, and CTA sections
5. THE Content_Generator SHALL include relevant hashtags at the end of the post
6. THE Content_Generator SHALL keep the total post length under 3,000 characters (LinkedIn's limit)

### Requirement 5: Prompt Engineering

**User Story:** As a content creator, I want well-crafted prompts sent to the LLM, so that the generated posts are consistently high quality.

#### Acceptance Criteria

1. THE Content_Generator SHALL construct prompts that include the article title, source, summary, and key topics
2. THE Content_Generator SHALL include the Hook-Value-CTA framework instructions in every prompt
3. THE Content_Generator SHALL specify the target audience (CIO, CISO, CTO, IT Director) in the prompt
4. THE Content_Generator SHALL instruct the model to use a professional yet engaging tone
5. WHEN the article has security or compliance themes, THE Content_Generator SHALL emphasize security-first messaging in the prompt

### Requirement 6: Error Handling and Resilience

**User Story:** As a content creator, I want robust error handling, so that failures are clear and recoverable.

#### Acceptance Criteria

1. IF Ollama returns an error response, THEN THE Content_Generator SHALL wrap it in a GenerationError with context
2. IF the generation times out, THEN THE Content_Generator SHALL raise a TimeoutError with the configured timeout value
3. WHEN a generation fails, THE Content_Generator SHALL include the article title in the error message for debugging
4. THE Content_Generator SHALL support configurable timeout values with a default of 120 seconds
5. IF generation fails, THEN THE Content_Generator SHALL NOT modify any input data or state

### Requirement 7: Output Data Structure

**User Story:** As a developer, I want a well-defined output structure, so that generated posts integrate cleanly with the existing pipeline.

#### Acceptance Criteria

1. THE Content_Generator SHALL return a GeneratedPost dataclass containing the full post text
2. THE GeneratedPost SHALL include separate fields for hook, value, and cta sections
3. THE GeneratedPost SHALL include the model name used for generation
4. THE GeneratedPost SHALL include a generation timestamp
5. THE GeneratedPost SHALL include the source article's URL for reference

### Requirement 8: Batch Processing Support

**User Story:** As a content creator, I want to generate posts for multiple articles efficiently, so that I can process entire pipeline outputs at once.

#### Acceptance Criteria

1. THE Content_Generator SHALL provide a batch generation method that accepts a list of ScoredArticle objects
2. WHEN processing a batch, THE Content_Generator SHALL continue processing remaining articles if one fails
3. WHEN processing a batch, THE Content_Generator SHALL return a list of results with success/failure status for each article
4. THE Content_Generator SHALL log progress during batch processing (articles processed / total)

### Requirement 9: Integration with Existing Pipeline

**User Story:** As a developer, I want the generator to integrate seamlessly with the existing Content Agent pipeline, so that it can be added as an optional processing stage.

#### Acceptance Criteria

1. THE Content_Generator SHALL accept ScoredArticle objects as input
2. THE Content_Generator SHALL be importable from src.engines.generator
3. THE Content_Generator SHALL follow the same logging conventions as other engine modules
4. THE Content_Generator SHALL be usable independently of the main pipeline workflow
