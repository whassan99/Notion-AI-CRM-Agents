"""
Action Agent.

Recommends the next best action for each lead based on ICP fit,
priority tier, staleness, and data quality. Uses deterministic
rules first, then LLM JSON output for ambiguous cases.
"""

import logging
from typing import Any, Dict, Tuple

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

_VALID_ACTIONS = {"outreach_now", "reengage", "nurture", "enrich_data", "hold"}
_VALID_CONFIDENCE = {"high", "medium", "low"}


class ActionAgent(BaseAgent):
    """Recommend a concrete next action for a lead."""

    prompt_file = "action_prompt.txt"

    def run(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine next action and rationale.

        Returns:
            next_action (str),
            action_reasoning (str),
            action_confidence (str: high/medium/low)
        """
        action, reasoning, confidence = self._determine_action(lead)
        logger.info(
            "Action for %s: %s (%s)",
            lead.get("company_name"),
            action,
            confidence,
        )
        return {
            "next_action": action,
            "action_reasoning": reasoning,
            "action_confidence": confidence,
        }

    def _determine_action(self, lead: Dict[str, Any]) -> Tuple[str, str, str]:
        """Rules first, LLM fallback for edge cases."""
        priority = str(lead.get("priority_tier", "review")).lower()
        stale = bool(lead.get("stale_flag", False))
        icp_score = lead.get("icp_score")
        research_confidence = str(lead.get("research_confidence", "medium")).lower()

        if priority == "review":
            return (
                "enrich_data",
                "Insufficient signal to act confidently; gather more context first.",
                "high",
            )
        if priority == "low":
            return (
                "nurture",
                "Low-priority lead; keep warm with low-touch nurture instead of immediate sales effort.",
                "high",
            )
        if priority == "high" and not stale:
            return (
                "outreach_now",
                "High-priority lead with recent activity; immediate outreach has the best chance to convert.",
                "high",
            )
        if priority == "high" and stale:
            return (
                "reengage",
                "Strong fit but stale activity; run a re-engagement sequence before closing as inactive.",
                "high",
            )

        # For medium/ambiguous cases, let the model choose an action.
        return self._llm_action(lead, icp_score, priority, stale, research_confidence)

    def _llm_action(
        self,
        lead: Dict[str, Any],
        icp_score: Any,
        priority: str,
        stale: bool,
        research_confidence: str,
    ) -> Tuple[str, str, str]:
        """Use LLM for edge cases and parse structured JSON safely."""
        prompt = self.prompt_template.format(
            company_name=lead.get("company_name", "N/A"),
            icp_score=icp_score if icp_score is not None else "unknown",
            priority_tier=priority,
            stale_flag=str(stale).lower(),
            research_confidence=research_confidence,
            notes=lead.get("notes") or "No notes available",
        )

        response = self._call_llm(
            prompt=prompt,
            system_prompt=(
                "You are a sales execution strategist. "
                "Always respond with valid JSON."
            ),
            structured=True,
        )

        data = self._parse_json_response(response)
        if not data:
            logger.warning("Could not parse action JSON — defaulting to enrich_data")
            return (
                "enrich_data",
                "Could not parse model output. Defaulting to data enrichment before taking action.",
                "low",
            )

        action = str(data.get("next_action", "enrich_data")).lower()
        if action not in _VALID_ACTIONS:
            action = "enrich_data"

        reasoning = str(data.get("action_reasoning", "Determine next step from available lead context."))
        confidence = str(data.get("action_confidence", "medium")).lower()
        if confidence not in _VALID_CONFIDENCE:
            confidence = "medium"

        return action, reasoning[:1000], confidence
