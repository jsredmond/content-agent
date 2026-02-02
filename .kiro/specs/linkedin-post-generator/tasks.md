# Implementation Plan: LinkedIn Post Generator

## Overview

This plan implements the LinkedIn Post Generator feature as an extension to the Content Agent pipeline. The implementation follows the existing project patterns with separate engine components, dataclasses for data models, and Hypothesis for property-based testing.

## Tasks

- [ ] 1. Set up configuration and data models
  - [ ] 1.1 Create PostGeneratorSettings dataclass in `src/config/post_settings.py`
    - Define settings: max_posts, request_timeout, max_retries, retry_delay, min_content_length, additional_hashtags
    - Implement from_env() class method to load from environment variables
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [ ] 1.2 Create data models in `src/engines/post_models.py`
    - Define ArticleInput, AnalyzedContent, GeneratedPost, FetchResult, PostOutputResult, PostGeneratorResult, PostGeneratorMetrics dataclasses
    - _Requirements: 1.4, 3.1, 4.1, 5.3, 5.4_

- [ ] 2. Implement CSV Reader
  - [ ] 2.1 Create `src/engines/post_csv_reader.py`
    - Implement read_articles_from_csv() function
    - Handle file not found and permission errors
    - Skip malformed rows with logging
    - Extract url, title, source, key_topics, summary fields
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  
  - [ ] 2.2 Write property tests for CSV Reader
    - **Property 1: CSV Parsing Round-Trip**
    - **Property 2: CSV Graceful Degradation**
    - **Validates: Requirements 1.1, 1.3, 1.4**

- [ ] 3. Implement Content Fetcher
  - [ ] 3.1 Create `src/engines/post_content_fetcher.py`
    - Implement fetch_article_content() with retry logic using tenacity
    - Implement extract_article_body() using BeautifulSoup to remove nav, ads, sidebars
    - Handle HTTP errors, timeouts, and SSL errors
    - Respect rate limiting with configurable delay
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [ ] 3.2 Write property tests for Content Fetcher
    - **Property 3: HTML Content Extraction**
    - **Property 4: Statistics Extraction**
    - **Validates: Requirements 2.1, 2.4, 3.1**

- [ ] 4. Checkpoint - Ensure CSV and Content Fetcher tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Article Analyzer
  - [ ] 5.1 Create `src/engines/post_article_analyzer.py`
    - Implement analyze_article() main function
    - Implement extract_statistics() to find numerical facts using regex
    - Implement extract_key_points() to identify bullet-worthy content
    - Implement extract_defense_strategies() to find recommendations
    - Generate hook questions based on content type
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  
  - [ ] 5.2 Write property tests for Article Analyzer
    - **Property 5: Content Analysis Structure**
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.5**

- [ ] 6. Implement Post Formatter
  - [ ] 6.1 Create `src/engines/post_formatter.py`
    - Implement format_linkedin_post() main function
    - Implement generate_opening_line() with facts/statistics
    - Implement format_bullet_list() with ✅ emojis
    - Implement generate_hashtags() from topics
    - Structure post with all required sections: opening, hook, explanation, bullets, real impact, defense strategy, closing, engagement question, URL, hashtags
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10_
  
  - [ ] 6.2 Write property tests for Post Formatter
    - **Property 6: Post Contains Required Sections**
    - **Property 7: Bullet List Format**
    - **Property 8: Post Contains URL and Hashtags**
    - **Validates: Requirements 4.1-4.10**

- [ ] 7. Checkpoint - Ensure Analyzer and Formatter tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement Output Writer
  - [ ] 8.1 Create `src/engines/post_output_writer.py`
    - Implement write_posts() to create individual text files
    - Implement write_summary_json() for metadata
    - Create timestamped output directory under src/output/posts/
    - Use UTF-8 encoding for emoji preservation
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [ ] 8.2 Write property tests for Output Writer
    - **Property 11: Output File Structure**
    - **Property 12: Output Encoding Round-Trip**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

- [ ] 9. Implement Post Generator Orchestrator
  - [ ] 9.1 Create `src/engines/post_generator.py`
    - Implement generate_posts_from_csv() main orchestrator
    - Wire together CSV Reader → Content Fetcher → Analyzer → Formatter → Output Writer
    - Handle per-article failures gracefully
    - Track metrics (success count, failure count, processing time)
    - Respect max_posts and min_content_length settings
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 7.2, 7.4_
  
  - [ ] 9.2 Write property tests for Post Generator
    - **Property 9: Generator Processes All Articles**
    - **Property 10: Generator Result Consistency**
    - **Property 13: Configuration Limits Posts**
    - **Property 14: Minimum Content Length Filter**
    - **Validates: Requirements 5.1-5.4, 7.2, 7.4**

- [ ] 10. Implement Observability
  - [ ] 10.1 Add run log writing to `src/engines/post_generator.py`
    - Write run log JSON with generation statistics
    - Include articles_processed, posts_generated, failures_count, processing_time_seconds
    - Log progress at each pipeline stage
    - _Requirements: 8.1, 8.2, 8.4_
  
  - [ ] 10.2 Write property tests for Observability
    - **Property 16: Run Log Creation**
    - **Validates: Requirements 8.2**

- [ ] 11. Checkpoint - Ensure all component tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Integration and CLI
  - [ ] 12.1 Add CLI entry point for post generation
    - Add `--generate-posts` flag to `src/main.py` or create `src/generate_posts.py`
    - Accept CSV path as argument
    - Support verbose logging flag
    - _Requirements: 5.1, 8.4_
  
  - [ ] 12.2 Update `src/engines/__init__.py` to export new components
    - Export PostGeneratorSettings, generate_posts_from_csv, and data models
    - _Requirements: N/A (integration)_

- [ ] 13. Configuration and Additional Hashtags
  - [ ] 13.1 Add environment variable support for additional hashtags
    - Parse POST_ADDITIONAL_HASHTAGS from .env (comma-separated)
    - Merge with topic-derived hashtags in formatter
    - _Requirements: 7.5_
  
  - [ ] 13.2 Write property test for additional hashtags
    - **Property 15: Additional Hashtags**
    - **Validates: Requirements 7.5**

- [ ] 14. Final checkpoint - Run full test suite
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks including tests are required for comprehensive coverage
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis with 100+ iterations
- Unit tests validate specific examples and edge cases
- The implementation follows existing project patterns in src/engines/
