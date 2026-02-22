"""
Market Research Agent.

Generates research briefs with data-quality awareness.
Assesses input completeness and injects a quality note so
the LLM can flag speculation appropriately.
Optionally enriches prompts with real web research data.
"""

import logging
from typing import Any, Dict, Optional

from agents.base_agent import BaseAgent
from services.web_research_service import WebResearchService

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """Generate market research briefs with confidence assessment."""

    prompt_file = "research_prompt.txt"

    def __init__(self, claude_service, web_research_service: Optional[WebResearchService] = None):
        super().__init__(claude_service)
        self.web_research = web_research_service

    def run(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a research brief for a lead.

        Returns:
            research_brief (str), research_confidence (str: high/medium/low)
        """
        # Gather web research if available
        web_research_text = "No web research data was available for this lead."
        has_web_content = False
        web_result = None
        if self.web_research:
            try:
                web_result = self.web_research.research_lead(lead)
                if web_result.has_content:
                    web_research_text = web_result.to_prompt_section()
                    has_web_content = True
                    logger.info(
                        "Web research for %s: %d pages fetched",
                        lead.get("company_name"),
                        web_result.pages_fetched,
                    )
                if web_result.errors:
                    for err in web_result.errors:
                        logger.warning("Web research warning: %s", err)
            except Exception as e:
                logger.warning("Web research failed for %s: %s", lead.get("company_name"), e)

        confidence = self._assess_data_quality(lead, web_result)
        quality_note = self._quality_note(lead, confidence, web_result)
        citations = self._build_citations(lead, web_result)

        prompt = self.prompt_template.format(
            company_name=lead.get("company_name", "N/A"),
            website=lead.get("website") or "Not provided",
            notes=lead.get("notes") or "No notes available",
            web_research=web_research_text,
            data_quality_note=quality_note,
        )

        response = self._call_llm(
            prompt=prompt,
            system_prompt="You are an expert market research analyst. Provide actionable insights.",
            structured=False,
        )

        logger.info(
            "Research for %s: confidence=%s, web_content=%s, sources=%d",
            lead.get("company_name"),
            confidence,
            has_web_content,
            len(citations),
        )

        brief = response
        if citations:
            brief = f"{response}\n\n## SOURCES\n" + "\n".join(f"- {c}" for c in citations)

        return {
            "research_brief": brief,
            "research_confidence": confidence,
            "research_citations": "\n".join(f"- {c}" for c in citations),
            "research_source_count": len(citations),
        }

    @staticmethod
    def _assess_data_quality(lead: Dict[str, Any], web_result=None) -> str:
        """Rate data quality using weighted evidence signals."""
        has_website = bool(lead.get("website"))
        has_notes = bool(lead.get("notes", "").strip())
        has_company = bool(lead.get("company_name", "").strip())
        notes_len = len(lead.get("notes", "").strip())
        has_web_content = bool(web_result and web_result.website_content)
        has_search_results = bool(web_result and web_result.search_results)
        pages_fetched = int(web_result.pages_fetched) if web_result else 0

        score = 0
        if has_company:
            score += 1
        if has_website:
            score += 1
        if has_notes:
            score += 1
        if notes_len >= 120:
            score += 1
        if has_web_content:
            score += 2
        if pages_fetched >= 2:
            score += 1
        if has_search_results:
            score += 1

        if score >= 6:
            return "high"
        if score >= 3:
            return "medium"
        return "low"

    @staticmethod
    def _quality_note(lead: Dict[str, Any], confidence: str, web_result=None) -> str:
        """Build a note describing what data is available/missing."""
        has_web_content = bool(web_result and web_result.website_content)
        missing = []
        if not lead.get("website"):
            missing.append("no website provided")
        if not lead.get("notes", "").strip():
            missing.append("no notes/context provided")
        if not lead.get("company_name", "").strip():
            missing.append("company name is missing")

        sources = []
        if lead.get("website"):
            sources.append("website URL")
        if lead.get("notes", "").strip():
            sources.append("CRM notes")
        if lead.get("company_name", "").strip():
            sources.append("company name")
        if has_web_content:
            sources.append("live website content")

        if not missing:
            note = f"Data quality: {confidence.upper()} — {', '.join(sources)} are all available."
            if has_web_content:
                note += " Live website content has been scraped and included above."
            return note

        note = (
            f"Data quality: {confidence.upper()} — "
            f"Available: {', '.join(sources) if sources else 'minimal data'}. "
            f"Missing: {', '.join(missing)}. "
            "Where data is unavailable, clearly state that you are speculating "
            "and prefix those sections with 'Based on available information...'."
        )
        return note

    @staticmethod
    def _build_citations(lead: Dict[str, Any], web_result=None) -> list[str]:
        """Build a deduplicated citation list for transparency."""
        citations = []
        website = (lead.get("website") or "").strip()
        if website:
            citations.append(f"Website: {website}")
        if lead.get("notes", "").strip():
            citations.append("CRM Notes")
        if web_result:
            citations.extend(web_result.source_urls)
        return list(dict.fromkeys(citations))
