"""
Notion Service using the official notion-client SDK.

Handles fetching leads with pagination, updating pages, and
database validation with clear error messages.
"""

import time
import logging
from typing import List, Dict, Any, Optional

from notion_client import Client, APIResponseError

from config import Config

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0


def _retry(func):
    """Decorator: retry on transient Notion API errors with exponential backoff."""
    def wrapper(*args, **kwargs):
        last_error = None
        for attempt in range(_MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except APIResponseError as e:
                if e.status in (429, 500, 502, 503):
                    last_error = e
                    delay = _BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Notion API %d (attempt %d/%d), retrying in %.1fs...",
                        e.status, attempt + 1, _MAX_RETRIES, delay,
                    )
                    time.sleep(delay)
                else:
                    raise
        raise RuntimeError(f"Notion API call failed after {_MAX_RETRIES} attempts: {last_error}")
    return wrapper


class NotionService:
    """Service for interacting with Notion CRM database."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        database_id: Optional[str] = None,
    ):
        self.api_key = api_key or Config.NOTION_API_KEY
        self.database_id = database_id or Config.NOTION_DATABASE_ID
        self.client = Client(auth=self.api_key)

    def validate_database(self) -> None:
        """
        Check that the database exists, is shared with the integration,
        and has expected input columns. Raises with actionable messages.
        """
        try:
            db = self._retrieve_database()
        except APIResponseError as e:
            if e.status == 404:
                raise RuntimeError(
                    f"Database not found (ID: {self.database_id}).\n"
                    "  - Double-check NOTION_DATABASE_ID in your .env\n"
                    "  - Make sure you shared the database with your integration:\n"
                    "    Open the database in Notion → '...' menu → 'Connections' → add your integration"
                ) from e
            if e.status == 401:
                raise RuntimeError(
                    "Notion API key is invalid or expired.\n"
                    "  Check NOTION_API_KEY in your .env\n"
                    "  Manage integrations at: https://www.notion.so/my-integrations"
                ) from e
            raise

        # Check for expected input properties
        db_props = set(db.get("properties", {}).keys())
        expected = {
            Config.NOTION_PROP_COMPANY,
            Config.NOTION_PROP_WEBSITE,
            Config.NOTION_PROP_NOTES,
            Config.NOTION_PROP_LAST_CONTACTED,
            Config.NOTION_PROP_STATUS,
        }
        missing = expected - db_props
        if missing:
            logger.warning(
                "Database is missing expected columns: %s. "
                "Some agent features may not work correctly. "
                "See NOTION_SETUP.md for the required schema.",
                ", ".join(sorted(missing)),
            )

    @_retry
    def _retrieve_database(self) -> Dict:
        return self.client.databases.retrieve(database_id=self.database_id)

    def fetch_leads(self, filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Fetch all leads with automatic pagination."""
        leads = []
        start_cursor = None

        while True:
            response = self._query_database(filter_dict, start_cursor)
            for page in response.get("results", []):
                lead = self._extract_lead_from_page(page)
                leads.append(lead)

            if not response.get("has_more"):
                break
            start_cursor = response.get("next_cursor")

        return leads

    @_retry
    def _query_database(
        self,
        filter_dict: Optional[Dict] = None,
        start_cursor: Optional[str] = None,
    ) -> Dict:
        kwargs: Dict[str, Any] = {"database_id": self.database_id}
        if filter_dict:
            kwargs["filter"] = filter_dict
        if start_cursor:
            kwargs["start_cursor"] = start_cursor
        return self.client.databases.query(**kwargs)

    def update_lead(self, page_id: str, properties: Dict[str, Any]) -> bool:
        """Update a Notion page with agent results."""
        try:
            notion_properties = self._format_properties_for_notion(properties)
            self._update_page(page_id, notion_properties)
            return True
        except APIResponseError as e:
            logger.error("Failed to update page %s: %s", page_id, e)
            return False

    @_retry
    def _update_page(self, page_id: str, notion_properties: Dict) -> None:
        self.client.pages.update(page_id=page_id, properties=notion_properties)

    # --- Data extraction ---

    def _extract_lead_from_page(self, page: Dict) -> Dict[str, Any]:
        """Extract clean lead data from a Notion page."""
        props = page.get("properties", {})
        return {
            "page_id": page["id"],
            "company_name": self._get_title(props.get(Config.NOTION_PROP_COMPANY, {})),
            "website": self._get_url(props.get(Config.NOTION_PROP_WEBSITE, {})),
            "notes": self._get_rich_text(props.get(Config.NOTION_PROP_NOTES, {})),
            "last_contacted": self._get_date(props.get(Config.NOTION_PROP_LAST_CONTACTED, {})),
            "status": self._get_select(props.get(Config.NOTION_PROP_STATUS, {})),
        }

    def _format_properties_for_notion(self, properties: Dict[str, Any]) -> Dict:
        """Convert a simple dict to Notion property format."""
        notion_props = {}
        for key, value in properties.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                notion_props[key] = {"number": value}
            elif isinstance(value, bool):
                notion_props[key] = {"checkbox": value}
            elif isinstance(value, str):
                # Notion rich_text content is limited to 2000 chars per block
                text = value[:2000]
                notion_props[key] = {
                    "rich_text": [{"text": {"content": text}}]
                }
        return notion_props

    # --- Property helpers ---

    @staticmethod
    def _get_title(prop: Dict) -> str:
        title_list = prop.get("title", [])
        if title_list:
            return title_list[0].get("text", {}).get("content", "")
        return ""

    @staticmethod
    def _get_rich_text(prop: Dict) -> str:
        text_list = prop.get("rich_text", [])
        return " ".join(t.get("text", {}).get("content", "") for t in text_list)

    @staticmethod
    def _get_url(prop: Dict) -> str:
        return prop.get("url") or ""

    @staticmethod
    def _get_date(prop: Dict) -> Optional[str]:
        date_obj = prop.get("date")
        if date_obj:
            return date_obj.get("start")
        return None

    @staticmethod
    def _get_select(prop: Dict) -> str:
        select_obj = prop.get("select")
        if select_obj:
            return select_obj.get("name", "")
        return ""
