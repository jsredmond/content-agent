# Implementation Plan: Robust Response Parsing

## Overview

This plan implements explicit tag-based response parsing and updated hook styles for the LinkedIn post generator. The implementation follows a bottom-up approach: first updating the prompt templates, then refactoring the parser, and finally adding property-based tests.

## Tasks

- [ ] 1. Update PromptBuilder class attributes
  - [x] 1.1 Update SYSTEM_PROMPT to forbid conversational filler
    - Add explicit instruction: "NEVER use conversational filler like 'Here is the post:', 'Sure!', 'Certainly!'"
    - Add instruction to begin output immediately with [HOOK] tag
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [x] 1.2 Update HOOK_VALUE_CTA_TEMPLATE with new hook styles
    - Replace "Bold Statement" with "Statistic-heavy: Lead with a compelling number or data point"
    - Replace "Contrarian View" with "Contrarian: Challenge conventional wisdom or common assumptions"
    - Replace "Fact-Driven" with "Bold Prediction: Make a confident forecast about the future"
    - Add instruction to cycle through hook styles for variety
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [x] 1.3 Add explicit tag format instructions to HOOK_VALUE_CTA_TEMPLATE
    - Add OUTPUT FORMAT section with [HOOK]/[/HOOK], [VALUE]/[/VALUE], [CTA]/[/CTA], [HASHTAGS]/[/HASHTAGS] examples
    - Remove the old "Return ONLY the post text" instruction
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 2. Implement regex-based response parsing
  - [x] 2.1 Add regex pattern constants to generator.py
    - Add HOOK_PATTERN, VALUE_PATTERN, CTA_PATTERN, HASHTAGS_PATTERN as compiled regex
    - Use re.IGNORECASE | re.DOTALL flags for flexibility
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [x] 2.2 Implement _extract_tagged_section helper method
    - Create method to extract content between [TAG] and [/TAG] markers
    - Return None if tags not found
    - Strip whitespace from extracted content
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [x] 2.3 Refactor _parse_response to use tag extraction with fallback
    - Try regex extraction first for each section
    - Fall back to existing paragraph-based parsing if tags missing
    - Strip conversational filler before first [HOOK] tag
    - _Requirements: 3.5, 3.6, 5.2, 5.3_

- [x] 3. Checkpoint - Verify implementation compiles and existing tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Update existing property tests for new hook styles
  - [x] 4.1 Update test_prompt_contains_bold_statement_hook_style to test "Statistic-heavy"
    - Change assertion from "Bold Statement" to "Statistic-heavy"
    - Update description assertion to "Lead with a compelling number or data point"
    - _Requirements: 4.1_
  
  - [x] 4.2 Update test_prompt_contains_contrarian_view_hook_style to test "Contrarian"
    - Change assertion from "Contrarian View" to "Contrarian"
    - Update description assertion to "Challenge conventional wisdom or common assumptions"
    - _Requirements: 4.2_
  
  - [x] 4.3 Update test_prompt_contains_fact_driven_hook_style to test "Bold Prediction"
    - Change assertion from "Fact-Driven" to "Bold Prediction"
    - Update description assertion to "Make a confident forecast about the future"
    - _Requirements: 4.3_
  
  - [x] 4.4 Update test_prompt_contains_all_hook_styles to use new style names
    - Update expected_hook_styles dictionary with new names and descriptions
    - _Requirements: 4.1, 4.2, 4.3_

- [ ] 5. Add new property tests for tag-based parsing
  - [x] 5.1 Write property test for tag extraction round trip
    - **Property 1: Tag Extraction Round Trip**
    - Generate random hook, value, cta, hashtags content
    - Wrap in tags, parse, verify extracted content matches original
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 6.1, 6.2, 6.3, 6.4, 6.5**
  
  - [x] 5.2 Write property test for filler stripping
    - **Property 2: Filler Stripping Preserves Content**
    - Generate random filler prefixes and tagged content
    - Verify parsing with filler produces same result as without filler
    - **Validates: Requirements 3.6**
  
  - [x] 5.3 Write property test for fallback parsing consistency
    - **Property 3: Fallback Parsing Consistency**
    - Generate responses without tags
    - Verify new parser produces same output as original paragraph-based parser
    - **Validates: Requirements 3.5, 5.2**
  
  - [x] 5.4 Write property test for no-filler instruction presence
    - **Property 5: No-Filler Instruction Present**
    - Verify get_system_prompt() contains filler prohibition instruction
    - **Validates: Requirements 1.1, 1.2**
  
  - [x] 5.5 Write property test for tag format instructions presence
    - **Property 6: Tag Format Instructions Present**
    - For any article, verify prompt contains all four tag pair instructions
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

- [ ] 6. Add property test for old hook style exclusion
  - [x] 6.1 Write property test verifying old styles are removed
    - **Property 4: Hook Style Names Present (negative check)**
    - For any article, verify prompt does NOT contain "Bold Statement", "Contrarian View", "Fact-Driven"
    - **Validates: Requirements 4.5**

- [x] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks including property-based tests are required
- The implementation maintains backward compatibility through fallback parsing
- Existing tests for ContextManager, OllamaClient, and BatchResult remain unchanged
- Property tests use Hypothesis with minimum 100 iterations per test
