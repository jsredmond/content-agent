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

python -m src.main
python -m src.main --mock
python -m src.main -v

pytest
pytest --cov=src

Source scraping approach

Preferred:

Use RSS feeds when offered by the source (more stable, cleaner dates)

Fallback:

Fetch and parse HTML list pages

Extract:

title

link (canonical if present)

publish date (parse robustly)

author (if present)

teaser or first paragraph (for summarization input)

Rules:

Respect reasonable request pacing (sleep between requests, retries with backoff)

Store canonical URLs without tracking parameters when possible

Cache per-run fetch results to reduce repeated calls

Scoring guidance (simple, explainable)

Recency score:

Higher for more recent posts within the configured window

Relevance score:

Keyword and phrase matches across themes:

cloud security

identity and access

governance and compliance

data protection, DLP (data loss prevention)

auditing, retention

DevSecOps, automation, policy-as-code

Overall score:

overall = 0.4(recency) + 0.6(relevance) (default, configurable)

Output and Google Drive upload

Write CSV to src/output/:

content_candidates_YYYYMMDD_HHMMSS.csv

Upload that file to the configured Google Drive uploads folder via connectors/google_drive.py

Log the uploaded file id and final path

Observability outputs

Each run must report:

counts per stage: fetched, normalized, deduped, selected

per-source failures (do not fail the entire run if one source fails)

upload result (success, file id, folder id)

top keywords/topics among selected articles

Development workflow, required Git commits

Commit to git after each major task.

A major task is a coherent unit of work that introduces or modifies one engine module, changes routing logic, updates CSV schema, or adds tests.

Rules:

After each major task:

run tests relevant to the change

update docs if behavior or schema changed

commit to git with a descriptive message

Suggested commit message format:

feat: add aws news blog scraper

feat: add purview blog scraper

feat: add content curation csv export

chore: update docs and settings

test: add scraper parsing tests

Never commit secrets:

.env

credentials.json

any exported CSV outputs that contain real user or contact emails