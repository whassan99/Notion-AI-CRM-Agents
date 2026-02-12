"""
Prioritization Agent.

Hybrid approach: deterministic rules for clear-cut cases,
LLM with JSON output for edge cases. All thresholds from Config.
Adds a "review" tier when ICP score is missing.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from config import Config
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class PriorityAgent(BaseAgent):
    """Prioritize leads and flag stale ones."""

    prompt_file = "priority_prompt.txt"

    def run(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine priority tier, reasoning, and stale flag.

        Returns:
            priority_tier (str), priority_reasoning (str),
            stale_flag (bool), days_since_contact (int)
        """
        days = self._calculate_days_since_contact(lead.get("last_contacted"))
        stale = days >= Config.STALE_DAYS_THRESHOLD
        icp_score = lead.get("icp_score")

        # If ICP score is missing or invalid, we can't prioritize reliably
        if icp_score is None or icp_score < 0:
            logger.info("Priority for %s: REVIEW (missing ICP score)", lead.get("company_name"))
            return {
                "priority_tier": "review",
                "priority_reasoning": "ICP score is unavailable — cannot prioritize without it.",
                "stale_flag": stale,
                "days_since_contact": days,
            }

        tier, reasoning = self._determine_priority(lead, icp_score, days)

        logger.info(
            "Priority for %s: %s (ICP=%s, days=%d%s)",
            lead.get("company_name"),
            tier.upper(),
            icp_score,
            days,
            ", STALE" if stale else "",
        )

        return {
            "priority_tier": tier,
            "priority_reasoning": reasoning,
            "stale_flag": stale,
            "days_since_contact": days,
        }

    def _determine_priority(
        self,
        lead: Dict[str, Any],
        icp_score: int,
        days_since_contact: int,
    ) -> tuple:
        """Return (tier, reasoning). Uses rules first, LLM for edge cases."""
        # HIGH: strong ICP + recent contact
        if icp_score >= Config.HIGH_ICP_MIN and days_since_contact <= Config.HIGH_RECENCY_MAX:
            return (
                "high",
                f"Strong ICP fit ({icp_score}) with recent contact ({days_since_contact}d ago).",
            )

        # LOW: weak ICP or very stale
        if icp_score <= Config.LOW_ICP_MAX:
            return (
                "low",
                f"Low ICP fit ({icp_score}) — below threshold of {Config.LOW_ICP_MAX}.",
            )
        if days_since_contact >= Config.LOW_STALE_DAYS:
            return (
                "low",
                f"Lead is stale ({days_since_contact}d since contact, threshold: {Config.LOW_STALE_DAYS}d).",
            )

        # Edge case — use LLM
        return self._llm_priority(lead, icp_score, days_since_contact)

    def _llm_priority(
        self,
        lead: Dict[str, Any],
        icp_score: int,
        days_since_contact: int,
    ) -> tuple:
        """Use LLM for ambiguous cases; parse JSON response."""
        prompt = self.prompt_template.format(
            company_name=lead.get("company_name", "N/A"),
            icp_score=icp_score,
            status=lead.get("status", "N/A"),
            days_since_contact=days_since_contact,
        )

        response = self._call_llm(
            prompt=prompt,
            system_prompt="You are a sales operations expert. Always respond with valid JSON.",
            structured=True,
        )

        data = self._parse_json_response(response)
        if data:
            tier = str(data.get("priority_tier", "medium")).lower()
            if tier not in ("high", "medium", "low"):
                tier = "medium"
            reasoning = data.get("priority_reasoning", "Determined by AI analysis.")
            return tier, str(reasoning)

        # Fallback if JSON parse fails
        logger.warning("Could not parse priority JSON — defaulting to medium")
        return "medium", "Could not parse LLM response; defaulting to medium."

    @staticmethod
    def _calculate_days_since_contact(last_contacted: str) -> int:
        """Days since last contact. Returns 999 if unknown."""
        if not last_contacted:
            return 999
        try:
            last_date = datetime.fromisoformat(last_contacted.replace("Z", "+00:00"))
            now = datetime.now(last_date.tzinfo)
            return (now - last_date).days
        except (ValueError, AttributeError):
            return 999
