# Implementation Plan: Ollama Content Generator

## Overview

This plan implements the Ollama-based LinkedIn post generator as a new engine module (`src/engines/generator.py`). The implementation follows a bottom-up approach: first building the internal components (exceptions, data models, context manager, prompt builder, Ollama client), then assembling them into the ContentGenerator class, and finally adding batch processing and tests.

## Tasks

- [x] 1. Create data models and exceptions
  - [x] 1.1 Create `src/engines/generator.py` with custom exceptions
    - Implement `OllamaConnectionError` with troubleshooting guidance
    - Implement `ModelNotAvailableError` with model name and pull instructions
    - Implement `GenerationError` with article title context
    - _Requirements: 1.2, 1.4, 6.1, 6.3_

  - [x] 1.2 Add `GeneratedPost` and `BatchResult` dataclasses
    - `GeneratedPost`: full_text, hook, value, cta, hashtags, model_used, generated_at, source_url, character_count
    - `BatchResult`: successful, failed, total_processed, success_rate
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 8.3_

- [x] 2. Implement ContextManager
  - [x] 2.1 Create `ContextManager` class in generator.py
    - Implement `__init__` with max_tokens parameter (default 10000)
    - Implement `estimate_tokens` method (approx 4 chars per token)
    - Implement `prepare_content` returning (content, was_truncated) tuple
    - Implement `summarize_for_context` for content reduction
    - Add warning logging when truncation occurs
    - _Requirements: 3.1, 3.2, 3.4, 3.5_

  - [x] 2.2 Write property tests for ContextManager
    - **Property 4: Content Within Limit Passes Through**
    - **Property 5: Oversized Content Truncation**
    - **Property 6: Truncation Warning Logging**
    - **Validates: Requirements 3.1, 3.2, 3.4**

- [x] 3. Implement PromptBuilder
  - [x] 3.1 Create `PromptBuilder` class in generator.py
    - Define `SYSTEM_PROMPT` constant with audience and tone instructions
    - Define `HOOK_VALUE_CTA_TEMPLATE` constant
    - Implement `build` method accepting article metadata
    - Implement `_add_security_framing` for security topics
    - Implement `_format_audience_context` for target audience
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 3.2 Write property tests for PromptBuilder
    - **Property 9: Prompt Completeness**
    - **Property 10: Security Framing for Security Topics**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

- [x] 4. Implement OllamaClient
  - [x] 4.1 Create `OllamaClient` class in generator.py
    - Implement `__init__` with timeout and num_ctx parameters
    - Implement `check_connection` using ollama.list()
    - Implement `list_models` returning available model names
    - Implement `chat` method with num_ctx in options
    - Handle connection errors and wrap in OllamaConnectionError
    - Handle timeout errors
    - _Requirements: 1.1, 1.2, 1.3, 2.4, 3.5, 6.2, 6.4_

  - [x] 4.2 Write property tests for OllamaClient error handling
    - **Property 1: Connection Error Handling**
    - **Property 2: Model Not Available Error**
    - **Property 12: Timeout Error Handling**
    - **Validates: Requirements 1.2, 1.4, 6.2**

- [x] 5. Checkpoint - Ensure component tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement ContentGenerator class
  - [x] 6.1 Create `ContentGenerator` class in generator.py
    - Implement `__init__` with model, timeout, max_tokens, num_ctx parameters
    - Default model to "qwen3-coder:30b"
    - Default timeout to 120 seconds
    - Default num_ctx to 16384
    - Initialize internal OllamaClient, ContextManager, PromptBuilder
    - _Requirements: 2.1, 2.2, 6.4_

  - [x] 6.2 Implement model validation
    - Implement `is_model_available` method
    - Implement `list_available_models` class method
    - Validate model exists before first generation
    - Raise ModelNotAvailableError for missing models
    - _Requirements: 1.4, 2.3, 2.4_

  - [x] 6.3 Implement single article generation
    - Implement `generate` method accepting ScoredArticle
    - Use ContextManager to prepare content
    - Use PromptBuilder to construct prompt
    - Call OllamaClient.chat with configured model
    - Parse response into hook, value, cta sections
    - Create and return GeneratedPost with all fields
    - Ensure character_count < 3000
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 9.1_

  - [x] 6.4 Write property tests for ContentGenerator
    - **Property 3: Model Configuration Acceptance**
    - **Property 7: GeneratedPost Structure Completeness**
    - **Property 8: Post Length Constraint**
    - **Property 11: Error Handling with Context**
    - **Property 13: Input Immutability on Failure**
    - **Validates: Requirements 2.1, 2.3, 4.1-4.6, 6.1, 6.3, 6.5, 7.1-7.5**

- [x] 7. Implement batch processing
  - [x] 7.1 Implement `generate_batch` method
    - Accept list of ScoredArticle objects
    - Process each article, catching errors per-article
    - Continue processing on individual failures
    - Log progress (articles processed / total)
    - Return BatchResult with successful, failed, counts, success_rate
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 7.2 Write property tests for batch processing
    - **Property 14: Batch Processing Resilience**
    - **Property 15: Batch Progress Logging**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4**

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Integration and finalization
  - [x] 9.1 Update `src/engines/__init__.py` exports
    - Export ContentGenerator, GeneratedPost, BatchResult
    - Export OllamaConnectionError, ModelNotAvailableError, GenerationError
    - _Requirements: 9.2_

  - [x] 9.2 Add `ollama` to requirements.txt
    - Add `ollama` package dependency
    - _Requirements: 1.1_

  - [x] 9.3 Write unit tests for integration points
    - Test module importability from src.engines.generator
    - Test standalone usage without pipeline
    - Test with ScoredArticle from existing pipeline
    - _Requirements: 9.2, 9.4_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required including property tests
- Each task references specific requirements for traceability
- Property tests use Hypothesis with minimum 100 iterations
- Ollama client interactions should be mocked in tests
- The generator follows the same logging conventions as other engine modules
