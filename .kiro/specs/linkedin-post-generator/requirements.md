# Requirements Document

## Introduction

The LinkedIn Post Generator is an extension to the Content Agent pipeline that transforms curated article metadata into fully-formed LinkedIn posts. The feature reads article URLs from the existing CSV output, fetches and analyzes full article content, and generates professional LinkedIn posts following a specific format optimized for engagement with security and IT leadership audiences.

## Glossary

- **Post_Generator**: The main component that orchestrates LinkedIn post generation from article URLs
- **Content_Fetcher**: Component that retrieves and extracts full article content from URLs
- **Post_Formatter**: Component that structures extracted content into the target LinkedIn post format
- **Article_Analyzer**: Component that extracts key facts, statistics, and actionable insights from article content
- **CSV_Reader**: Component that reads article metadata from the existing pipeline CSV output
- **Generated_Post**: Data model representing a complete LinkedIn post with all required sections

## Requirements

### Requirement 1: CSV Input Processing

**User Story:** As a content creator, I want to read article data from the existing pipeline CSV output, so that I can generate LinkedIn posts for curated articles.

#### Acceptance Criteria

1. WHEN a CSV file path is provided, THE CSV_Reader SHALL parse all article rows and return structured article metadata
2. WHEN the CSV file does not exist, THE CSV_Reader SHALL return a descriptive error indicating the file was not found
3. WHEN the CSV contains malformed rows, THE CSV_Reader SHALL skip invalid rows and log warnings while continuing to process valid rows
4. THE CSV_Reader SHALL extract url, title, source, key_topics, and summary fields from each row

### Requirement 2: Article Content Fetching

**User Story:** As a content creator, I want to fetch full article content from URLs, so that I can generate detailed LinkedIn posts with specific facts and statistics.

#### Acceptance Criteria

1. WHEN a valid article URL is provided, THE Content_Fetcher SHALL retrieve the full HTML content and extract the article body text
2. WHEN an article URL returns a non-200 HTTP status, THE Content_Fetcher SHALL return an error result with the status code
3. WHEN an article URL times out, THE Content_Fetcher SHALL retry up to the configured maximum retries before returning a timeout error
4. WHEN extracting article content, THE Content_Fetcher SHALL remove navigation, ads, and non-article elements
5. THE Content_Fetcher SHALL respect rate limiting by waiting the configured delay between requests

### Requirement 3: Article Content Analysis

**User Story:** As a content creator, I want to extract key facts, statistics, and insights from article content, so that I can create compelling LinkedIn posts.

#### Acceptance Criteria

1. WHEN article content is provided, THE Article_Analyzer SHALL extract numerical statistics and specific facts
2. WHEN article content is provided, THE Article_Analyzer SHALL identify the main threat, announcement, or topic
3. WHEN article content is provided, THE Article_Analyzer SHALL extract actionable defense strategies or recommendations
4. WHEN article content is provided, THE Article_Analyzer SHALL identify real-world impact examples or case studies
5. WHEN article content contains bullet points or lists, THE Article_Analyzer SHALL preserve key list items for the post

### Requirement 4: LinkedIn Post Formatting

**User Story:** As a content creator, I want posts formatted in a specific engaging style, so that they maximize engagement with my target audience.

#### Acceptance Criteria

1. THE Post_Formatter SHALL generate an attention-grabbing opening line containing specific numbers or facts from the article
2. THE Post_Formatter SHALL include a hook question after the opening (e.g., "The sophistication?" or "What made this possible?")
3. THE Post_Formatter SHALL include a detailed explanation section of 2-4 sentences
4. THE Post_Formatter SHALL generate a bullet list with checkmark emojis (✅) highlighting 3-7 key points
5. THE Post_Formatter SHALL include a "Real impact:" section with concrete examples when available
6. THE Post_Formatter SHALL include a "Defense strategy:" section with actionable recommendations
7. THE Post_Formatter SHALL include a thought-provoking closing statement
8. THE Post_Formatter SHALL include an engagement question at the end
9. THE Post_Formatter SHALL append the article URL
10. THE Post_Formatter SHALL append 3-5 relevant hashtags based on article topics

### Requirement 5: Post Generation Orchestration

**User Story:** As a content creator, I want to generate multiple LinkedIn posts from a batch of articles, so that I can efficiently create content for my publishing schedule.

#### Acceptance Criteria

1. WHEN a list of articles is provided, THE Post_Generator SHALL process each article and generate a corresponding LinkedIn post
2. WHEN an article fails to fetch or analyze, THE Post_Generator SHALL log the error and continue processing remaining articles
3. WHEN post generation completes, THE Post_Generator SHALL return a result containing successful posts and a list of failures
4. THE Post_Generator SHALL track generation metrics including success count, failure count, and processing time

### Requirement 6: Output Generation

**User Story:** As a content creator, I want generated posts saved to files, so that I can review and publish them.

#### Acceptance Criteria

1. WHEN posts are generated, THE Post_Generator SHALL write each post to a separate text file with a descriptive filename
2. WHEN posts are generated, THE Post_Generator SHALL write a summary JSON file containing metadata for all generated posts
3. THE Post_Generator SHALL create output files in a timestamped directory under src/output/posts/
4. WHEN writing output files, THE Post_Generator SHALL use UTF-8 encoding to preserve emojis and special characters

### Requirement 7: Configuration

**User Story:** As a developer, I want configurable settings for post generation, so that I can tune the behavior without code changes.

#### Acceptance Criteria

1. THE Post_Generator SHALL read configuration from environment variables with sensible defaults
2. THE Post_Generator SHALL support configuring the maximum number of posts to generate per run
3. THE Post_Generator SHALL support configuring the request timeout for content fetching
4. THE Post_Generator SHALL support configuring the minimum article content length to process
5. WHERE hashtag customization is enabled, THE Post_Generator SHALL allow specifying additional hashtags via configuration

### Requirement 8: Error Handling and Observability

**User Story:** As a developer, I want comprehensive error handling and logging, so that I can diagnose issues and monitor post generation.

#### Acceptance Criteria

1. WHEN any component encounters an error, THE Post_Generator SHALL log the error with context including article URL and error type
2. WHEN post generation completes, THE Post_Generator SHALL write a run log with generation statistics
3. IF a critical error prevents all processing, THEN THE Post_Generator SHALL exit gracefully with a non-zero status code
4. THE Post_Generator SHALL log progress at each stage of processing for observability
