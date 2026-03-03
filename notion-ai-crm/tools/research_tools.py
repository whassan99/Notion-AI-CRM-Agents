"""Research prompt generation tool."""

from pathlib import Path
from typing import Any

from agents.research_agent import ResearchAgent


def _load_prompt() -> str:
    path = Path(__file__).parent.parent / "prompts" / "research_prompt.txt"
    return path.read_text()


def generate_research_prompt(
    company_name: str,
    website: str = "",
    notes: str = "",
    web_research_context: str = "",
) -> dict[str, Any]:
    """Build a research prompt for Claude Code to reason over.

    Args:
        company_name: The company to research.
        website: Company website URL.
        notes: CRM notes about the company.
        web_research_context: Optional pre-fetched web research content
            (e.g. from Claude Code's own web search). If empty, the prompt
            will note that no web research was available.
    """
    lead = {
        "company_name": company_name,
        "website": website,
        "notes": notes,
    }

    # Use ResearchAgent's static methods for data quality assessment
    confidence = ResearchAgent._assess_data_quality(lead)
    quality_note = ResearchAgent._quality_note(lead, confidence)
    citations = ResearchAgent._build_citations(lead)

    web_text = web_research_context or "No web research data was available for this lead."

    template = _load_prompt()
    prompt = template.format(
        company_name=company_name,
        website=website or "Not provided",
        notes=notes or "No notes available",
        web_research=web_text,
        data_quality_note=quality_note,
    )

    return {
        "prompt": prompt,
        "system_prompt": "You are an expert market research analyst. Provide actionable insights.",
        "data_quality": confidence,
        "citations": citations,
        "output_format": "prose",
        "guidelines": (
            "Respond with a structured research brief (300-400 words) containing sections: "
            "COMPANY SUMMARY, INDUSTRY SNAPSHOT, BUYER PERSONA, RISK SIGNALS. "
            "This is prose output, NOT JSON."
        ),
    }
