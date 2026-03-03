"""
Claude LLM Service with retry logic and exponential backoff.
"""

import time
import logging
from typing import Optional

from anthropic import Anthropic, RateLimitError, APIConnectionError, APIStatusError

from config import Config

logger = logging.getLogger(__name__)

# Retryable error types
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds


class ClaudeService:
    """Wrapper for Anthropic Claude API with retry and backoff."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or Config.CLAUDE_API_KEY
        self.model = model or Config.CLAUDE_MODEL
        self.client = Anthropic(api_key=self.api_key)

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.5,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Generate a response from Claude with automatic retry.

        Retries on rate limits, connection errors, and 5xx status codes.
        Raises immediately on auth errors (401/403).
        """
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        last_error = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self.client.messages.create(**kwargs)
                return response.content[0].text

            except RateLimitError as e:
                last_error = e
                delay = _BASE_DELAY * (2 ** attempt)
                logger.warning("Rate limited (attempt %d/%d), retrying in %.1fs...", attempt + 1, _MAX_RETRIES, delay)
                time.sleep(delay)

            except APIConnectionError as e:
                last_error = e
                delay = _BASE_DELAY * (2 ** attempt)
                logger.warning("Connection error (attempt %d/%d), retrying in %.1fs...", attempt + 1, _MAX_RETRIES, delay)
                time.sleep(delay)

            except APIStatusError as e:
                if e.status_code in _RETRYABLE_STATUS_CODES:
                    last_error = e
                    delay = _BASE_DELAY * (2 ** attempt)
                    logger.warning("Server error %d (attempt %d/%d), retrying in %.1fs...", e.status_code, attempt + 1, _MAX_RETRIES, delay)
                    time.sleep(delay)
                else:
                    # Non-retryable (401, 403, 400, etc.) — raise immediately
                    raise

        # All retries exhausted
        raise RuntimeError(f"Claude API call failed after {_MAX_RETRIES} attempts: {last_error}")

    def generate_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate a structured response with low temperature (0.2)."""
        return self.generate(
            prompt=prompt,
            max_tokens=1500,
            temperature=0.2,
            system_prompt=system_prompt,
        )
