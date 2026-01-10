# Requirements Document

## Introduction

The Content Agent is an AI-assisted workflow that discovers, scores, and curates timely cloud and security articles from AWS News Blog and Microsoft Purview blog. It normalizes, deduplicates, and ranks articles by relevance to security-first cloud modernization themes, then exports a CSV to Google Drive for LinkedIn post drafting.

## Glossary

- **Content_Agent**: The main orchestration system that runs the curation pipeline
- **Source_Fetcher**: Component responsible for retrieving articles from configured blog sources
- **Article_Normalizer**: Component that standardizes article fields across different sources
- **Deduplicator**: Component that removes duplicate articles by URL and title
- **Relevance_Scorer**: Component that calculates recency and topic relevance scores
- **Summarizer**: Component that generates summaries and LinkedIn-ready metadata
- **Selector**: Component that picks top N articles based on overall score
- **CSV_Writer**: Component that outputs curated articles to CSV format
- **Google_Drive_Connector**: Component that uploads files to Google Drive
- **Canonical_URL**: A URL stripped of tracking parameters and normalized for deduplication
- **Recency_Score**: A 0-100 score based on how recently an article was published
- **Relevance_Score**: A 0-100 score based on keyword and topic matches
- **Overall_Score**: A weighted combination of recency and relevance scores

## Requirements

### Requirement 1: Source Fetching

**User Story:** As a content curator, I want to fetch articles from AWS News Blog and Microsoft Purview blog, so that I have a pool of recent cloud security content to curate.

#### Acceptance Criteria

1. WHEN the Content_Agent starts a run, THE Source_Fetcher SHALL attempt to fetch articles from each configured source independently
2. IF a source fetch fails, THEN THE Source_Fetcher SHALL log the error and continue with remaining sources
3. WHEN fetching from AWS News Blog, THE Source_Fetcher SHALL extract title, link, published date, author, and teaser text
4. WHEN fetching from Microsoft Purview blog, THE Source_Fetcher SHALL extract title, link, published date, author, and teaser text
5. THE Source_Fetcher SHALL respect request pacing with configurable delays between requests
6. THE Source_Fetcher SHALL implement retry logic with exponential backoff for transient failures
7. WHEN a source provides an RSS feed, THE Source_Fetcher SHALL prefer RSS over HTML scraping
8. THE Source_Fetcher SHALL limit fetched articles per source to the configured maximum (default 50)

### Requirement 2: Article Normalization

**User Story:** As a content curator, I want articles from different sources normalized to a common format, so that I can compare and rank them consistently.

#### Acceptance Criteria

1. WHEN an article is fetched, THE Article_Normalizer SHALL produce a normalized record with: title, canonical_url, published_date, author, and summary_text
2. THE Article_Normalizer SHALL strip tracking parameters from URLs to produce canonical URLs
3. WHEN a published date is present, THE Article_Normalizer SHALL parse it into a standard datetime format
4. IF a published date cannot be parsed, THEN THE Article_Normalizer SHALL set it to null and log a warning
5. THE Article_Normalizer SHALL trim whitespace and normalize unicode in text fields

### Requirement 3: Deduplication

**User Story:** As a content curator, I want duplicate articles removed, so that the same content does not appear multiple times in my output.

#### Acceptance Criteria

1. THE Deduplicator SHALL first remove articles with duplicate canonical URLs
2. THE Deduplicator SHALL then remove articles with duplicate normalized titles (case-insensitive, whitespace-normalized)
3. WHEN duplicates are found, THE Deduplicator SHALL keep the article with the earliest published date
4. THE Deduplicator SHALL report the count of articles removed during deduplication

### Requirement 4: Relevance Scoring

**User Story:** As a content curator, I want articles scored by recency and topic relevance, so that I can identify the most valuable content for my audience.

#### Acceptance Criteria

1. THE Relevance_Scorer SHALL calculate a recency_score (0-100) based on days since publication within the configured window
2. WHEN an article is published today, THE Relevance_Scorer SHALL assign a recency_score of 100
3. WHEN an article is at the edge of the recency window, THE Relevance_Scorer SHALL assign a recency_score approaching 0
4. THE Relevance_Scorer SHALL calculate a relevance_score (0-100) based on keyword matches across configured themes
5. THE Relevance_Scorer SHALL match keywords in title, summary, and teaser text
6. THE Relevance_Scorer SHALL calculate overall_score using configurable weights (default: 0.4 * recency + 0.6 * relevance)
7. THE Relevance_Scorer SHALL support configurable keyword sets for themes: cloud security, identity and access, governance and compliance, data protection, DLP, auditing, retention, DevSecOps, automation, policy-as-code

### Requirement 5: Summarization and Metadata Generation

**User Story:** As a content curator, I want LinkedIn-ready summaries and metadata generated for each article, so that I can quickly draft social posts.

#### Acceptance Criteria

1. THE Summarizer SHALL generate a 1-3 sentence summary for each article
2. THE Summarizer SHALL generate a "why it matters" statement with security-first framing
3. THE Summarizer SHALL generate a suggested LinkedIn angle (1 sentence)
4. THE Summarizer SHALL generate suggested hashtags relevant to the article topics
5. THE Summarizer SHALL extract key topics from the article content

### Requirement 6: Article Selection

**User Story:** As a content curator, I want the top N highest-scoring articles selected, so that I receive a manageable set of the best content.

#### Acceptance Criteria

1. THE Selector SHALL sort articles by overall_score in descending order
2. THE Selector SHALL select the top N articles (configurable, default 10)
3. IF fewer than N articles are available, THEN THE Selector SHALL select all available articles
4. THE Selector SHALL exclude articles with overall_score below a configurable minimum threshold

### Requirement 7: CSV Output

**User Story:** As a content curator, I want curated articles exported to a CSV file, so that I have a portable artifact for downstream workflows.

#### Acceptance Criteria

1. THE CSV_Writer SHALL write output to src/output/ with filename format content_candidates_YYYYMMDD_HHMMSS.csv
2. THE CSV_Writer SHALL include all required fields: source, title, url, published_date, author, summary, key_topics, why_it_matters, suggested_linkedin_angle, suggested_hashtags, score_overall, score_recency, score_relevance, collected_at
3. THE CSV_Writer SHALL use semicolon delimiters for multi-value fields (key_topics, suggested_hashtags)
4. THE CSV_Writer SHALL encode the file as UTF-8

### Requirement 8: Google Drive Upload

**User Story:** As a content curator, I want the CSV automatically uploaded to Google Drive, so that it is accessible for team collaboration.

#### Acceptance Criteria

1. WHEN a CSV is written, THE Google_Drive_Connector SHALL upload it to the configured uploads folder
2. THE Google_Drive_Connector SHALL authenticate using the service account credentials from credentials.json
3. WHEN upload succeeds, THE Google_Drive_Connector SHALL log the uploaded file ID and folder path
4. IF upload fails, THEN THE Google_Drive_Connector SHALL log the error and continue (do not fail the entire run)

### Requirement 9: Observability and Logging

**User Story:** As a content curator, I want detailed run logs and metrics, so that I can monitor pipeline health and debug issues.

#### Acceptance Criteria

1. THE Content_Agent SHALL report counts per stage: fetched, normalized, deduped, selected
2. THE Content_Agent SHALL report per-source fetch results including any failures
3. THE Content_Agent SHALL report upload status with file ID and folder ID when available
4. THE Content_Agent SHALL report top keywords/topics among selected articles
5. THE Content_Agent SHALL write a run log JSON file to src/output/ with run metrics
6. IF any stage encounters an error, THEN THE Content_Agent SHALL log the error and continue processing where possible

### Requirement 10: Configuration Management

**User Story:** As a content curator, I want configurable settings for the pipeline, so that I can tune behavior without code changes.

#### Acceptance Criteria

1. THE Content_Agent SHALL load configuration from settings including: Google Drive folder ID, per-source fetch limits, recency window days, scoring weights, keyword sets, and target selection count
2. THE Content_Agent SHALL support environment variables via .env file for secrets
3. THE Content_Agent SHALL use sensible defaults when configuration values are not provided
4. THE Content_Agent SHALL validate configuration at startup and report invalid values
