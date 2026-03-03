"""Action recommendation tools — deterministic rules + prompt for edge cases."""

from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent


_VALID_ACTIONS = {"outreach_now", "reengage", "nurture", "enrich_data", "hold"}
_VALID_CONFIDENCE = {"high", "medium", "low"}


def _load_prompt() -> str:
    path = Path(__file__).parent.parent / "prompts" / "action_prompt.txt"
    return path.read_text()


def recommend_action(
    priority_tier: str = "review",
    stale_flag: bool = False,
    icp_score: int | None = None,
    research_confidence: str = "medium",
    company_name: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Recommend next action. Returns result directly for clear cases,
    or a prompt for Claude Code to reason over for ambiguous cases.
    """
    priority = priority_tier.lower()

    if priority == "review":
        return {
            "next_action": "enrich_data",
            "action_reasoning": "Insufficient signal to act confidently; gather more context first.",
            "action_confidence": "high",
            "needs_llm": False,
        }

    if priority == "low":
        return {
            "next_action": "nurture",
            "action_reasoning": "Low-priority lead; keep warm with low-touch nurture instead of immediate sales effort.",
            "action_confidence": "high",
            "needs_llm": False,
        }

    if priority == "high" and not stale_flag:
        if research_confidence == "low":
            return {
                "next_action": "enrich_data",
                "action_reasoning": "High-priority lead but research confidence is low; enrich data before outreach to avoid missteps.",
                "action_confidence": "medium",
                "needs_llm": False,
            }
        return {
            "next_action": "outreach_now",
            "action_reasoning": "High-priority lead with recent activity; immediate outreach has the best chance to convert.",
            "action_confidence": "high",
            "needs_llm": False,
        }

    if priority == "high" and stale_flag:
        return {
            "next_action": "reengage",
            "action_reasoning": "Strong fit but stale activity; run a re-engagement sequence before closing as inactive.",
            "action_confidence": "high",
            "needs_llm": False,
        }

    # Medium/ambiguous → prompt for LLM
    template = _load_prompt()
    prompt = template.format(
        company_name=company_name or "N/A",
        icp_score=icp_score if icp_score is not None else "unknown",
        priority_tier=priority,
        stale_flag=str(stale_flag).lower(),
        research_confidence=research_confidence,
        notes=notes or "No notes available",
    )

    return {
        "needs_llm": True,
        "prompt": prompt,
        "system_prompt": "You are a sales execution strategist. Always respond with valid JSON.",
        "expected_format": {
            "next_action": "outreach_now|reengage|nurture|enrich_data|hold",
            "action_reasoning": "1-2 sentence rationale",
            "action_confidence": "high|medium|low",
        },
    }


def parse_action_result(raw_json: str) -> dict[str, Any]:
    """Validate Claude's action recommendation response."""
    parsed = BaseAgent._parse_json_response(raw_json)

    if not parsed:
        return {
            "next_action": "enrich_data",
            "action_reasoning": "Could not parse model output. Defaulting to data enrichment.",
            "action_confidence": "low",
            "valid": False,
        }

    action = str(parsed.get("next_action", "enrich_data")).lower()
    if action not in _VALID_ACTIONS:
        action = "enrich_data"

    confidence = str(parsed.get("action_confidence", "medium")).lower()
    if confidence not in _VALID_CONFIDENCE:
        confidence = "medium"

    reasoning = str(parsed.get("action_reasoning", ""))[:1000]

    return {
        "next_action": action,
        "action_reasoning": reasoning,
        "action_confidence": confidence,
        "valid": True,
    }
