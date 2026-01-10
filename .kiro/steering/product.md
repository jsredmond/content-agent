# Content Agent (Blog Event Scraper)

An AI-assisted workflow that discovers, scores, and curates timely cloud and security articles for LinkedIn post creation, then exports a CSV to Google Drive.

## Purpose

Orchestrate steps to:
- Scrape new articles from AWS News Blog and Microsoft Purview Blog
- Normalize and deduplicate articles across sources
- Score articles for relevance to security-first cloud modernization themes
- Generate LinkedIn-ready metadata (summaries, angles, hashtags)
- Output a CSV to Google Drive for content drafting workflows
- Ensure every run produces a usable artifact (graceful error handling)

## Audience and Outcome

Designed for content generation workflows supporting:
- CIO, CISO, CTO, IT Director audiences
- Regulated industries (finance, healthcare, government, professional services)
- Security-first messaging paired with practical modernization guidance

## Sources

### AWS News Blog
- RSS feed preferred, HTML fallback
- Extracts: title, link, published date, author, teaser

### Microsoft Purview Blog
- RSS feed preferred, HTML fallback
- Extracts: title, link, published date, author, teaser

## Curation Rules

An article is "good" if it is:
- **Recent**: Published within the recency window (default 30 days)
- **Relevant**: Matches at least one core theme:
  - Cloud security, identity, governance, compliance
  - Data security, data governance, DLP, auditing, retention
  - DevSecOps, automation, policy-as-code, security monitoring
  - Practical rollout guidance, reference architectures, product updates
- **Useful for LinkedIn**: Clear takeaway, actionable guidance, or meaningful announcement

## Run Behavior

| Setting | Default | Description |
|---------|---------|-------------|
| `max_articles_per_source` | 50 | Max articles fetched per source |
| `target_selected` | 10 | Number of top articles to select |
| `recency_days` | 30 | Recency scoring window |
| `recency_weight` | 0.4 | Weight for recency in overall score |
| `relevance_weight` | 0.6 | Weight for relevance in overall score |

If fewer than target are found, export what is available with a summary in logs.

## Output

### Primary Deliverable
CSV uploaded to Google Drive Shared Drive:
- Filename: `content_candidates_YYYYMMDD_HHMMSS.csv`

### CSV Schema
| Field | Description |
|-------|-------------|
| source | AWS News Blog or Microsoft Purview Blog |
| title | Article title |
| url | Canonical URL (no tracking params) |
| published_date | ISO format datetime |
| author | Author name (if available) |
| summary | 1-3 sentence summary |
| key_topics | Semicolon-delimited matched themes |
| why_it_matters | Security-first framing statement |
| suggested_linkedin_angle | Single sentence LinkedIn angle |
| suggested_hashtags | Semicolon-delimited hashtags |
| score_overall | 0-100 weighted score |
| score_recency | 0-100 recency score |
| score_relevance | 0-100 relevance score |
| collected_at | Collection timestamp |

## Guardrails

- Deduplicate by canonical URL, then by normalized title
- Strip tracking parameters from URLs
- Keep earliest article when duplicates found
- Continue processing if one source fails
- Log all errors without failing entire run

## LinkedIn Workflow

Use the exported CSV to draft 3-5 LinkedIn posts per run that connect:
1. The article's update or announcement
2. The security or compliance implication
3. The modernization outcome for the audience

## Keyword Themes

The relevance scorer matches against these themes:
- **cloud_security**: cloud security, security posture, threat detection, zero trust, encryption
- **identity_and_access**: IAM, authentication, authorization, SSO, MFA, RBAC
- **governance_and_compliance**: governance, compliance, regulatory, audit, GDPR, HIPAA, SOC 2
- **data_protection**: data protection, DLP, data classification, sensitive data, PII
- **auditing_and_retention**: auditing, audit log, retention, logging, monitoring
- **devsecops**: DevSecOps, automation, policy-as-code, IaC, CI/CD security, shift left
