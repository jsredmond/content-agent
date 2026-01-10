# Project Structure (Content Agent)

This file describes the intended system layout and the required modules so Kiro generates an implementation spec that matches the actual workflow.

## Directory layout

src/
├── main.py
├── agent/
│   ├── config.py
│   ├── runner.py
│   └── workflow.py
├── config/
│   └── settings.py
├── connectors/
│   └── google_drive.py
├── engines/
│   ├── source_fetcher.py
│   ├── aws_news_blog_scraper.py
│   ├── purview_blog_scraper.py
│   ├── article_normalizer.py
│   ├── deduplication.py
│   ├── relevance_scorer.py
│   ├── summarizer.py
│   ├── selector.py
│   ├── csv_writer.py
│   └── observability.py
├── output/
│   ├── content_candidates_*.csv
│   └── run_log_*.json

## Workflow (curation pipeline)

1. Load settings and initialize run context
2. Fetch articles per source:
   - AWS News Blog scraper
   - Microsoft Purview blog scraper
3. Normalize fields:
   - title, canonical url, published date, author, summary text
4. Deduplicate:
   - by canonical url, then normalized title
5. Score relevance:
   - recency score (time decay)
   - relevance score (topic keywords and signals)
   - overall score (weighted)
6. Summarize and generate LinkedIn-ready metadata:
   - 1 to 3 sentence summary
   - why it matters (security-first framing)
   - suggested LinkedIn angle
   - suggested hashtags
7. Select top N items (default 10)
8. Write CSV artifact to `output/`
9. Upload CSV to Google Drive uploads folder
10. Emit run logs and metrics

## Configuration expectations

Settings should support:
- Google Drive uploads folder identifier or name
- per-source fetch limits
- recency window (days)
- scoring weights and keyword sets
- target selection count

## CSV schema (Content Candidates)

Required fields:
- source
- title
- url
- published_date
- author
- summary
- key_topics
- why_it_matters
- suggested_linkedin_angle
- suggested_hashtags
- score_overall
- score_recency
- score_relevance
- collected_at

## Observability outputs

Each run must report:
- fetched_count_by_source
- normalized_count
- deduped_count
- selected_count
- top_topics
- average_score_overall
- upload_status and uploaded_file_id (if available)
- errors and partial failures (per source)
