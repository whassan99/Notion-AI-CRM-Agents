"""Config introspection tool."""

from typing import Any

from config import Config


def get_config() -> dict[str, Any]:
    """Return current CRM agent configuration.

    Includes ICP criteria, priority thresholds, and Notion property name mappings
    so Claude Code knows how to read/write the correct Notion properties.
    """
    return {
        "icp_criteria": Config.ICP_CRITERIA,
        "thresholds": {
            "high_icp_min": Config.HIGH_ICP_MIN,
            "high_recency_max_days": Config.HIGH_RECENCY_MAX,
            "low_icp_max": Config.LOW_ICP_MAX,
            "low_stale_days": Config.LOW_STALE_DAYS,
            "stale_days_threshold": Config.STALE_DAYS_THRESHOLD,
        },
        "notion_input_properties": {
            "company": Config.NOTION_PROP_COMPANY,
            "website": Config.NOTION_PROP_WEBSITE,
            "notes": Config.NOTION_PROP_NOTES,
            "last_contacted": Config.NOTION_PROP_LAST_CONTACTED,
            "status": Config.NOTION_PROP_STATUS,
        },
        "notion_output_properties": {
            "icp_score": Config.NOTION_PROP_ICP_SCORE,
            "confidence_score": Config.NOTION_PROP_CONFIDENCE,
            "icp_reasoning": Config.NOTION_PROP_ICP_REASONING,
            "research_brief": Config.NOTION_PROP_RESEARCH_BRIEF,
            "research_confidence": Config.NOTION_PROP_RESEARCH_CONFIDENCE,
            "research_citations": Config.NOTION_PROP_RESEARCH_CITATIONS,
            "research_source_count": Config.NOTION_PROP_RESEARCH_SOURCE_COUNT,
            "research_providers": Config.NOTION_PROP_RESEARCH_PROVIDERS,
            "signal_type": Config.NOTION_PROP_SIGNAL_TYPE,
            "signal_strength": Config.NOTION_PROP_SIGNAL_STRENGTH,
            "signal_date": Config.NOTION_PROP_SIGNAL_DATE,
            "signal_reasoning": Config.NOTION_PROP_SIGNAL_REASONING,
            "priority_tier": Config.NOTION_PROP_PRIORITY_TIER,
            "priority_reasoning": Config.NOTION_PROP_PRIORITY_REASONING,
            "stale_flag": Config.NOTION_PROP_STALE_FLAG,
            "next_action": Config.NOTION_PROP_NEXT_ACTION,
            "action_reasoning": Config.NOTION_PROP_ACTION_REASONING,
            "action_confidence": Config.NOTION_PROP_ACTION_CONFIDENCE,
        },
        "valid_actions": ["outreach_now", "reengage", "nurture", "enrich_data", "hold"],
        "valid_priority_tiers": ["high", "medium", "low", "review"],
        "signal_types": ["buying_intent", "funding", "leadership_change", "hiring", "technology_initiative", "none"],
    }
