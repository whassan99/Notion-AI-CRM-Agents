"""
Pipeline orchestrator for the Notion AI CRM Copilot.

Fetches leads from Notion, runs AI agents (ICP, Research, Signals, Priority),
and writes results back. Supports dry-run mode and result tracking.
"""

import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from config import Config
from services.notion_service import NotionService
from services.claude_service import ClaudeService
from services.web_research_service import WebResearchService
from services.notification_service import LeadSummary, SlackNotifier
from agents import ICPAgent, ResearchAgent, SignalAgent, PriorityAgent, ActionAgent

logger = logging.getLogger(__name__)
_REQUIRED_RESULT_KEYS = ("icp_score", "priority_tier", "next_action")

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
    lead_summaries: List[LeadSummary] = field(default_factory=list)

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


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO datetime string. Returns None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _load_last_successful_run() -> Optional[datetime]:
    """Load last successful run timestamp from local state file."""
    path = Path(Config.PIPELINE_STATE_FILE).expanduser()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read pipeline state from %s: %s", path, exc)
        return None
    return _parse_iso_datetime(payload.get("last_successful_run"))


def _save_last_successful_run(timestamp: datetime) -> None:
    """Persist last successful run timestamp for incremental processing."""
    path = Path(Config.PIPELINE_STATE_FILE).expanduser()
    payload = {
        "last_successful_run": timestamp.astimezone(timezone.utc).isoformat(),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))
    except OSError as exc:
        logger.warning("Could not write pipeline state to %s: %s", path, exc)


def _is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def _has_required_outputs(existing_results: Optional[dict]) -> bool:
    """Whether the lead already has enough outputs to be considered scored."""
    if not isinstance(existing_results, dict):
        return False
    icp_score = existing_results.get("icp_score")
    if not isinstance(icp_score, (int, float)) or isinstance(icp_score, bool) or icp_score < 0:
        return False
    for key in _REQUIRED_RESULT_KEYS[1:]:
        if _is_blank(existing_results.get(key)):
            return False
    return True


def _should_process_lead(
    lead: dict,
    last_successful_run: Optional[datetime],
) -> tuple[bool, str]:
    """
    Decide if a lead should be processed.

    Rules:
    - Always process if required output fields are missing.
    - If already scored, process only when lead changed since last successful run.
    """
    existing = lead.get("existing_results")
    if not _has_required_outputs(existing):
        return True, "missing outputs"

    if last_successful_run is None:
        return False, "already scored"

    last_edited = _parse_iso_datetime(lead.get("last_edited_time"))
    if last_edited and last_edited > last_successful_run:
        return True, "changed since last run"

    return False, "unchanged since last run"


def run_pipeline(
    limit: Optional[int] = None,
    dry_run: bool = False,
    no_web: bool = False,
    notify_slack: bool = False,
    full_refresh: bool = False,
) -> PipelineResult:
    """
    Run the full AI agent pipeline on leads.

    Args:
        limit: Maximum number of leads to process.
        dry_run: If True, use sample data and skip Notion writes.
        no_web: If True, disable web research entirely.
        notify_slack: If True, post a summary to Slack after the run.
        full_refresh: If True, ignore incremental state and process all leads.

    Returns:
        PipelineResult with counts and error details.
    """
    result = PipelineResult()
    incremental_mode = (
        Config.INCREMENTAL_ENABLED
        and not dry_run
        and not full_refresh
    )
    last_successful_run = None

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

        if incremental_mode:
            last_successful_run = _load_last_successful_run()
            if last_successful_run:
                logger.info(
                    "Incremental mode enabled (last successful run: %s)",
                    last_successful_run.isoformat(),
                )
            else:
                logger.info(
                    "Incremental mode enabled (no previous run state found)."
                )

            selected = []
            for lead in leads:
                should_process, reason = _should_process_lead(lead, last_successful_run)
                if should_process:
                    selected.append(lead)
                else:
                    result.skipped += 1
                    logger.debug(
                        "Skipping %s (%s)",
                        lead.get("company_name", "Unknown"),
                        reason,
                    )
            leads = selected
            logger.info(
                "Incremental selection: %d leads to process, %d skipped",
                len(leads),
                result.skipped,
            )
        elif full_refresh:
            logger.info("Full refresh enabled — processing all leads.")
        else:
            logger.info("Incremental mode disabled — processing all leads.")

    if limit:
        eligible_count = len(leads)
        leads = leads[:limit]
        logger.info("Processing first %d leads (from %d eligible)", len(leads), eligible_count)

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
    signal_agent = SignalAgent(claude)
    priority_agent = PriorityAgent(claude)
    action_agent = ActionAgent(claude)

    # Process each lead
    for i, lead in enumerate(leads, 1):
        company = lead.get("company_name", "Unknown")
        logger.info("[%d/%d] Processing: %s", i, len(leads), company)

        try:
            # Run ICP Agent
            icp_results = icp_agent.run(lead)

            # Run Research Agent
            research_results = research_agent.run(lead)

            # Run Signal Agent
            lead_with_research = {**lead, **research_results}
            signal_results = signal_agent.run(lead_with_research)

            # Enrich lead with context for priority scoring
            lead_enriched = {**lead, **icp_results, **research_results, **signal_results}
            priority_results = priority_agent.run(lead_enriched)

            # Enrich lead for action recommendation
            lead_with_priority = {**lead_enriched, **priority_results, **research_results}

            # Run Action Agent
            action_results = action_agent.run(lead_with_priority)

            # Combine all results
            all_results = {
                **icp_results,
                **research_results,
                **signal_results,
                **priority_results,
                **action_results,
            }

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
            result.lead_summaries.append(LeadSummary(
                company=company,
                icp_score=icp_results.get("icp_score", -1),
                priority_tier=priority_results.get("priority_tier", "review"),
                stale=priority_results.get("stale_flag", False),
            ))
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

    if not dry_run and Config.INCREMENTAL_ENABLED:
        if result.failed == 0:
            _save_last_successful_run(datetime.now(timezone.utc))
        else:
            logger.warning(
                "Not updating incremental state because %d lead(s) failed.",
                result.failed,
            )

    # Slack notification
    if notify_slack or Config.SLACK_ENABLED:
        webhook_url = Config.SLACK_WEBHOOK_URL
        if webhook_url:
            notifier = SlackNotifier(webhook_url)
            notifier.send_pipeline_summary(
                succeeded=result.succeeded,
                failed=result.failed,
                skipped=result.skipped,
                leads=result.lead_summaries,
                errors=result.errors,
                dry_run=dry_run,
            )
        else:
            logger.warning("Slack notification requested but SLACK_WEBHOOK_URL is not set")

    return result
