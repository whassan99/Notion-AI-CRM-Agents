"""
CRM Agent MCP Server.

Exposes CRM lead analysis capabilities as MCP tools for Claude Code.
Deterministic agents run directly; LLM-needing agents return structured
prompts for Claude Code to reason over.
"""

import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path so agents/config can be imported
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

from tools.icp_tools import score_icp_fit, parse_icp_result
from tools.signal_tools import detect_signals
from tools.priority_tools import determine_priority, parse_priority_result
from tools.action_tools import recommend_action, parse_action_result
from tools.research_tools import generate_research_prompt
from tools.config_tools import get_config

mcp = FastMCP(
    "crm-agent",
    instructions=(
        "CRM lead analysis tools. Use detect_signals for instant signal detection. "
        "For ICP scoring: call score_icp_fit to get a prompt, reason over it, then "
        "pass your JSON answer to parse_icp_result. Same pattern for priority and action "
        "when needs_llm=True. Use get_config to see Notion property mappings."
    ),
)


@mcp.tool()
def tool_score_icp_fit(
    company_name: str,
    website: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Generate an ICP (Ideal Customer Profile) scoring prompt.

    Returns a structured prompt with a 5-dimension rubric (0-20 each, total 0-100)
    for you to reason over. After reasoning, pass your JSON answer to parse_icp_result.

    Args:
        company_name: The company name to score.
        website: Company website URL.
        notes: CRM notes about the company.
    """
    return score_icp_fit(company_name, website, notes)


@mcp.tool()
def tool_parse_icp_result(raw_json: str) -> dict[str, Any]:
    """Validate and clean an ICP scoring JSON response.

    Takes the raw JSON string you produced when reasoning over the ICP prompt,
    validates dimension scores (clamped 0-20), recalculates total from dimensions,
    and returns a clean result.

    Args:
        raw_json: Your JSON response from the ICP scoring prompt.
    """
    return parse_icp_result(raw_json)


@mcp.tool()
def tool_detect_signals(
    company_name: str = "",
    notes: str = "",
    status: str = "",
    research_brief: str = "",
    last_contacted: str | None = None,
    last_edited_time: str | None = None,
) -> dict[str, Any]:
    """Detect trigger signals from lead data using pattern matching.

    Runs entirely server-side (no LLM needed). Detects: buying_intent,
    funding, leadership_change, hiring, technology_initiative.

    Args:
        company_name: Company name.
        notes: CRM notes text to scan for signals.
        status: Lead status.
        research_brief: Research brief text to also scan.
        last_contacted: ISO date of last contact (for signal dating).
        last_edited_time: ISO timestamp of last edit (fallback for signal dating).
    """
    return detect_signals(
        company_name=company_name,
        notes=notes,
        status=status,
        research_brief=research_brief,
        last_contacted=last_contacted,
        last_edited_time=last_edited_time,
    )


@mcp.tool()
def tool_determine_priority(
    icp_score: int | None = None,
    last_contacted: str | None = None,
    status: str = "",
    company_name: str = "",
    signal_type: str = "none",
    signal_strength: str = "none",
) -> dict[str, Any]:
    """Determine lead priority tier.

    Uses deterministic rules for clear cases (high ICP + recent = HIGH,
    low ICP = LOW, stale = LOW). Returns needs_llm=False with the result,
    or needs_llm=True with a prompt for you to reason over edge cases.

    If needs_llm=True, reason over the prompt, then pass your JSON answer
    to parse_priority_result along with the context fields.

    Args:
        icp_score: ICP score (0-100). None or <0 triggers "review" tier.
        last_contacted: ISO date of last contact.
        status: Lead status (e.g. "Qualified", "New").
        company_name: Company name.
        signal_type: Detected signal type (from detect_signals).
        signal_strength: Signal strength "high"/"medium"/"none".
    """
    return determine_priority(
        icp_score=icp_score,
        last_contacted=last_contacted,
        status=status,
        company_name=company_name,
        signal_type=signal_type,
        signal_strength=signal_strength,
    )


@mcp.tool()
def tool_parse_priority_result(
    raw_json: str,
    stale_flag: bool = False,
    days_since_contact: int = 999,
    icp_score: int = 50,
    signal_type: str = "none",
    signal_strength: str = "none",
) -> dict[str, Any]:
    """Validate a priority JSON response and apply signal boost.

    Use this after reasoning over a priority prompt (when needs_llm was True).

    Args:
        raw_json: Your JSON response from the priority prompt.
        stale_flag: From determine_priority result.
        days_since_contact: From determine_priority result.
        icp_score: The lead's ICP score.
        signal_type: Detected signal type.
        signal_strength: Signal strength.
    """
    return parse_priority_result(
        raw_json=raw_json,
        stale_flag=stale_flag,
        days_since_contact=days_since_contact,
        icp_score=icp_score,
        signal_type=signal_type,
        signal_strength=signal_strength,
    )


@mcp.tool()
def tool_recommend_action(
    priority_tier: str = "review",
    stale_flag: bool = False,
    icp_score: int | None = None,
    research_confidence: str = "medium",
    company_name: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Recommend the next best CRM action for a lead.

    Deterministic for clear cases (review→enrich, low→nurture, high+recent→outreach).
    Returns needs_llm=False with result, or needs_llm=True with prompt for ambiguous cases.

    Args:
        priority_tier: Lead priority ("high", "medium", "low", "review").
        stale_flag: Whether the lead is stale.
        icp_score: ICP score (0-100).
        research_confidence: Research data quality ("high", "medium", "low").
        company_name: Company name.
        notes: CRM notes.
    """
    return recommend_action(
        priority_tier=priority_tier,
        stale_flag=stale_flag,
        icp_score=icp_score,
        research_confidence=research_confidence,
        company_name=company_name,
        notes=notes,
    )


@mcp.tool()
def tool_parse_action_result(raw_json: str) -> dict[str, Any]:
    """Validate an action recommendation JSON response.

    Use this after reasoning over an action prompt (when needs_llm was True).

    Args:
        raw_json: Your JSON response from the action prompt.
    """
    return parse_action_result(raw_json)


@mcp.tool()
def tool_generate_research_prompt(
    company_name: str,
    website: str = "",
    notes: str = "",
    web_research_context: str = "",
) -> dict[str, Any]:
    """Generate a research brief prompt for a lead.

    Returns a prompt for you to reason over and produce a prose research brief.
    Output is prose (NOT JSON) with sections: COMPANY SUMMARY, INDUSTRY SNAPSHOT,
    BUYER PERSONA, RISK SIGNALS.

    Args:
        company_name: Company to research.
        website: Company website URL.
        notes: CRM notes.
        web_research_context: Optional web research content you've already gathered
            (e.g. from your own web searches). If provided, it's included in the prompt.
    """
    return generate_research_prompt(
        company_name=company_name,
        website=website,
        notes=notes,
        web_research_context=web_research_context,
    )


@mcp.tool()
def tool_get_config() -> dict[str, Any]:
    """Get CRM agent configuration.

    Returns ICP criteria, priority thresholds, and Notion property name mappings.
    Use this to know which Notion properties to read from and write to.
    """
    return get_config()


@mcp.tool()
def tool_run_full_analysis(
    company_name: str,
    website: str = "",
    notes: str = "",
    status: str = "",
    last_contacted: str | None = None,
    last_edited_time: str | None = None,
    web_research_context: str = "",
) -> dict[str, Any]:
    """Run all deterministic analysis steps and generate prompts for LLM steps.

    This is a convenience tool that runs signal detection immediately and
    prepares the ICP and research prompts in one call. You'll still need to:
    1. Reason over the ICP prompt and call parse_icp_result
    2. Reason over the research prompt to produce a brief
    3. Call determine_priority with the ICP results
    4. Call recommend_action with priority results

    Args:
        company_name: Company name.
        website: Website URL.
        notes: CRM notes.
        status: Lead status.
        last_contacted: ISO date of last contact.
        last_edited_time: ISO timestamp of last Notion edit.
        web_research_context: Optional pre-fetched web research.
    """
    signals = detect_signals(
        company_name=company_name,
        notes=notes,
        status=status,
        research_brief="",
        last_contacted=last_contacted,
        last_edited_time=last_edited_time,
    )

    icp_prompt_data = score_icp_fit(
        company_name=company_name,
        website=website,
        notes=notes,
    )

    research_prompt_data = generate_research_prompt(
        company_name=company_name,
        website=website,
        notes=notes,
        web_research_context=web_research_context,
    )

    return {
        "signals": signals,
        "icp_prompt": icp_prompt_data,
        "research_prompt": research_prompt_data,
        "next_steps": [
            "1. Reason over icp_prompt.prompt with icp_prompt.system_prompt to produce ICP JSON",
            "2. Call parse_icp_result with your ICP JSON",
            "3. Reason over research_prompt.prompt with research_prompt.system_prompt to produce a research brief",
            "4. Call determine_priority with icp_score from step 2 and signal results",
            "5. If determine_priority returns needs_llm=True, reason over the prompt and call parse_priority_result",
            "6. Call recommend_action with the priority result",
            "7. If recommend_action returns needs_llm=True, reason over the prompt and call parse_action_result",
            "8. Use get_config to see Notion property names, then write results back with notion-update-page",
        ],
    }


if __name__ == "__main__":
    mcp.run()
