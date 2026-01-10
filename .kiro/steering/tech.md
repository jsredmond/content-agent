# Tech Stack and Development Workflow (Content Agent)

## Runtime
- Python 3.10+
- Virtual environment in `.venv`

## Dependencies

Core:
- requests
- pandas
- python-dotenv

Recommended for scraping and normalization:
- beautifulsoup4 plus lxml (HTML parsing)
- feedparser (use RSS when available, fallback to HTML parsing)
- python-dateutil (date parsing)
- tenacity (retries and backoff)
- tldextract (URL normalization)

Optional (only if needed):
- readability-lxml (article extraction)
- newspaper3k (article extraction, heavier dependency)

## Environment and secrets
- `.env` for local config, do not commit
- `credentials.json` for Google Drive service account, do not commit

## Run commands

Create and activate venv:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
