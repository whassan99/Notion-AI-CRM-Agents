"""Priority tools — deterministic rules + prompt for edge cases."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import Config
from agents.base_agent import BaseAgent


def _load_prompt() -> str:
    path = Path(__file__).parent.parent / "prompts" / "priority_prompt.txt"
    return path.read_text()


def _calculate_days_since_contact(last_contacted: str | None) -> int:
    if not last_contacted:
        return 999
    try:
        last_date = datetime.fromisoformat(last_contacted.replace("Z", "+00:00"))
        if last_date.tzinfo is None:
            last_date = last_date.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - last_date).days
    except (ValueError, AttributeError):
        return 999


def _apply_signal_boost(
    tier: str, reasoning: str, icp_score: int,
    signal_type: str, signal_strength: str,
) -> tuple[str, str]:
    if tier not in ("low", "medium"):
        return tier, reasoning
    if signal_strength != "high":
        return tier, reasoning
    if icp_score <= Config.LOW_ICP_MAX:
        return tier, reasoning

    boosted = "medium" if tier == "low" else "high"
    label = signal_type if signal_type and signal_type != "none" else "trigger"
    return boosted, f"{reasoning} Boosted from {tier} to {boosted} due to strong {label} signal."


def determine_priority(
    icp_score: int | None = None,
    last_contacted: str | None = None,
    status: str = "",
    company_name: str = "",
    signal_type: str = "none",
    signal_strength: str = "none",
) -> dict[str, Any]:
    """Determine lead priority. Returns result directly for clear cases,
    or a prompt for Claude Code to reason over for edge cases.

    Fields always returned: stale_flag, days_since_contact.
    For deterministic results: priority_tier, priority_reasoning, needs_llm=False.
    For edge cases: prompt, system_prompt, expected_format, needs_llm=True.
    """
    days = _calculate_days_since_contact(last_contacted)
    stale = days >= Config.STALE_DAYS_THRESHOLD

    base = {"stale_flag": stale, "days_since_contact": days}

    # Missing ICP → review
    if icp_score is None or icp_score < 0:
        return {
            **base,
            "priority_tier": "review",
            "priority_reasoning": "ICP score is unavailable — cannot prioritize without it.",
            "needs_llm": False,
        }

    # HIGH: strong ICP + recent contact
    if icp_score >= Config.HIGH_ICP_MIN and days <= Config.HIGH_RECENCY_MAX:
        tier, reasoning = "high", f"Strong ICP fit ({icp_score}) with recent contact ({days}d ago)."
        tier, reasoning = _apply_signal_boost(tier, reasoning, icp_score, signal_type, signal_strength)
        return {**base, "priority_tier": tier, "priority_reasoning": reasoning, "needs_llm": False}

    # LOW: weak ICP
    if icp_score <= Config.LOW_ICP_MAX:
        tier, reasoning = "low", f"Low ICP fit ({icp_score}) — below threshold of {Config.LOW_ICP_MAX}."
        tier, reasoning = _apply_signal_boost(tier, reasoning, icp_score, signal_type, signal_strength)
        return {**base, "priority_tier": tier, "priority_reasoning": reasoning, "needs_llm": False}

    # LOW: stale
    if days >= Config.LOW_STALE_DAYS:
        tier, reasoning = "low", f"Lead is stale ({days}d since contact, threshold: {Config.LOW_STALE_DAYS}d)."
        tier, reasoning = _apply_signal_boost(tier, reasoning, icp_score, signal_type, signal_strength)
        return {**base, "priority_tier": tier, "priority_reasoning": reasoning, "needs_llm": False}

    # Edge case → prompt for LLM
    template = _load_prompt()
    prompt = template.format(
        company_name=company_name or "N/A",
        icp_score=icp_score,
        status=status or "N/A",
        days_since_contact=days,
    )

    return {
        **base,
        "needs_llm": True,
        "prompt": prompt,
        "system_prompt": "You are a sales operations expert. Always respond with valid JSON.",
        "expected_format": {
            "priority_tier": "high | medium | low",
            "priority_reasoning": "1-2 sentences citing specific factors",
        },
        # Pass through for post-parse signal boost
        "_icp_score": icp_score,
        "_signal_type": signal_type,
        "_signal_strength": signal_strength,
    }


def parse_priority_result(
    raw_json: str,
    stale_flag: bool = False,
    days_since_contact: int = 999,
    icp_score: int = 50,
    signal_type: str = "none",
    signal_strength: str = "none",
) -> dict[str, Any]:
    """Validate Claude's priority response and apply signal boost."""
    parsed = BaseAgent._parse_json_response(raw_json)

    if not parsed:
        tier, reasoning = "medium", "Could not parse LLM response; defaulting to medium."
    else:
        tier = str(parsed.get("priority_tier", "medium")).lower()
        if tier not in ("high", "medium", "low"):
            tier = "medium"
        reasoning = str(parsed.get("priority_reasoning", "Determined by AI analysis."))

    tier, reasoning = _apply_signal_boost(tier, reasoning, icp_score, signal_type, signal_strength)

    return {
        "priority_tier": tier,
        "priority_reasoning": reasoning,
        "stale_flag": stale_flag,
        "days_since_contact": days_since_contact,
    }
