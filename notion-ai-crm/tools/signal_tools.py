"""Signal detection tool — fully deterministic, no LLM needed."""

from typing import Any

from agents.signal_agent import SignalAgent


_agent = SignalAgent()


def detect_signals(
    company_name: str = "",
    notes: str = "",
    status: str = "",
    research_brief: str = "",
    last_contacted: str | None = None,
    last_edited_time: str | None = None,
) -> dict[str, Any]:
    """Detect trigger signals from lead data using regex pattern matching.

    Returns signal_type, signal_strength, signal_date, signal_reasoning.
    No LLM call needed — this runs entirely inside the server.
    """
    lead = {
        "company_name": company_name,
        "notes": notes,
        "status": status,
        "research_brief": research_brief,
        "last_contacted": last_contacted,
        "last_edited_time": last_edited_time,
    }
    return _agent.run(lead)
