"""
Configuration for the Notion AI CRM Copilot.

Loads environment variables, validates API keys, and provides
all configurable thresholds and property mappings.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Central configuration — all magic numbers and settings live here."""

    # --- API Keys ---
    NOTION_API_KEY: str = os.getenv("NOTION_API_KEY", "")
    NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "")
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    # --- Priority Thresholds ---
    HIGH_ICP_MIN: int = int(os.getenv("HIGH_ICP_MIN", "75"))
    HIGH_RECENCY_MAX: int = int(os.getenv("HIGH_RECENCY_MAX", "10"))
    LOW_ICP_MAX: int = int(os.getenv("LOW_ICP_MAX", "40"))
    LOW_STALE_DAYS: int = int(os.getenv("LOW_STALE_DAYS", "45"))
    STALE_DAYS_THRESHOLD: int = int(os.getenv("STALE_DAYS_THRESHOLD", "14"))

    # --- Slack Notifications ---
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    SLACK_ENABLED: bool = os.getenv("SLACK_ENABLED", "false").lower() in ("true", "1", "yes")

    # --- Web Research ---
    BRAVE_SEARCH_API_KEY: str = os.getenv("BRAVE_SEARCH_API_KEY", "")
    WEB_RESEARCH_ENABLED: bool = os.getenv("WEB_RESEARCH_ENABLED", "true").lower() in ("true", "1", "yes")
    WEB_RESEARCH_TIMEOUT: int = int(os.getenv("WEB_RESEARCH_TIMEOUT", "10"))
    WEB_RESEARCH_DELAY: float = float(os.getenv("WEB_RESEARCH_DELAY", "1.0"))
    WEB_RESEARCH_MAX_PAGES: int = int(os.getenv("WEB_RESEARCH_MAX_PAGES", "3"))

    # --- ICP Criteria (injected into prompt) ---
    ICP_CRITERIA: str = os.getenv(
        "ICP_CRITERIA",
        (
            "B2B SaaS companies with 50-500 employees, "
            "strong product-market fit indicators, "
            "actively investing in growth and technology, "
            "decision-makers accessible and engaged, "
            "budget availability signals present"
        ),
    )

    # --- Notion Property Name Mapping ---
    # Input properties (read from Notion)
    NOTION_PROP_COMPANY: str = os.getenv("NOTION_PROP_COMPANY", "Company")
    NOTION_PROP_WEBSITE: str = os.getenv("NOTION_PROP_WEBSITE", "Website")
    NOTION_PROP_NOTES: str = os.getenv("NOTION_PROP_NOTES", "Notes")
    NOTION_PROP_LAST_CONTACTED: str = os.getenv("NOTION_PROP_LAST_CONTACTED", "Last Contacted")
    NOTION_PROP_STATUS: str = os.getenv("NOTION_PROP_STATUS", "Status")

    # Output properties (written by agents)
    NOTION_PROP_ICP_SCORE: str = os.getenv("NOTION_PROP_ICP_SCORE", "icp_score")
    NOTION_PROP_CONFIDENCE: str = os.getenv("NOTION_PROP_CONFIDENCE", "confidence_score")
    NOTION_PROP_ICP_REASONING: str = os.getenv("NOTION_PROP_ICP_REASONING", "icp_reasoning")
    NOTION_PROP_RESEARCH_BRIEF: str = os.getenv("NOTION_PROP_RESEARCH_BRIEF", "research_brief")
    NOTION_PROP_PRIORITY_TIER: str = os.getenv("NOTION_PROP_PRIORITY_TIER", "priority_tier")
    NOTION_PROP_PRIORITY_REASONING: str = os.getenv("NOTION_PROP_PRIORITY_REASONING", "priority_reasoning")
    NOTION_PROP_STALE_FLAG: str = os.getenv("NOTION_PROP_STALE_FLAG", "stale_flag")
    NOTION_PROP_NEXT_ACTION: str = os.getenv("NOTION_PROP_NEXT_ACTION", "next_action")
    NOTION_PROP_ACTION_REASONING: str = os.getenv("NOTION_PROP_ACTION_REASONING", "action_reasoning")
    NOTION_PROP_ACTION_CONFIDENCE: str = os.getenv("NOTION_PROP_ACTION_CONFIDENCE", "action_confidence")
    NOTION_PROP_RESEARCH_CONFIDENCE: str = os.getenv("NOTION_PROP_RESEARCH_CONFIDENCE", "research_confidence")
    NOTION_PROP_RESEARCH_CITATIONS: str = os.getenv("NOTION_PROP_RESEARCH_CITATIONS", "research_citations")
    NOTION_PROP_RESEARCH_SOURCE_COUNT: str = os.getenv("NOTION_PROP_RESEARCH_SOURCE_COUNT", "research_source_count")

    @classmethod
    def validate(cls, require_notion: bool = True) -> bool:
        """
        Validate configuration with actionable error messages.

        Args:
            require_notion: If False, skip Notion key validation (for dry-run).

        Raises:
            ValueError with specific guidance on how to fix the issue.
        """
        errors = []

        # Claude API key
        if not cls.CLAUDE_API_KEY:
            errors.append(
                "CLAUDE_API_KEY is missing.\n"
                "  Get one at: https://console.anthropic.com/settings/keys"
            )
        elif not cls.CLAUDE_API_KEY.startswith("sk-ant-"):
            errors.append(
                "CLAUDE_API_KEY doesn't look right (should start with 'sk-ant-').\n"
                "  Check: https://console.anthropic.com/settings/keys"
            )

        if require_notion:
            # Notion API key
            if not cls.NOTION_API_KEY:
                errors.append(
                    "NOTION_API_KEY is missing.\n"
                    "  Create an integration at: https://www.notion.so/my-integrations"
                )
            elif not (
                cls.NOTION_API_KEY.startswith("secret_")
                or cls.NOTION_API_KEY.startswith("ntn_")
            ):
                errors.append(
                    "NOTION_API_KEY doesn't look right (should start with 'secret_' or 'ntn_').\n"
                    "  Check: https://www.notion.so/my-integrations"
                )

            # Notion database ID
            if not cls.NOTION_DATABASE_ID:
                errors.append(
                    "NOTION_DATABASE_ID is missing.\n"
                    "  Find it in your Notion database URL:\n"
                    "  https://notion.so/workspace/[DATABASE_ID]?v=..."
                )
            elif len(cls.NOTION_DATABASE_ID.replace("-", "")) != 32:
                errors.append(
                    "NOTION_DATABASE_ID doesn't look right (should be 32 hex characters).\n"
                    "  Find it in your Notion database URL:\n"
                    "  https://notion.so/workspace/[DATABASE_ID]?v=..."
                )

        if errors:
            raise ValueError("\n\n".join(errors))

        return True
