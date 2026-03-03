"""ICP scoring tools — prompt generation and result validation."""

import json
from pathlib import Path
from typing import Any

from config import Config
from agents.icp_agent import DIMENSIONS
from agents.base_agent import BaseAgent


def _load_prompt() -> str:
    path = Path(__file__).parent.parent / "prompts" / "icp_prompt.txt"
    return path.read_text()


def score_icp_fit(
    company_name: str,
    website: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Build the ICP scoring prompt for Claude Code to reason over.

    Returns a dict with:
      - prompt: The full ICP scoring prompt with rubric
      - system_prompt: The system instruction for Claude
      - expected_format: Description of the expected JSON output
    """
    template = _load_prompt()
    prompt = template.format(
        company_name=company_name,
        website=website or "Not provided",
        notes=notes or "No notes available",
        icp_criteria=Config.ICP_CRITERIA,
    )

    return {
        "prompt": prompt,
        "system_prompt": (
            "You are an expert sales analyst specializing in ICP fit scoring. "
            "Always respond with valid JSON."
        ),
        "expected_format": {
            "icp_score": "0-100 (sum of 5 dimensions)",
            "dimension_scores": {
                "company_size_stage": "0-20",
                "market_industry_fit": "0-20",
                "budget_buying_signals": "0-20",
                "engagement_accessibility": "0-20",
                "strategic_alignment": "0-20",
            },
            "confidence_score": "0-100 based on data availability",
            "icp_reasoning": "2-4 sentences with evidence",
            "data_gaps": "missing info or empty string",
        },
    }


def parse_icp_result(raw_json: str) -> dict[str, Any]:
    """Validate and clean Claude's ICP scoring response.

    Takes the raw JSON string from Claude's response and returns
    a validated, clamped result matching the canonical schema.
    """
    parsed = BaseAgent._parse_json_response(raw_json)

    if parsed is None:
        return {
            "icp_score": -1,
            "confidence_score": 0,
            "icp_reasoning": "Could not score — response was not valid JSON.",
            "data_gaps": "Parse failure",
            "valid": False,
            "error": "JSON parse failed",
        }

    clamp = BaseAgent._clamp

    # Extract dimension scores
    dim_scores = {}
    total = 0
    raw_dims = parsed.get("dimension_scores")
    has_dimensions = isinstance(raw_dims, dict) and any(
        raw_dims.get(d) is not None for d in DIMENSIONS
    )
    for dim in DIMENSIONS:
        score = (raw_dims or {}).get(dim, 0)
        try:
            score = int(clamp(float(score), 0, 20))
        except (TypeError, ValueError):
            score = 0
        dim_scores[dim] = score
        total += score

    llm_total = parsed.get("icp_score")
    warnings = []
    if has_dimensions:
        if llm_total is not None:
            try:
                llm_val = int(clamp(float(llm_total), 0, 100))
            except (TypeError, ValueError):
                llm_val = None
            if llm_val is not None and llm_val != total:
                warnings.append(
                    f"LLM reported icp_score={llm_total} but dimensions sum to {total} — using sum"
                )
        icp_score = int(clamp(total, 0, 100))
    else:
        if llm_total is not None:
            try:
                icp_score = int(clamp(float(llm_total), 0, 100))
            except (TypeError, ValueError):
                icp_score = -1
            warnings.append("Missing dimension_scores — using LLM total unverified")
        else:
            icp_score = -1
            warnings.append("Missing both dimension_scores and icp_score")

    try:
        confidence = int(clamp(float(parsed.get("confidence_score", 0)), 0, 100))
    except (TypeError, ValueError):
        confidence = 0

    reasoning = str(parsed.get("icp_reasoning", ""))[:1000]
    data_gaps = str(parsed.get("data_gaps", ""))[:500]

    result = {
        "icp_score": icp_score,
        "dimension_scores": dim_scores,
        "confidence_score": confidence,
        "icp_reasoning": reasoning,
        "data_gaps": data_gaps,
        "valid": icp_score >= 0,
    }
    if warnings:
        result["warnings"] = warnings
    return result
