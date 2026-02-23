# Notion AI CRM Copilot

AI agents that turn raw Notion leads into scored, researched, and prioritized opportunities you can act on faster.


## Description

Notion AI CRM Copilot reads leads from a Notion database, runs 3 focused AI agents, and writes insights back to Notion:

- ICP Scoring Agent: scores lead fit (0-100) with confidence.
- Market Research Agent: generates a concise research brief.
- Prioritization Agent: assigns `high`, `medium`, `low`, or `review`.

The system is designed to be practical and transparent: configurable thresholds, clear outputs, and graceful handling of missing data.

## Before / After

| Before | After |
|--------|-------|
| Manual lead-by-lead research | Automated research brief per lead |
| Gut-feel qualification | Rubric-based ICP score + confidence |
| Unclear follow-up order | Priority tier with reasoning |
| Stale leads missed | Automatic stale lead flag |

## Real Example

Example Lead (Before / After)

Before

- Company: ExampleCo
- Website: `example.com`
- Notes: B2B SaaS selling to hospitals

After

- ICP Score: `82`
- Confidence: `70`
- Reasoning:
  - Strong industry fit
  - Clear B2B use case
  - Budget signals in notes

## Quick Start

### 1. Clone and install

```bash
git clone <your-repo-url>
cd notion-ai-crm
pip install -r requirements.txt
```

### 2. Configure environment

```bash
# Recommended: guided setup (writes .env and can auto-create output columns)
python main.py --setup

# Or manual setup:
cp .env.example .env
```

Fill in:

- `NOTION_API_KEY`
- `NOTION_DATABASE_ID`
- `CLAUDE_API_KEY`

For Notion database/integration setup, follow [`NOTION_SETUP.md`](NOTION_SETUP.md).

### 3. Run

```bash
# Dry run (no Notion writes)
python main.py --dry-run

# Process first 3 leads
python main.py --limit 3

# Process all leads
python main.py

# Force a full refresh (ignore incremental state)
python main.py --full-refresh
```

By default, runs are incremental: unchanged leads that already have core outputs are skipped.

## Lightweight Evaluation

- Tested on a small set of leads.
- Compared outputs against human judgment for fit and priority.
- Directionally useful for triage, not perfect.
- Works best when input data quality is good (website, notes, recent contact context).

## What The Agents Do

### ICP Scoring Agent

- Uses a 5-dimension rubric.
- Produces:
  - `icp_score` (0-100)
  - `confidence_score` (0-100)
  - `icp_reasoning`

### Market Research Agent

- Produces a short lead research brief.
- Flags lower-quality inputs and marks speculative reasoning.
- Appends source citations (website/search/CRM notes) for auditability.
- Outputs `research_confidence` and `research_source_count`.

### Prioritization Agent

- Uses deterministic rules for obvious cases.
- Uses the LLM for edge cases.
- Produces:
  - `priority_tier`
  - `priority_reasoning`
  - `stale_flag`

### Action Agent

- Recommends next step:
  - `outreach_now`, `reengage`, `nurture`, `enrich_data`, `hold`
- Produces:
  - `next_action`
  - `action_reasoning`
  - `action_confidence`

## Configuration

Set behavior through `.env`:

```dotenv
HIGH_ICP_MIN=75
HIGH_RECENCY_MAX=10
LOW_ICP_MAX=40
LOW_STALE_DAYS=45
STALE_DAYS_THRESHOLD=14
INCREMENTAL_ENABLED=true
PIPELINE_STATE_FILE=.pipeline_state.json
```

Optional: map custom Notion column names:

```dotenv
NOTION_PROP_COMPANY=Company
NOTION_PROP_WEBSITE=Website
NOTION_PROP_NOTES=Notes
```

## Limitations

- No live web browsing or scraping; research uses provided CRM data and model knowledge.
- ICP quality depends on how clear your ICP criteria are.
- Large Notion batches can be slow due to API limits.
- AI output can be wrong or incomplete; verify important decisions manually.

## Troubleshooting

- `CLAUDE_API_KEY is missing`:
  - Confirm `.env` exists and includes `CLAUDE_API_KEY=...`.
- `Database not found`:
  - Verify `NOTION_DATABASE_ID` and confirm your Notion integration has access.
- Leads processed but no Notion updates:
  - Confirm output properties exist in your Notion database schema.

## Public Repo Safety Checklist

- `.env` is gitignored (keep real keys only in local `.env`).
- `.env.example` contains placeholders only.
- No hardcoded secrets in source files.
- Rotate keys immediately if a real key was ever committed.

## License

MIT - see [`LICENSE`](LICENSE).
