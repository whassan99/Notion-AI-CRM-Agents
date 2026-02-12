"""
Base agent with shared utilities: prompt loading, JSON parsing, LLM calling.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from services.claude_service import ClaudeService

logger = logging.getLogger(__name__)


class BaseAgent:
    """Shared base for all CRM agents."""

    # Subclasses set this to the prompt filename, e.g. "icp_prompt.txt"
    prompt_file: str = ""

    def __init__(self, claude_service: ClaudeService):
        self.claude = claude_service
        self.prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load prompt template from the prompts/ directory."""
        if not self.prompt_file:
            return ""
        path = Path(__file__).parent.parent / "prompts" / self.prompt_file
        try:
            return path.read_text()
        except FileNotFoundError:
            logger.warning("Prompt file not found: %s", path)
            return ""

    def _call_llm(
        self,
        prompt: str,
        system_prompt: str,
        structured: bool = True,
    ) -> str:
        """Call Claude via the shared service."""
        if structured:
            return self.claude.generate_structured(prompt, system_prompt=system_prompt)
        return self.claude.generate(prompt, system_prompt=system_prompt)

    @staticmethod
    def _parse_json_response(response: str) -> Optional[Dict[str, Any]]:
        """
        Extract and parse JSON from an LLM response.

        Handles:
          - Raw JSON
          - JSON wrapped in ```json ... ``` blocks
          - JSON embedded in surrounding text
        """
        text = response.strip()

        # Try to extract from ```json ... ``` fences
        if "```" in text:
            start = text.find("```json")
            if start != -1:
                start = text.index("\n", start) + 1
            else:
                start = text.find("```") + 3
                # Skip to next line
                nl = text.find("\n", start)
                if nl != -1:
                    start = nl + 1
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in text
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start : brace_end + 1])
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _clamp(value: float, min_val: float = 0, max_val: float = 100) -> float:
        """Clamp a value to [min_val, max_val]."""
        return max(min_val, min(max_val, value))
