import json

import pipeline as pipeline_module


class _StubNotionService:
    def __init__(self, leads):
        self._leads = leads
        self.updated = []

    def validate_database(self):
        return None

    def fetch_leads(self):
        return self._leads

    def update_lead(self, page_id, properties):
        self.updated.append((page_id, properties))
        return True


class _StubClaudeService:
    pass


class _StubICPAgent:
    def __init__(self, _claude):
        pass

    def run(self, _lead):
        return {
            "icp_score": 81,
            "confidence_score": 72,
            "icp_reasoning": "Strong fit.",
            "data_gaps": "",
        }


class _StubResearchAgent:
    def __init__(self, _claude, web_research_service=None):
        _ = web_research_service

    def run(self, _lead):
        return {
            "research_brief": "Research brief",
            "research_confidence": "high",
            "research_citations": "",
            "research_source_count": 0,
            "research_providers": "website:success",
        }


class _StubSignalAgent:
    def __init__(self, _claude):
        pass

    def run(self, _lead):
        return {
            "signal_type": "funding",
            "signal_strength": "high",
            "signal_date": "2026-02-20",
            "signal_reasoning": "Detected funding signal.",
        }


class _StubPriorityAgent:
    def __init__(self, _claude):
        pass

    def run(self, _lead):
        return {
            "priority_tier": "high",
            "priority_reasoning": "High confidence.",
            "stale_flag": False,
            "days_since_contact": 1,
        }


class _StubActionAgent:
    def __init__(self, _claude):
        pass

    def run(self, _lead):
        return {
            "next_action": "outreach_now",
            "action_reasoning": "Act now.",
            "action_confidence": "high",
        }


def _lead(page_id, last_edited_time, existing_results):
    return {
        "page_id": page_id,
        "company_name": page_id,
        "website": "https://example.com",
        "notes": "note",
        "last_contacted": "2026-02-01",
        "status": "Qualified",
        "last_edited_time": last_edited_time,
        "existing_results": existing_results,
    }


def _patch_pipeline_dependencies(monkeypatch, notion_stub):
    monkeypatch.setattr(pipeline_module.Config, "WEB_RESEARCH_ENABLED", False)
    monkeypatch.setattr(pipeline_module.Config, "SLACK_ENABLED", False)
    monkeypatch.setattr(pipeline_module.Config, "INCREMENTAL_ENABLED", True)
    monkeypatch.setattr(pipeline_module, "NotionService", lambda: notion_stub)
    monkeypatch.setattr(pipeline_module, "ClaudeService", _StubClaudeService)
    monkeypatch.setattr(pipeline_module, "ICPAgent", _StubICPAgent)
    monkeypatch.setattr(pipeline_module, "ResearchAgent", _StubResearchAgent)
    monkeypatch.setattr(pipeline_module, "SignalAgent", _StubSignalAgent)
    monkeypatch.setattr(pipeline_module, "PriorityAgent", _StubPriorityAgent)
    monkeypatch.setattr(pipeline_module, "ActionAgent", _StubActionAgent)


def test_incremental_mode_processes_changed_and_missing_outputs_only(tmp_path, monkeypatch):
    state_path = tmp_path / "pipeline_state.json"
    old_run = "2026-02-20T00:00:00+00:00"
    state_path.write_text(json.dumps({"last_successful_run": old_run}))
    monkeypatch.setattr(pipeline_module.Config, "PIPELINE_STATE_FILE", str(state_path))

    leads = [
        _lead(
            "unchanged_scored",
            "2026-02-19T00:00:00+00:00",
            {"icp_score": 90, "priority_tier": "high", "next_action": "outreach_now"},
        ),
        _lead(
            "changed_scored",
            "2026-02-21T00:00:00+00:00",
            {"icp_score": 78, "priority_tier": "medium", "next_action": "reengage"},
        ),
        _lead(
            "missing_outputs",
            "2026-02-18T00:00:00+00:00",
            {"icp_score": None, "priority_tier": "", "next_action": ""},
        ),
    ]
    notion_stub = _StubNotionService(leads)
    _patch_pipeline_dependencies(monkeypatch, notion_stub)

    result = pipeline_module.run_pipeline()

    assert result.succeeded == 2
    assert result.skipped == 1
    assert [page_id for page_id, _ in notion_stub.updated] == ["changed_scored", "missing_outputs"]

    state_payload = json.loads(state_path.read_text())
    assert state_payload["last_successful_run"] != old_run


def test_incremental_mode_without_state_still_skips_already_scored(tmp_path, monkeypatch):
    state_path = tmp_path / "pipeline_state.json"
    monkeypatch.setattr(pipeline_module.Config, "PIPELINE_STATE_FILE", str(state_path))

    leads = [
        _lead(
            "already_scored",
            "2026-02-21T00:00:00+00:00",
            {"icp_score": 84, "priority_tier": "high", "next_action": "outreach_now"},
        ),
        _lead(
            "needs_scoring",
            "2026-02-21T00:00:00+00:00",
            {"icp_score": None, "priority_tier": "", "next_action": ""},
        ),
    ]
    notion_stub = _StubNotionService(leads)
    _patch_pipeline_dependencies(monkeypatch, notion_stub)

    result = pipeline_module.run_pipeline()

    assert result.succeeded == 1
    assert result.skipped == 1
    assert [page_id for page_id, _ in notion_stub.updated] == ["needs_scoring"]


def test_full_refresh_processes_all_leads_even_if_unchanged(tmp_path, monkeypatch):
    state_path = tmp_path / "pipeline_state.json"
    state_path.write_text(json.dumps({"last_successful_run": "2026-02-20T00:00:00+00:00"}))
    monkeypatch.setattr(pipeline_module.Config, "PIPELINE_STATE_FILE", str(state_path))

    leads = [
        _lead(
            "unchanged_scored",
            "2026-02-19T00:00:00+00:00",
            {"icp_score": 90, "priority_tier": "high", "next_action": "outreach_now"},
        ),
    ]
    notion_stub = _StubNotionService(leads)
    _patch_pipeline_dependencies(monkeypatch, notion_stub)

    result = pipeline_module.run_pipeline(full_refresh=True)

    assert result.succeeded == 1
    assert result.skipped == 0
    assert [page_id for page_id, _ in notion_stub.updated] == ["unchanged_scored"]
