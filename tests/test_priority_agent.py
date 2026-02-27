from agents.priority_agent import PriorityAgent


class _StubClaude:
    def __init__(self, response: str):
        self.response = response

    def generate_structured(self, prompt: str, system_prompt: str = "") -> str:
        _ = prompt, system_prompt
        return self.response

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        _ = prompt, system_prompt
        return self.response


def test_high_signal_boosts_medium_to_high():
    agent = PriorityAgent(
        _StubClaude('{"priority_tier":"medium","priority_reasoning":"Balanced signal."}')
    )
    result = agent.run(
        {
            "company_name": "Acme",
            "icp_score": 60,
            "last_contacted": "2026-02-01",
            "status": "Qualified",
            "signal_type": "funding",
            "signal_strength": "high",
        }
    )

    assert result["priority_tier"] == "high"
    assert "Boosted from medium to high" in result["priority_reasoning"]


def test_high_signal_does_not_boost_weak_icp_fit():
    agent = PriorityAgent(_StubClaude('{"priority_tier":"medium","priority_reasoning":"Balanced signal."}'))
    result = agent.run(
        {
            "company_name": "Acme",
            "icp_score": 30,
            "last_contacted": "2026-02-20",
            "status": "Qualified",
            "signal_type": "funding",
            "signal_strength": "high",
        }
    )

    assert result["priority_tier"] == "low"
    assert "Boosted from" not in result["priority_reasoning"]


def test_non_high_signal_does_not_boost():
    agent = PriorityAgent(_StubClaude('{"priority_tier":"medium","priority_reasoning":"Balanced signal."}'))
    result = agent.run(
        {
            "company_name": "Acme",
            "icp_score": 60,
            "last_contacted": "2026-02-01",
            "status": "Qualified",
            "signal_type": "hiring",
            "signal_strength": "medium",
        }
    )

    assert result["priority_tier"] == "medium"
    assert "Boosted from" not in result["priority_reasoning"]
