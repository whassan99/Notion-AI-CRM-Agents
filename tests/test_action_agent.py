from agents.action_agent import ActionAgent


class _StubClaude:
    def __init__(self, response: str):
        self.response = response

    def generate_structured(self, prompt: str, system_prompt: str = "") -> str:
        return self.response

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return self.response


def test_review_priority_returns_enrich_data_without_llm_call():
    agent = ActionAgent(_StubClaude('{"next_action":"hold"}'))
    result = agent.run({"company_name": "Acme", "priority_tier": "review"})

    assert result["next_action"] == "enrich_data"
    assert result["action_confidence"] == "high"


def test_high_non_stale_returns_outreach_now():
    agent = ActionAgent(_StubClaude('{"next_action":"hold"}'))
    result = agent.run({"company_name": "Acme", "priority_tier": "high", "stale_flag": False})

    assert result["next_action"] == "outreach_now"
    assert result["action_confidence"] == "high"


def test_medium_priority_uses_llm_json():
    response = (
        '{"next_action":"reengage","action_reasoning":"There is signal but no recent response.",'
        '"action_confidence":"medium"}'
    )
    agent = ActionAgent(_StubClaude(response))
    result = agent.run({"company_name": "Acme", "priority_tier": "medium"})

    assert result["next_action"] == "reengage"
    assert result["action_confidence"] == "medium"


def test_invalid_llm_json_defaults_to_enrich_data():
    agent = ActionAgent(_StubClaude("not-json"))
    result = agent.run({"company_name": "Acme", "priority_tier": "medium"})

    assert result["next_action"] == "enrich_data"
    assert result["action_confidence"] == "low"


def test_invalid_action_and_confidence_are_normalized():
    response = '{"next_action":"call_now","action_reasoning":"x","action_confidence":"certain"}'
    agent = ActionAgent(_StubClaude(response))
    result = agent.run({"company_name": "Acme", "priority_tier": "medium"})

    assert result["next_action"] == "enrich_data"
    assert result["action_confidence"] == "medium"
