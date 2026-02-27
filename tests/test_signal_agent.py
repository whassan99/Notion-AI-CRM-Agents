from agents.signal_agent import SignalAgent


def test_detects_high_signal_and_uses_date_from_notes():
    agent = SignalAgent()
    result = agent.run(
        {
            "company_name": "Acme",
            "notes": "2026-02-10 - Team requested demo after evaluating vendors.",
            "research_brief": "",
            "last_edited_time": "2026-02-20T11:00:00.000Z",
        }
    )

    assert result["signal_type"] == "buying_intent"
    assert result["signal_strength"] == "high"
    assert result["signal_date"] == "2026-02-10"
    assert "requested demo" in result["signal_reasoning"]


def test_detects_signal_from_research_brief_when_notes_are_empty():
    agent = SignalAgent()
    result = agent.run(
        {
            "company_name": "Acme",
            "notes": "",
            "research_brief": "The company is hiring and expanding sales team this quarter.",
            "last_edited_time": "2026-02-20T11:00:00.000Z",
        }
    )

    assert result["signal_type"] == "hiring"
    assert result["signal_strength"] == "medium"
    assert result["signal_date"] == "2026-02-20"


def test_returns_none_when_no_signals_found():
    agent = SignalAgent()
    result = agent.run(
        {
            "company_name": "Acme",
            "notes": "General discovery call with no clear trigger.",
            "research_brief": "",
            "last_contacted": "2026-02-03",
        }
    )

    assert result["signal_type"] == "none"
    assert result["signal_strength"] == "none"
    assert result["signal_date"] == "2026-02-03"
