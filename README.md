# Content Agent

An AI-assisted workflow that discovers, scores, and curates timely cloud and security articles for LinkedIn post creation, then exports a CSV to Google Drive.

## Purpose

Orchestrate steps to:
- Scrape new articles from AWS News Blog and Microsoft Purview Blog
- Normalize and deduplicate articles across sources
- Score articles for relevance to security-first cloud modernization themes
- Generate LinkedIn-ready metadata (summaries, angles, hashtags)
- Output a CSV to Google Drive for content drafting workflows

## Quick Start

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Google Drive folder ID

# Run
python -m src.main           # Production run
python -m src.main -v        # Verbose logging
python -m src.main --mock    # Mock mode (no live fetching)
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_DRIVE_FOLDER_ID` | required | Google Drive folder ID for CSV upload |
| `MAX_ARTICLES_PER_SOURCE` | 50 | Max articles fetched per source |
| `RECENCY_WINDOW_DAYS` | 30 | Days for recency scoring window |
| `TARGET_SELECTED` | 10 | Number of top articles to select |
| `MIN_SCORE_THRESHOLD` | 0.0 | Minimum score to include article |
| `RECENCY_WEIGHT` | 0.4 | Weight for recency in overall score |
| `RELEVANCE_WEIGHT` | 0.6 | Weight for relevance in overall score |
| `REQUEST_DELAY_SECONDS` | 1.0 | Delay between HTTP requests |
| `MAX_RETRIES` | 3 | Max retries for failed requests |

### Google Drive Setup

1. Create a service account in Google Cloud Console
2. Download credentials as `credentials.json` (place in project root)
3. Share your Google Drive folder with the service account email
4. For Shared Drives, grant "Contributor" access

## Sources

| Source | RSS Feed |
|--------|----------|
| AWS News Blog | `https://aws.amazon.com/blogs/aws/feed/` |
| Microsoft Purview Blog | `https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=AzurePurviewBlog` |

## Scoring Algorithm

Articles are scored on two dimensions:

- **Recency (0-100)**: Linear decay from 100 (today) to 0 (at recency window edge)
- **Relevance (0-100)**: Keyword matching across security and cloud themes

**Overall Score**: `(recency_weight × recency) + (relevance_weight × relevance)`

### Relevance Themes

- Cloud security, zero trust, encryption
- IAM, authentication, MFA, RBAC
- Governance, compliance, GDPR, HIPAA, SOC 2
- Data protection, DLP, data classification
- Auditing, retention, logging
- DevSecOps, automation, policy-as-code

## Output

### CSV File

Uploaded to Google Drive: `content_candidates_YYYYMMDD_HHMMSS.csv`

| Field | Description |
|-------|-------------|
| source | AWS News Blog or Microsoft Purview Blog |
| title | Article title |
| url | Canonical URL |
| published_date | ISO format datetime |
| author | Author name |
| summary | 1-3 sentence summary |
| key_topics | Matched themes (semicolon-delimited) |
| why_it_matters | Security-first framing |
| suggested_linkedin_angle | LinkedIn angle |
| suggested_hashtags | Hashtags (semicolon-delimited) |
| score_overall | Weighted score (0-100) |
| score_recency | Recency score (0-100) |
| score_relevance | Relevance score (0-100) |
| collected_at | Collection timestamp |

### Run Log

Local JSON file: `src/output/run_log_YYYYMMDD_HHMMSS.json`

## Testing

```bash
pytest                  # Run all tests
pytest --cov=src        # With coverage
pytest -v               # Verbose output
```

## Project Structure

```
src/
├── main.py                 # CLI entry point
├── agent/
│   ├── runner.py           # Main runner
│   └── workflow.py         # Pipeline orchestrator
├── config/
│   └── settings.py         # Settings dataclass
├── connectors/
│   └── google_drive.py     # Google Drive upload
├── engines/
│   ├── aws_news_blog_scraper.py
│   ├── purview_blog_scraper.py
│   ├── article_normalizer.py
│   ├── deduplication.py
│   ├── relevance_scorer.py
│   ├── summarizer.py
│   ├── selector.py
│   ├── csv_writer.py
│   └── observability.py
└── output/                 # Generated files
```

## License

Private project - not for distribution.
