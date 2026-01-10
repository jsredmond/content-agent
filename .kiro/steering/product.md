# Content Agent (Blog Event Scraper)

An AI-assisted workflow that discovers, scores, and curates timely cloud and security articles for LinkedIn post creation, then exports a CSV to the Google Drive uploads folder.

## Purpose

Orchestrate steps to:
- Scrape new articles from:
  - AWS News Blog (AWS Blog)
  - Microsoft Purview blog
- Normalize and deduplicate articles across sources
- Score articles for relevance to Heliobright’s positioning (security-first cloud modernization)
- Output a Google Drive-ready CSV of high-quality article links and metadata for LinkedIn drafting
- Ensure every run produces a usable artifact (no silent failures)

## Audience and outcome

Designed for content generation workflows that support:
- CIO, CISO, CTO, IT Director audiences
- Regulated industries (finance, healthcare, government, professional services)
- Security-first messaging paired with practical modernization guidance

## Sources (initial)

### AWS
- AWS News Blog (AWS Blog)

### Microsoft
- Microsoft Purview blog

## Curation rules (what “good” means)

An article is “good” if it is:
- Recent (default: published within the last 30 days)
- Relevant to at least one core theme:
  - Cloud security, identity, governance, compliance
  - Data security, data governance, DLP (data loss prevention), auditing, retention
  - DevSecOps, automation, policy-as-code, security monitoring
  - Practical rollout guidance, reference architectures, or product updates with clear impact
- Useful for LinkedIn: clear takeaway, actionable guidance, or meaningful announcement

## Run behavior

- `max_articles_per_source`: default 50 fetched
- `target_selected`: default 10 curated items
- `recency_days`: default 30
- If fewer than target are found, export what is available and include a short run summary in logs.

## Output

### Primary deliverable
A CSV uploaded to the Google Drive uploads folder:
- `content_candidates_YYYYMMDD_HHMMSS.csv`

### CSV schema (required)
- `source` (AWS News Blog, Microsoft Purview blog)
- `title`
- `url` (canonical)
- `published_date`
- `author` (if available)
- `summary` (1 to 3 sentences)
- `key_topics` (semicolon-delimited)
- `why_it_matters` (1 to 2 sentences, plain English, security-first framing)
- `suggested_linkedin_angle` (1 sentence)
- `suggested_hashtags` (semicolon-delimited)
- `score_overall` (0 to 100)
- `score_recency` (0 to 100)
- `score_relevance` (0 to 100)
- `collected_at` (timestamp)

## Guardrails

- Deduplicate by canonical URL, then by normalized title
- Do not include tracking parameters in stored URLs when a clean canonical URL is available
- Do not include low-signal content (job posts, event listings without substance, thin announcements)
- Keep language calm, factual, and free of hype

## Call to action (internal workflow)
Use the exported CSV to draft 3 to 5 LinkedIn posts per run that connect:
- the article’s update,
- the security or compliance implication,
- the modernization outcome.

Not sure where to start? Contact us for a free consultation.
