# Notion Database Setup

Two options: duplicate a template (fastest) or create the database manually.

## Option A: Duplicate Template (Recommended)

<!-- TODO: Add template link once published -->
1. Open the template link: *(coming soon)*
2. Click "Duplicate" in the top-right
3. The database will appear in your Notion workspace with all columns pre-configured

Then skip to [Step 3: Connect the Integration](#step-3-connect-the-integration).

## Option B: Create Manually

### Step 1: Create a Notion Integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"New integration"**
3. Give it a name (e.g., "CRM Copilot")
4. Select your workspace
5. Click **"Submit"**
6. Copy the **Internal Integration Token** — this is your `NOTION_API_KEY`

### Step 2: Create the Database

Create a new full-page database in Notion with these columns:

#### Input Columns (you fill these in)

| Column Name | Type | Required? | Purpose |
|-------------|------|-----------|---------|
| `Company` | Title | Yes | The lead's company name |
| `Website` | URL | Recommended | Company website for research context |
| `Notes` | Text | Recommended | Any context about the lead (stage, conversations, signals) |
| `Last Contacted` | Date | Recommended | When you last reached out (used for staleness) |
| `Status` | Select | Optional | Current status (e.g., New, Contacted, Qualified) |

#### Output Columns (auto-created by setup wizard)

If you run `python main.py --setup` and choose schema bootstrap, these are created automatically.
You can also add them manually if you prefer:

| Column Name | Type | Purpose |
|-------------|------|---------|
| `icp_score` | Number | ICP fit score (0-100) |
| `confidence_score` | Number | How much data was available for scoring (0-100) |
| `icp_reasoning` | Text | Why the lead got this score |
| `research_brief` | Text | Market research summary |
| `research_confidence` | Select | Research confidence (`high`, `medium`, `low`) |
| `research_citations` | Text | Source list used for research |
| `research_source_count` | Number | Number of sources used |
| `research_providers` | Text | Provider trace (which enrichment steps ran) |
| `priority_tier` | Select | HIGH / MEDIUM / LOW / REVIEW |
| `priority_reasoning` | Text | Why this priority was assigned |
| `stale_flag` | Checkbox | True if the lead hasn't been contacted recently |
| `next_action` | Select | Suggested next step (`outreach_now`, etc.) |
| `action_reasoning` | Text | Why that action was chosen |
| `action_confidence` | Select | Action confidence (`high`, `medium`, `low`) |

> **Tip:** You can rename columns to match your preferences by updating the `NOTION_PROP_*` variables in `.env`. See `.env.example` for details.

### Step 3: Connect the Integration

1. Open your CRM database in Notion
2. Click the **"..."** menu in the top-right corner
3. Scroll down to **"Connections"**
4. Click **"Add connections"**
5. Search for and select the integration you created in Step 1

> **Important:** The integration can only access databases you explicitly share with it. If you skip this step, you'll get a "Database not found" error.

### Step 4: Get the Database ID

1. Open your database in Notion
2. Look at the URL in your browser:
   ```
   https://www.notion.so/your-workspace/a4125267378749029859ac2a64ac122f?v=...
   ```
3. The database ID is the long string of letters and numbers after the workspace name:
   `a4125267378749029859ac2a64ac122f`
4. Copy this — it's your `NOTION_DATABASE_ID`

> **Note:** The ID may include dashes (e.g., `a4125267-3787-4902-9859-ac2a64ac122f`). Both formats work.

### Step 5: Add to .env

```bash
NOTION_API_KEY=secret_your_token_here
NOTION_DATABASE_ID=your_database_id_here
```

### Verify It Works

```bash
python main.py --limit 1
```

If everything is connected, you'll see one lead processed and the output columns populated in Notion.
