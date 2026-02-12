"""
ICP (Ideal Customer Profile) Scoring Agent.

Uses a 5-dimension rubric (each 0-20 points) for transparent,
reproducible scoring. Returns structured JSON with dimension
breakdown, confidence based on data availability, and data gaps.
"""

import logging
from typing import Any, Dict

from config import Config
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

DIMENSIONS = [
    "company_size_stage",
    "market_industry_fit",
    "budget_buying_signals",
    "engagement_accessibility",
    "strategic_alignment",
]


class ICPAgent(BaseAgent):
    """Score leads against the Ideal Customer Profile using a rubric."""

    prompt_file = "icp_prompt.txt"

    def run(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a lead and return ICP fit scores.

        Returns:
            icp_score (0-100), dimension_scores, confidence_score (0-100),
            icp_reasoning, data_gaps
        """
        prompt = self.prompt_template.format(
            company_name=lead.get("company_name", "N/A"),
            website=lead.get("website") or "Not provided",
            notes=lead.get("notes") or "No notes available",
            icp_criteria=Config.ICP_CRITERIA,
        )

        response = self._call_llm(
            prompt=prompt,
            system_prompt=(
                "You are an expert sales analyst specializing in ICP fit scoring. "
                "Always respond with valid JSON."
            ),
            structured=True,
        )

        result = self._parse(response)
        logger.info(
            "ICP for %s: score=%d, confidence=%d",
            lead.get("company_name"),
            result["icp_score"],
            result["confidence_score"],
        )
        return result

    def _parse(self, response: str) -> Dict[str, Any]:
        """Parse the JSON response; return failure result if parsing fails."""
        data = self._parse_json_response(response)

        if data is None:
            logger.warning("Failed to parse ICP response as JSON")
            return {
                "icp_score": -1,
                "confidence_score": 0,
                "icp_reasoning": "Could not score — LLM response was not valid JSON.",
                "data_gaps": "Parse failure",
            }

        # Extract and clamp dimension scores
        dim_scores = {}
        total = 0
        for dim in DIMENSIONS:
            score = data.get("dimension_scores", {}).get(dim, 0)
            score = int(self._clamp(score, 0, 20))
            dim_scores[dim] = score
            total += score

        icp_score = int(self._clamp(data.get("icp_score", total), 0, 100))
        confidence = int(self._clamp(data.get("confidence_score", 0), 0, 100))
        reasoning = data.get("icp_reasoning", "")
        data_gaps = data.get("data_gaps", "")

        return {
            "icp_score": icp_score,
            "confidence_score": confidence,
            "icp_reasoning": str(reasoning)[:1000],
            "data_gaps": str(data_gaps)[:500] if data_gaps else "",
        }
