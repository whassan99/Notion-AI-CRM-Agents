"""
Market Research Agent.

Generates research briefs with data-quality awareness.
Assesses input completeness and injects a quality note so
the LLM can flag speculation appropriately.
"""

import logging
from typing import Any, Dict

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """Generate market research briefs with confidence assessment."""

    prompt_file = "research_prompt.txt"

    def run(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a research brief for a lead.

        Returns:
            research_brief (str), research_confidence (str: high/medium/low)
        """
        confidence = self._assess_data_quality(lead)
        quality_note = self._quality_note(lead, confidence)

        prompt = self.prompt_template.format(
            company_name=lead.get("company_name", "N/A"),
            website=lead.get("website") or "Not provided",
            notes=lead.get("notes") or "No notes available",
            data_quality_note=quality_note,
        )

        response = self._call_llm(
            prompt=prompt,
            system_prompt="You are an expert market research analyst. Provide actionable insights.",
            structured=False,
        )

        logger.info(
            "Research for %s: confidence=%s",
            lead.get("company_name"),
            confidence,
        )

        return {
            "research_brief": response,
            "research_confidence": confidence,
        }

    @staticmethod
    def _assess_data_quality(lead: Dict[str, Any]) -> str:
        """Rate data completeness: high / medium / low."""
        has_website = bool(lead.get("website"))
        has_notes = bool(lead.get("notes", "").strip())
        has_company = bool(lead.get("company_name", "").strip())

        filled = sum([has_website, has_notes, has_company])
        if filled >= 3:
            return "high"
        elif filled >= 2:
            return "medium"
        return "low"

    @staticmethod
    def _quality_note(lead: Dict[str, Any], confidence: str) -> str:
        """Build a note describing what data is available/missing."""
        missing = []
        if not lead.get("website"):
            missing.append("no website provided")
        if not lead.get("notes", "").strip():
            missing.append("no notes/context provided")
        if not lead.get("company_name", "").strip():
            missing.append("company name is missing")

        if not missing:
            return "Data quality: HIGH — website, notes, and company name are all available."

        return (
            f"Data quality: {confidence.upper()} — "
            f"Missing: {', '.join(missing)}. "
            "Where data is unavailable, clearly state that you are speculating "
            "and prefix those sections with 'Based on available information...'."
        )
