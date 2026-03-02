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
        raw_dims = data.get("dimension_scores")
        has_dimensions = isinstance(raw_dims, dict) and any(
            raw_dims.get(d) is not None for d in DIMENSIONS
        )
        for dim in DIMENSIONS:
            score = (raw_dims or {}).get(dim, 0)
            score = int(self._clamp(score, 0, 20))
            dim_scores[dim] = score
            total += score

        llm_total = data.get("icp_score")
        if has_dimensions:
            # Prefer calculated sum — it's verifiable
            if llm_total is not None and int(self._clamp(llm_total, 0, 100)) != total:
                logger.warning(
                    "ICP score mismatch: LLM said %s but dimensions sum to %d — using sum",
                    llm_total,
                    total,
                )
            icp_score = int(self._clamp(total, 0, 100))
        else:
            # No dimensions provided — use LLM total if available
            if llm_total is not None:
                icp_score = int(self._clamp(llm_total, 0, 100))
                logger.warning(
                    "ICP response missing dimension_scores — using LLM total %d unverified",
                    icp_score,
                )
            else:
                icp_score = -1
                logger.warning("ICP response missing both dimension_scores and icp_score")

        confidence = int(self._clamp(data.get("confidence_score", 0), 0, 100))
        reasoning = str(data.get("icp_reasoning", ""))
        data_gaps = data.get("data_gaps", "")

        if len(reasoning) > 1000:
            logger.debug("ICP reasoning truncated from %d to 1000 chars", len(reasoning))
        data_gaps_str = str(data_gaps)[:500] if data_gaps else ""
        if data_gaps and len(str(data_gaps)) > 500:
            logger.debug("ICP data_gaps truncated from %d to 500 chars", len(str(data_gaps)))

        return {
            "icp_score": icp_score,
            "confidence_score": confidence,
            "icp_reasoning": reasoning[:1000],
            "data_gaps": data_gaps_str,
        }
