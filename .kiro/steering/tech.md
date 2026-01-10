# Tech Stack and Development Workflow (Content Agent)

## Runtime
- Python 3.10+
- Virtual environment in `.venv`

## Dependencies (requirements.txt)

```
requests
pandas
python-dotenv
beautifulsoup4
lxml
feedparser
python-dateutil
tenacity
tldextract
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
hypothesis
pytest
pytest-cov
```

## Environment and secrets

Required files (do not commit):
- `.env` - Configuration and folder IDs
- `credentials.json` - Google Cloud service account credentials

### .env configuration

```bash
# Google Drive (Shared Drive supported)
GOOGLE_DRIVE_FOLDER_ID=<your_folder_id>
# Alternative: GOOGLE_DRIVE_OUTPUT_FOLDER_ID=<your_folder_id>

# Pipeline settings (optional, defaults shown)
MAX_ARTICLES_PER_SOURCE=50
RECENCY_WINDOW_DAYS=30
TARGET_SELECTED=10
MIN_SCORE_THRESHOLD=0.0
RECENCY_WEIGHT=0.4
RELEVANCE_WEIGHT=0.6
REQUEST_DELAY_SECONDS=1.0
MAX_RETRIES=3
```

### Google Drive Setup

1. Create a service account in Google Cloud Console
2. Download credentials as `credentials.json`
3. Share your Google Drive folder with the service account email
4. For Shared Drives (Team Drives), grant "Contributor" access

## Run commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run pipeline
python -m src.main           # Production run
python -m src.main -v        # Verbose logging
python -m src.main --mock    # Mock mode (no live fetching)

# Testing
pytest                       # Run all tests
pytest --cov=src             # With coverage
pytest -v                    # Verbose output
```

## Source RSS Feeds

### AWS News Blog
- RSS: `https://aws.amazon.com/blogs/aws/feed/`
- Fallback HTML: `https://aws.amazon.com/blogs/aws/`

### Microsoft Purview Blog
- RSS: `https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=AzurePurviewBlog`
- Fallback HTML: `https://techcommunity.microsoft.com/t5/azure-purview-blog/bg-p/AzurePurviewBlog`

## Scoring Algorithm

### Recency Score (0-100)
- 100 for articles published today
- Linear decay to 0 at recency window edge (default 30 days)
- 0 for articles outside window or with no date

### Relevance Score (0-100)
Keyword matching across themes:
- cloud_security
- identity_and_access
- governance_and_compliance
- data_protection
- auditing_and_retention
- devsecops

### Overall Score
```
overall = (recency_weight * recency) + (relevance_weight * relevance)
```
Default: 0.4 * recency + 0.6 * relevance

## Output Files

### CSV Output
- Location: `src/output/content_candidates_YYYYMMDD_HHMMSS.csv`
- Encoding: UTF-8
- Multi-value delimiter: semicolon (`;`)

### Run Log
- Location: `src/output/run_log_YYYYMMDD_HHMMSS.json`
- Contains: counts, topics, scores, upload status, errors

## Testing

### Property-Based Tests (Hypothesis)
24 correctness properties validated with 100+ iterations each:
- Properties 1-2: Source fetching
- Properties 3-6: Normalization
- Properties 7-10: Deduplication
- Properties 11-13: Scoring
- Properties 14-17: Summarization
- Properties 18-20: Selection
- Property 21: CSV output
- Property 22: Observability
- Properties 23-24: Configuration

### Unit Tests
- AWS scraper RSS/HTML parsing
- Purview scraper RSS/HTML parsing
- Google Drive upload success/failure handling

## Development Workflow

Commit after each major task with descriptive messages:
```
feat: add aws news blog scraper
feat: add purview blog scraper
fix: update Purview blog RSS URL
fix: add Shared Drive support for Google Drive upload
test: add scraper parsing tests
chore: update steering docs
```

Never commit:
- `.env`
- `credentials.json`
- `src/output/*.csv`
- `src/output/*.json`
