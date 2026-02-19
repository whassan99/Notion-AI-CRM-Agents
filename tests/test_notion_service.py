from services.notion_service import NotionService
from config import Config


def test_maps_canonical_output_keys_to_configured_names(monkeypatch):
    monkeypatch.setattr(Config, "NOTION_PROP_ICP_SCORE", "ICP Score")
    service = NotionService(api_key="secret_test", database_id="dbid")

    mapped = service._map_output_property_names({"icp_score": 91, "custom": "x"})

    assert mapped["ICP Score"] == 91
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
