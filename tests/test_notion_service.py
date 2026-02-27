from services.notion_service import NotionService
from config import Config


def test_maps_canonical_output_keys_to_configured_names(monkeypatch):
    monkeypatch.setattr(Config, "NOTION_PROP_ICP_SCORE", "ICP Score")
    monkeypatch.setattr(Config, "NOTION_PROP_NEXT_ACTION", "Next Action")
    monkeypatch.setattr(Config, "NOTION_PROP_RESEARCH_CONFIDENCE", "Research Confidence")
    monkeypatch.setattr(Config, "NOTION_PROP_RESEARCH_PROVIDERS", "Research Providers")
    monkeypatch.setattr(Config, "NOTION_PROP_SIGNAL_TYPE", "Signal Type")
    service = NotionService(api_key="secret_test", database_id="dbid")

    mapped = service._map_output_property_names(
        {
            "icp_score": 91,
            "next_action": "outreach_now",
            "research_confidence": "high",
            "research_providers": "website:success",
            "signal_type": "funding",
            "custom": "x",
        }
    )

    assert mapped["ICP Score"] == 91
    assert mapped["Next Action"] == "outreach_now"
    assert mapped["Research Confidence"] == "high"
    assert mapped["Research Providers"] == "website:success"
    assert mapped["Signal Type"] == "funding"
    assert mapped["custom"] == "x"


def test_formats_by_schema_type_and_skips_unknown_properties():
    service = NotionService(api_key="secret_test", database_id="dbid")
    service._database_properties_cache = {
        "icp_score": {"type": "number"},
        "priority_tier": {"type": "select"},
        "priority_reasoning": {"type": "rich_text"},
        "stale_flag": {"type": "checkbox"},
    }

    notion_props = service._format_properties_for_notion(
        {
            "icp_score": 88,
            "priority_tier": "high",
            "priority_reasoning": "Strong fit and recent contact",
            "stale_flag": False,
            "days_since_contact": 3,
        }
    )

    assert notion_props["icp_score"] == {"number": 88}
    assert notion_props["priority_tier"] == {"select": {"name": "high"}}
    assert "priority_reasoning" in notion_props
    assert notion_props["stale_flag"] == {"checkbox": False}
    assert "days_since_contact" not in notion_props


def test_prepare_update_properties_maps_then_formats(monkeypatch):
    monkeypatch.setattr(Config, "NOTION_PROP_ICP_SCORE", "ICP Score")
    service = NotionService(api_key="secret_test", database_id="dbid")
    service._database_properties_cache = {"ICP Score": {"type": "number"}}

    notion_props = service._prepare_update_properties({"icp_score": 77})

    assert notion_props == {"ICP Score": {"number": 77}}


def test_extract_lead_includes_existing_results_and_last_edited_time():
    service = NotionService(api_key="secret_test", database_id="dbid")
    page = {
        "id": "page-1",
        "last_edited_time": "2026-02-22T11:00:00.000Z",
        "properties": {
            Config.NOTION_PROP_COMPANY: {
                "type": "title",
                "title": [{"plain_text": "Acme", "text": {"content": "Acme"}}],
            },
            Config.NOTION_PROP_WEBSITE: {"type": "url", "url": "https://acme.com"},
            Config.NOTION_PROP_NOTES: {
                "type": "rich_text",
                "rich_text": [{"plain_text": "B2B SaaS", "text": {"content": "B2B SaaS"}}],
            },
            Config.NOTION_PROP_LAST_CONTACTED: {
                "type": "date",
                "date": {"start": "2026-02-20"},
            },
            Config.NOTION_PROP_STATUS: {
                "type": "select",
                "select": {"name": "Qualified"},
            },
            Config.NOTION_PROP_ICP_SCORE: {"type": "number", "number": 88},
            Config.NOTION_PROP_PRIORITY_TIER: {
                "type": "select",
                "select": {"name": "high"},
            },
            Config.NOTION_PROP_NEXT_ACTION: {
                "type": "select",
                "select": {"name": "outreach_now"},
            },
        },
    }

    lead = service._extract_lead_from_page(page)

    assert lead["company_name"] == "Acme"
    assert lead["last_edited_time"] == "2026-02-22T11:00:00.000Z"
    assert lead["existing_results"]["icp_score"] == 88
    assert lead["existing_results"]["priority_tier"] == "high"
    assert lead["existing_results"]["next_action"] == "outreach_now"


def test_bootstrap_output_properties_creates_only_missing(monkeypatch):
    service = NotionService(api_key="secret_test", database_id="dbid")
    score_col = Config.NOTION_PROP_ICP_SCORE
    priority_col = Config.NOTION_PROP_PRIORITY_TIER
    next_action_col = Config.NOTION_PROP_NEXT_ACTION

    service._database_properties_cache = {
        score_col: {"type": "number"},
    }
    captured = {}

    def _fake_update(props):
        captured.update(props)

    monkeypatch.setattr(service, "_update_database_properties", _fake_update)
    monkeypatch.setattr(
        service,
        "_retrieve_database",
        lambda: {"properties": {**service._database_properties_cache, **captured}},
    )

    created = service.bootstrap_output_properties()

    assert score_col not in captured
    assert priority_col in captured
    assert next_action_col in captured
    assert score_col not in created
    assert priority_col in created
    assert next_action_col in created


def test_bootstrap_output_properties_noop_when_all_present(monkeypatch):
    service = NotionService(api_key="secret_test", database_id="dbid")
    full_schema = service._output_property_schema()
    service._database_properties_cache = {
        name: {"type": next(iter(spec.keys()))}
        for name, spec in full_schema.items()
    }
    called = {"updated": False}

    def _fake_update(_props):
        called["updated"] = True

    monkeypatch.setattr(service, "_update_database_properties", _fake_update)

    created = service.bootstrap_output_properties()

    assert created == []
    assert not called["updated"]
