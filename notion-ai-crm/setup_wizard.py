"""
Interactive setup wizard for first-time project configuration.

Collects required credentials, writes .env, validates Notion access,
and optionally bootstraps missing output properties in the target database.
"""

import os
import getpass
from pathlib import Path
from typing import Dict, Optional

from dotenv import dotenv_values

from services.notion_service import NotionService

_REQUIRED_KEYS = ("NOTION_API_KEY", "NOTION_DATABASE_ID", "CLAUDE_API_KEY")
_DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def _read_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    values = dotenv_values(path)
    return {k: str(v) for k, v in values.items() if k and v is not None}


def _format_env_value(value: str) -> str:
    if any(ch in value for ch in (" ", "#", '"')):
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _write_env_file(path: Path, values: Dict[str, str]) -> None:
    ordered_keys = list(_REQUIRED_KEYS) + ["CLAUDE_MODEL"]
    extra_keys = sorted(k for k in values if k not in ordered_keys)
    lines = []
    for key in ordered_keys + extra_keys:
        value = values.get(key)
        if value is None:
            continue
        lines.append(f"{key}={_format_env_value(value)}")
    path.write_text("\n".join(lines) + "\n")


def _prompt_value(name: str, default: Optional[str] = None, secret: bool = False) -> str:
    while True:
        label = f"{name}"
        if default:
            label += f" [{default}]"
        label += ": "
        raw = getpass.getpass(label) if secret else input(label)
        value = raw.strip()
        if value:
            return value
        if default:
            return default.strip()
        print(f"{name} is required.")


def _prompt_yes_no(question: str, default_yes: bool = True) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    while True:
        raw = input(f"{question} {suffix}: ").strip().lower()
        if not raw:
            return default_yes
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("Please answer yes or no.")


def _collect_warnings(values: Dict[str, str]) -> list[str]:
    warnings = []
    notion_key = values.get("NOTION_API_KEY", "")
    if notion_key and not (notion_key.startswith("secret_") or notion_key.startswith("ntn_")):
        warnings.append("NOTION_API_KEY does not match expected prefix (secret_ or ntn_).")

    db_id = values.get("NOTION_DATABASE_ID", "")
    if db_id and len(db_id.replace("-", "")) != 32:
        warnings.append("NOTION_DATABASE_ID should be 32 hex characters (dashes optional).")

    claude_key = values.get("CLAUDE_API_KEY", "")
    if claude_key and not claude_key.startswith("sk-ant-"):
        warnings.append("CLAUDE_API_KEY does not match expected prefix (sk-ant-).")
    return warnings


def run_setup_wizard(env_path: str = ".env") -> int:
    """Run interactive project setup."""
    path = Path(env_path).expanduser()
    existing = _read_env_file(path)

    print("\nNotion AI CRM setup wizard\n")
    print("This will save configuration in .env and verify your Notion connection.\n")

    values = dict(existing)
    values["NOTION_API_KEY"] = _prompt_value(
        "NOTION_API_KEY",
        default=existing.get("NOTION_API_KEY"),
        secret=True,
    )
    values["NOTION_DATABASE_ID"] = _prompt_value(
        "NOTION_DATABASE_ID",
        default=existing.get("NOTION_DATABASE_ID"),
    )
    values["CLAUDE_API_KEY"] = _prompt_value(
        "CLAUDE_API_KEY",
        default=existing.get("CLAUDE_API_KEY"),
        secret=True,
    )
    values["CLAUDE_MODEL"] = _prompt_value(
        "CLAUDE_MODEL",
        default=existing.get("CLAUDE_MODEL", _DEFAULT_MODEL),
    )

    bootstrap_schema = _prompt_yes_no(
        "Auto-create missing output columns in your Notion database?",
        default_yes=True,
    )

    warnings = _collect_warnings(values)
    if warnings:
        print("\nPotential issues detected:")
        for warning in warnings:
            print(f"- {warning}")
        if not _prompt_yes_no("Continue anyway?", default_yes=False):
            print("Setup cancelled.")
            return 1

    _write_env_file(path, values)
    os.environ.update(values)
    print(f"\nSaved configuration to {path}")

    try:
        notion = NotionService(
            api_key=values["NOTION_API_KEY"],
            database_id=values["NOTION_DATABASE_ID"],
        )
        notion.validate_database()
        print("Notion access check: OK")

        if bootstrap_schema:
            created = notion.bootstrap_output_properties()
            if created:
                print("Created missing output properties:")
                for name in created:
                    print(f"- {name}")
            else:
                print("Output properties already present. No schema changes needed.")

    except Exception as exc:
        print(f"\nSetup failed during Notion validation: {exc}")
        return 1

    print("\nSetup complete. Next step: run `python main.py --dry-run`.")
    return 0
