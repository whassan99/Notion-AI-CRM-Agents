"""
Slack notification service for pipeline run summaries.

Sends a formatted summary to a Slack channel via an incoming webhook URL.
No extra dependencies — uses httpx which is already in requirements.txt.

Usage:
    Set SLACK_WEBHOOK_URL in .env (create one at api.slack.com/apps).
    Run with: python main.py --slack
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LeadSummary:
    """Result data for a single processed lead, used to build Slack summary."""

    company: str
    icp_score: int          # -1 if scoring failed
    priority_tier: str      # "high" | "medium" | "low" | "review"
    stale: bool


class SlackNotifier:
    """
    Sends pipeline run summaries to Slack via an incoming webhook.

    Formats a Block Kit message with:
    - Run statistics (processed / failed / skipped / stale)
    - Priority distribution (high / medium / low / review counts)
    - Top 3 leads by ICP score
    - Error list (if any)
    """

    PRIORITY_EMOJI = {
        "high": ":large_green_circle:",
        "medium": ":large_yellow_circle:",
        "low": ":red_circle:",
        "review": ":white_circle:",
    }

    def __init__(self, webhook_url: str):
        if not webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL is not set")
        self.webhook_url = webhook_url

    def send_pipeline_summary(
        self,
        succeeded: int,
        failed: int,
        skipped: int,
        leads: List[LeadSummary],
        errors: List[str],
        dry_run: bool = False,
    ) -> bool:
        """
        Post a formatted pipeline summary to Slack.

        Returns True if the message was delivered, False on any error.
        Never raises — notification failure should never crash the pipeline.
        """
        blocks = self._build_blocks(
            succeeded, failed, skipped, leads, errors, dry_run
        )
        try:
            response = httpx.post(
                self.webhook_url,
                json={"blocks": blocks},
                timeout=10,
            )
            response.raise_for_status()
            logger.info("Slack notification sent successfully")
            return True
        except httpx.HTTPStatusError as e:
            logger.warning("Slack returned HTTP %s: %s", e.response.status_code, e.response.text)
            return False
        except Exception as e:
            logger.warning("Slack notification failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_blocks(
        self,
        succeeded: int,
        failed: int,
        skipped: int,
        leads: List[LeadSummary],
        errors: List[str],
        dry_run: bool,
    ) -> list:
        total = succeeded + failed + skipped
        mode_tag = " _(dry run)_" if dry_run else ""

        # Tally priority tiers and stale count
        tier_counts = {"high": 0, "medium": 0, "low": 0, "review": 0}
        stale_count = 0
        for lead in leads:
            tier = (lead.priority_tier or "review").lower()
            if tier in tier_counts:
                tier_counts[tier] += 1
            if lead.stale:
                stale_count += 1

        blocks: list = []

        # --- Header ---
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":bar_chart: CRM Pipeline Complete{mode_tag}",
                "emoji": True,
            },
        })

        # --- Run stats ---
        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Processed:* {succeeded}/{total}"},
                {"type": "mrkdwn", "text": f"*Failed:* {failed}"},
                {"type": "mrkdwn", "text": f"*Skipped:* {skipped}"},
                {"type": "mrkdwn", "text": f"*Stale leads:* {stale_count}"},
            ],
        })

        blocks.append({"type": "divider"})

        # --- Priority distribution ---
        dist_parts = []
        for tier, emoji in self.PRIORITY_EMOJI.items():
            dist_parts.append(f"{emoji} *{tier.capitalize()}:* {tier_counts[tier]}")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Priority Distribution*\n" + "   ".join(dist_parts),
            },
        })

        # --- Top 3 leads by ICP score ---
        scored_leads = [l for l in leads if l.icp_score >= 0]
        top_leads = sorted(scored_leads, key=lambda l: l.icp_score, reverse=True)[:3]

        if top_leads:
            blocks.append({"type": "divider"})
            lines = []
            for lead in top_leads:
                tier = (lead.priority_tier or "review").lower()
                emoji = self.PRIORITY_EMOJI.get(tier, ":white_circle:")
                stale_tag = "  :warning: _stale_" if lead.stale else ""
                lines.append(
                    f"{emoji} *{lead.company}* — ICP: {lead.icp_score}/100"
                    f" | {lead.priority_tier.capitalize()}{stale_tag}"
                )
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Top Leads*\n" + "\n".join(lines),
                },
            })

        # --- Errors (capped at 5) ---
        if errors:
            blocks.append({"type": "divider"})
            shown = errors[:5]
            error_text = "\n".join(f"• {e}" for e in shown)
            if len(errors) > 5:
                error_text += f"\n_...and {len(errors) - 5} more_"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":x: *Errors*\n{error_text}",
                },
            })

        return blocks
