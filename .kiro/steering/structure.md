# Project Structure (Content Agent)

This file describes the system layout and modules for the Content Agent curation pipeline.

## Directory layout

```
src/
├── __init__.py
├── main.py                          # CLI entry point
├── agent/
│   ├── __init__.py
│   ├── runner.py                    # Main runner, wires components
│   └── workflow.py                  # Pipeline orchestrator
├── config/
│   ├── __init__.py
│   └── settings.py                  # Settings dataclass and loader
├── connectors/
│   ├── __init__.py
│   └── google_drive.py              # Google Drive upload (supports Shared Drives)
├── engines/
│   ├── __init__.py
│   ├── source_fetcher.py            # SourceFetcher protocol
│   ├── aws_news_blog_scraper.py     # AWS News Blog RSS/HTML scraper
│   ├── purview_blog_scraper.py      # Microsoft Purview Blog RSS/HTML scraper
│   ├── article_normalizer.py        # RawArticle, NormalizedArticle, ScoredArticle dataclasses
│   ├── deduplication.py             # URL and title deduplication
│   ├── relevance_scorer.py          # Recency and relevance scoring
│   ├── summarizer.py                # Summary, LinkedIn angle, hashtag generation
│   ├── selector.py                  # Top N article selection
│   ├── csv_writer.py                # CSV output writer
│   └── observability.py             # RunMetrics and logging
└── output/
    ├── content_candidates_*.csv     # Generated CSV files
    └── run_log_*.json               # Run metrics JSON files

tests/
├── __init__.py
├── test_aws_scraper.py              # AWS scraper unit tests
├── test_purview_scraper.py          # Purview scraper unit tests
├── test_google_drive.py             # Google Drive connector tests
├── test_normalizer_properties.py    # Properties 3-6
├── test_deduplication_properties.py # Properties 7-10
├── test_scorer_properties.py        # Properties 11-13
├── test_summarizer_properties.py    # Properties 14-17
├── test_selector_properties.py      # Properties 18-20
├── test_csv_writer_properties.py    # Property 21
├── test_observability_properties.py # Property 22
├── test_config_properties.py        # Properties 23-24
├── test_source_fetcher_properties.py # Property 1
└── test_workflow_properties.py      # Property 2
```

## Workflow (curation pipeline)

1. Load settings from `.env` and environment variables
2. Fetch articles per source (failures isolated per source):
   - AWS News Blog: RSS feed at `https://aws.amazon.com/blogs/aws/feed/`
   - Microsoft Purview Blog: RSS feed at `https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=AzurePurviewBlog`
3. Normalize fields: title, canonical_url, published_date, author, summary_text
4. Deduplicate: by canonical URL first, then by normalized title (keep earliest)
5. Score relevance: recency (0-100) + relevance (0-100) → overall (weighted)
6. Generate LinkedIn metadata: summary, why_it_matters, linkedin_angle, hashtags
7. Select top N articles by overall score (default 10)
8. Write CSV to `src/output/content_candidates_YYYYMMDD_HHMMSS.csv`
9. Upload CSV to Google Drive Shared Drive folder
10. Write run log to `src/output/run_log_YYYYMMDD_HHMMSS.json`

## Data Models

### RawArticle
Raw article from source before normalization.

### NormalizedArticle
Standardized article with canonical URL and parsed date.

### ScoredArticle
Final article with scores and generated LinkedIn metadata.

## Configuration (via .env)

```
GOOGLE_DRIVE_FOLDER_ID=<folder_id>        # or GOOGLE_DRIVE_OUTPUT_FOLDER_ID
MAX_ARTICLES_PER_SOURCE=50
RECENCY_WINDOW_DAYS=30
TARGET_SELECTED=10
MIN_SCORE_THRESHOLD=0.0
RECENCY_WEIGHT=0.4
RELEVANCE_WEIGHT=0.6
REQUEST_DELAY_SECONDS=1.0
MAX_RETRIES=3
```

## Observability outputs

Each run reports:
- fetched_count_by_source (dict)
- normalized_count, deduped_count, selected_count (int)
- top_topics (list of matched themes)
- average_score_overall (float)
- upload_status: "success", "failed", or "skipped"
- uploaded_file_id (if successful)
- errors (list of error messages)
