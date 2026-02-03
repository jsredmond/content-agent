# Implementation Plan: Prompt Builder Enhancements

## Overview

This plan implements enhancements to the PromptBuilder and ContentGenerator classes in `src/engines/generator.py`. The implementation follows an incremental approach, updating the prompt template first, then the validation gate, and finally the default model.

## Tasks

- [ ] 1. Update PromptBuilder hook instructions
  - [x] 1.1 Update HOOK_VALUE_CTA_TEMPLATE with three specific hook styles
    - Add "Bold Statement: A confident, declarative opening"
    - Add "Contrarian View: Challenge conventional wisdom"
    - Add "Fact-Driven: Lead with a compelling statistic or data point"
    - Add instruction to avoid starting with a question
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  
  - [x] 1.2 Write property test for hook styles in prompt
    - **Property 1: Hook Styles Present in Prompt**
    - **Validates: Requirements 1.1, 1.3, 1.4, 1.5**
  
  - [x] 1.3 Write property test for avoid-question instruction
    - **Property 2: Avoid Question Instruction Present**
    - **Validates: Requirements 1.2**

- [ ] 2. Update PromptBuilder hashtag limit
  - [x] 2.1 Update HOOK_VALUE_CTA_TEMPLATE with hashtag limit instruction
    - Change hashtag instruction to specify exactly 3 hashtags
    - Add explicit instruction: "no more, no fewer than 3 hashtags"
    - Instruct LLM to select 3 most relevant from provided list
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [x] 2.2 Write property test for hashtag limit instruction
    - **Property 3: Hashtag Limit Instruction Present**
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 3. Checkpoint - Verify PromptBuilder changes
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement validation gate in ContentGenerator
  - [x] 4.1 Add MIN_SCORE_THRESHOLD constant to ContentGenerator
    - Add class constant: MIN_SCORE_THRESHOLD = 50.0
    - _Requirements: 3.1_
  
  - [x] 4.2 Update generate_batch to filter articles by score
    - Filter articles with score_overall < MIN_SCORE_THRESHOLD before processing
    - Log skipped articles at DEBUG level with their score
    - Log summary count of skipped articles at INFO level
    - Ensure BatchResult.total_processed only counts attempted articles
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [x] 4.3 Write property test for validation gate filtering
    - **Property 4: Validation Gate Filters Low-Score Articles**
    - **Validates: Requirements 3.1, 3.3, 3.4**
  
  - [x] 4.4 Write property test for skip logging
    - **Property 5: Skip Logging for Low-Score Articles**
    - **Validates: Requirements 3.2**

- [ ] 5. Update default model in ContentGenerator
  - [x] 5.1 Change DEFAULT_MODEL from "qwen3-coder:30b" to "llama4:scout"
    - Update DEFAULT_MODEL class constant
    - Update docstrings referencing the default model
    - _Requirements: 4.1, 4.2_
  
  - [x] 5.2 Write unit tests for default model configuration
    - Test default model is "llama4:scout"
    - Test custom model configuration still works
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 6. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive testing
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- All changes are in `src/engines/generator.py`
- Tests go in `tests/test_generator_properties.py`
