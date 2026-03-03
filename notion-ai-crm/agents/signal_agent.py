"""
Signal Agent.

Detects trigger signals from CRM notes/research content and returns
normalized signal fields for prioritization and reporting.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_SIGNAL_RULES = [
    {
        "signal_type": "buying_intent",
        "signal_strength": "high",
        "patterns": [
            r"\brequested demo\b",
            r"\brfp\b",
            r"\bevaluating vendors?\b",
            r"\bbudget approved\b",
            r"\bpilot program\b",
            r"\bactively searching\b",
        ],
    },
    {
        "signal_type": "funding",
        "signal_strength": "high",
        "patterns": [
            r"\bseries [a-e]\b",
            r"\bseed round\b",
            r"\braised \$?\d",
            r"\bnew funding\b",
            r"\bventure[- ]backed\b",
        ],
    },
    {
        "signal_type": "leadership_change",
        "signal_strength": "high",
        "patterns": [
            r"\bnew (vp|head|chief|c[mo]{2})\b",
            r"\bnew ceo\b",
            r"\bnew cro\b",
            r"\bnew cmo\b",
            r"\bnew head of sales\b",
        ],
    },
    {
        "signal_type": "hiring",
        "signal_strength": "medium",
        "patterns": [
            r"\bhiring\b",
            r"\bexpanding (sales|gtm|revenue) team\b",
            r"\bjob openings?\b",
            r"\bheadcount growth\b",
        ],
    },
    {
        "signal_type": "technology_initiative",
        "signal_strength": "medium",
        "patterns": [
            r"\bdigital transformation\b",
            r"\bautomation initiative\b",
            r"\bmigrating (to|from)\b",
            r"\breplatform(ing)?\b",
            r"\bmodernization\b",
        ],
    },
]

_STRENGTH_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


class SignalAgent:
    """Detect lead signals to support priority boosting."""

    def __init__(self, _claude_service=None):
        # Kept for a drop-in interface with other agents in the pipeline.
        pass

    def run(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        text = self._build_context_text(lead)
        detected = self._detect_signal(text)
        signal_date = self._extract_signal_date(lead)

        if not detected:
            return {
                "signal_type": "none",
                "signal_strength": "none",
                "signal_date": signal_date,
                "signal_reasoning": "No strong trigger signals detected from notes/research.",
            }

        signal_type = detected["signal_type"]
        signal_strength = detected["signal_strength"]
        matched_text = detected["matched_text"]
        logger.info(
            "Signals for %s: %s (%s)",
            lead.get("company_name"),
            signal_type,
            signal_strength,
        )
        return {
            "signal_type": signal_type,
            "signal_strength": signal_strength,
            "signal_date": signal_date,
            "signal_reasoning": (
                f"Detected {signal_type} ({signal_strength}) from phrase: '{matched_text}'."
            ),
        }

    @staticmethod
    def _build_context_text(lead: Dict[str, Any]) -> str:
        parts = [
            lead.get("company_name", ""),
            lead.get("notes", ""),
            lead.get("research_brief", ""),
            lead.get("status", ""),
        ]
        return "\n".join(str(part) for part in parts if part)

    @staticmethod
    def _detect_signal(text: str) -> Optional[Dict[str, str]]:
        if not text.strip():
            return None

        best: Optional[Dict[str, str]] = None
        best_rank = -1
        haystack = text.lower()

        for rule in _SIGNAL_RULES:
            for pattern in rule["patterns"]:
                match = re.search(pattern, haystack)
                if not match:
                    continue
                rank = _STRENGTH_RANK.get(rule["signal_strength"], 0)
                if rank > best_rank:
                    best_rank = rank
                    best = {
                        "signal_type": rule["signal_type"],
                        "signal_strength": rule["signal_strength"],
                        "matched_text": match.group(0)[:120],
                    }
                break

        return best

    def _extract_signal_date(self, lead: Dict[str, Any]) -> Optional[str]:
        notes = str(lead.get("notes", "") or "")
        iso_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", notes)
        if iso_match:
            return iso_match.group(0)

        for candidate in (lead.get("last_edited_time"), lead.get("last_contacted")):
            parsed = self._coerce_date(candidate)
            if parsed:
                return parsed
        return None

    @staticmethod
    def _coerce_date(value: Any) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.date().isoformat()
        except ValueError:
            return None
