"""
Pipeline orchestrator for the Notion AI CRM Copilot.

Fetches leads from Notion, runs AI agents (ICP, Research, Priority),
and writes results back. Supports dry-run mode and result tracking.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from config import Config
from services.notion_service import NotionService
from services.claude_service import ClaudeService
from services.web_research_service import WebResearchService
from agents import ICPAgent, ResearchAgent, PriorityAgent

logger = logging.getLogger(__name__)

# Sample leads for dry-run mode — one strong, one weak
SAMPLE_LEADS = [
    {
        "page_id": "dry-run-001",
        "company_name": "Acme SaaS Corp",
        "website": "https://acmesaas.com",
        "notes": "Series B, 200 employees, expanding sales team. Expressed interest in automation tools. VP Sales responded to outreach.",
        "last_contacted": "2025-02-01",
        "status": "Qualified",
    },
    {
        "page_id": "dry-run-002",
        "company_name": "TinyStart LLC",
        "website": "",
        "notes": "",
        "last_contacted": None,
        "status": "New",
    },
]


@dataclass
class PipelineResult:
    """Tracks pipeline execution results."""

    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.succeeded + self.failed + self.skipped

    def summary(self) -> str:
        parts = [f"{self.succeeded}/{self.total} leads processed"]
        if self.failed:
            parts.append(f"{self.failed} failed")
        if self.skipped:
            parts.append(f"{self.skipped} skipped")
        return ", ".join(parts)


def run_pipeline(
    limit: Optional[int] = None,
    dry_run: bool = False,
    no_web: bool = False,
) -> PipelineResult:
    """
    Run the full AI agent pipeline on leads.

    Args:
        limit: Maximum number of leads to process.
        dry_run: If True, use sample data and skip Notion writes.
        no_web: If True, disable web research entirely.

    Returns:
        PipelineResult with counts and error details.
    """
    result = PipelineResult()

    # Initialize services
    logger.info("Initializing services...")
    claude = ClaudeService()

    if dry_run:
        logger.info("DRY RUN — using sample leads, skipping Notion writes")
        leads = SAMPLE_LEADS
        notion = None
    else:
        notion = NotionService()
        # Validate database access before processing
        notion.validate_database()

        logger.info("Fetching leads from Notion...")
        leads = notion.fetch_leads()

        if not leads:
            logger.warning("No leads found in Notion database.")
            return result

        logger.info("Found %d leads", len(leads))

    if limit:
        leads = leads[:limit]
        logger.info("Processing first %d leads", len(leads))

    # Initialize web research service
    web_research = None
    if Config.WEB_RESEARCH_ENABLED and not no_web:
        web_research = WebResearchService()
        logger.info("Web research enabled")
    else:
        logger.info("Web research disabled")

    # Initialize agents
    icp_agent = ICPAgent(claude)
    research_agent = ResearchAgent(claude, web_research_service=web_research)
    priority_agent = PriorityAgent(claude)

    # Process each lead
    for i, lead in enumerate(leads, 1):
        company = lead.get("company_name", "Unknown")
        logger.info("[%d/%d] Processing: %s", i, len(leads), company)

        try:
            # Run ICP Agent
            icp_results = icp_agent.run(lead)

            # Run Research Agent
            research_results = research_agent.run(lead)

            # Enrich lead with ICP score for priority agent
            lead_enriched = {**lead, **icp_results}

            # Run Priority Agent
            priority_results = priority_agent.run(lead_enriched)

            # Combine all results
            all_results = {**icp_results, **research_results, **priority_results}

            # Write back to Notion (skip in dry-run)
            if dry_run:
                logger.info("DRY RUN — would write to Notion: %s", {
                    k: (v[:80] + "...") if isinstance(v, str) and len(v) > 80 else v
                    for k, v in all_results.items()
                })
            else:
                success = notion.update_lead(lead["page_id"], all_results)
                if not success:
                    logger.warning("Failed to write results for %s", company)

            result.succeeded += 1
            logger.info("Done: %s", company)

        except Exception as e:
            result.failed += 1
            error_msg = f"{company}: {e}"
            result.errors.append(error_msg)
            logger.error("Error processing %s: %s", company, e)
            continue

    # Summary
    logger.info("Pipeline complete — %s", result.summary())
    if result.errors:
        logger.info("Errors:")
        for err in result.errors:
            logger.info("  - %s", err)

    return result
