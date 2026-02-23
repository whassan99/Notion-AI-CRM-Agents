from pathlib import Path

import setup_wizard


class _StubNotionService:
    created_instances = []

    def __init__(self, api_key, database_id):
        self.api_key = api_key
        self.database_id = database_id
        self.validated = False
        self.bootstrapped = False
        _StubNotionService.created_instances.append(self)

    def validate_database(self):
        self.validated = True

    def bootstrap_output_properties(self):
        self.bootstrapped = True
        return ["icp_score", "priority_tier"]


class _FailingNotionService:
    def __init__(self, api_key, database_id):
        self.api_key = api_key
        self.database_id = database_id

    def validate_database(self):
        raise RuntimeError("validation failed")

    def bootstrap_output_properties(self):
        return []


def test_setup_wizard_writes_env_and_bootstraps_schema(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    db_id = "a" * 32

    inputs = iter([db_id, "claude-sonnet-4-5-20250929", "y"])
    secrets = iter(["secret_test_token", "sk-ant-test-key"])

    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    monkeypatch.setattr(setup_wizard.getpass, "getpass", lambda _prompt="": next(secrets))
    monkeypatch.setattr(setup_wizard, "NotionService", _StubNotionService)

    exit_code = setup_wizard.run_setup_wizard(env_path=str(env_path))

    assert exit_code == 0
    content = env_path.read_text()
    assert "NOTION_API_KEY=secret_test_token" in content
    assert f"NOTION_DATABASE_ID={db_id}" in content
    assert "CLAUDE_API_KEY=sk-ant-test-key" in content
    assert "CLAUDE_MODEL=claude-sonnet-4-5-20250929" in content

    assert _StubNotionService.created_instances
    instance = _StubNotionService.created_instances[-1]
    assert instance.validated
    assert instance.bootstrapped


def test_setup_wizard_returns_error_when_notion_validation_fails(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    db_id = "b" * 32
    inputs = iter([db_id, "claude-sonnet-4-5-20250929", "n"])
    secrets = iter(["secret_fail_token", "sk-ant-fail-key"])

    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    monkeypatch.setattr(setup_wizard.getpass, "getpass", lambda _prompt="": next(secrets))
    monkeypatch.setattr(setup_wizard, "NotionService", _FailingNotionService)

    exit_code = setup_wizard.run_setup_wizard(env_path=str(env_path))

    assert exit_code == 1
    assert Path(env_path).exists()
