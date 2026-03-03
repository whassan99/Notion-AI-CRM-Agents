"""
Web Research Service for enriching leads with real website data.

Fetches and parses website content, optionally searches via Brave API,
respects robots.txt, and provides in-memory caching.
"""

import logging
import time
import urllib.robotparser
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from config import Config

logger = logging.getLogger(__name__)

# Tags whose content is not useful for research
_STRIP_TAGS = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript", "iframe"}

# Max characters to keep from scraped content (~3000 tokens)
_MAX_CONTENT_CHARS = 12_000

# Subpages to try scraping beyond the homepage
_SUBPAGES = ["/about", "/pricing", "/blog"]
_SUPPORTED_PROVIDERS = ("website", "brave")


class WebResearchResult:
    """Structured result from web research for a single lead."""

    def __init__(
        self,
        website_content: str = "",
        search_results: str = "",
        pages_fetched: int = 0,
        source_urls: Optional[List[str]] = None,
        provider_trace: Optional[List[Dict[str, Any]]] = None,
        errors: Optional[List[str]] = None,
    ):
        self.website_content = website_content
        self.search_results = search_results
        self.pages_fetched = pages_fetched
        self.source_urls = source_urls or []
        self.provider_trace = provider_trace or []
        self.errors = errors or []

    @property
    def has_content(self) -> bool:
        """Whether any useful content was retrieved."""
        return bool(self.website_content.strip() or self.search_results.strip())

    def to_prompt_section(self) -> str:
        """Format research results for injection into a prompt."""
        if not self.has_content:
            return "No web research data was available for this lead."

        parts = []
        if self.website_content:
            parts.append(f"WEBSITE CONTENT:\n{self.website_content}")
        if self.search_results:
            parts.append(f"SEARCH RESULTS:\n{self.search_results}")
        if self.source_urls:
            sources = "\n".join(f"- {url}" for url in self.source_urls)
            parts.append(f"SOURCES:\n{sources}")
        return "\n\n".join(parts)


class WebResearchService:
    """Fetches and processes web content for lead enrichment."""

    def __init__(
        self,
        timeout: Optional[int] = None,
        delay: Optional[float] = None,
        max_pages: Optional[int] = None,
        brave_api_key: Optional[str] = None,
        provider_order: Optional[List[str]] = None,
        target_chars: Optional[int] = None,
        run_all_providers: Optional[bool] = None,
    ):
        self.timeout = timeout if timeout is not None else Config.WEB_RESEARCH_TIMEOUT
        self.delay = delay if delay is not None else Config.WEB_RESEARCH_DELAY
        self.max_pages = max_pages if max_pages is not None else Config.WEB_RESEARCH_MAX_PAGES
        self.brave_api_key = brave_api_key if brave_api_key is not None else Config.BRAVE_SEARCH_API_KEY
        self.provider_order = (
            provider_order
            if provider_order is not None
            else self._parse_provider_order(Config.WEB_RESEARCH_WATERFALL)
        )
        self.target_chars = (
            target_chars
            if target_chars is not None
            else Config.WEB_RESEARCH_TARGET_CHARS
        )
        self.run_all_providers = (
            run_all_providers
            if run_all_providers is not None
            else Config.WEB_RESEARCH_RUN_ALL_PROVIDERS
        )
        self._cache: Dict[str, str] = {}
        self._robot_parsers: Dict[str, urllib.robotparser.RobotFileParser] = {}
        self._request_count = 0

    def research_lead(self, lead: Dict[str, Any]) -> WebResearchResult:
        """
        Gather web research for a lead.

        Scrapes the lead's website and optionally runs a Brave search.
        Returns a WebResearchResult with all gathered content.
        """
        self._request_count = 0
        result = WebResearchResult()

        website = lead.get("website", "")
        company_name = lead.get("company_name", "")
        for provider in self.provider_order:
            if provider == "website":
                self._run_website_provider(result, website)
            elif provider == "brave":
                self._run_brave_provider(result, company_name)

            if (
                not self.run_all_providers
                and self._combined_chars(result) >= self.target_chars
            ):
                result.provider_trace.append(
                    {
                        "provider": "waterfall",
                        "status": "stop_threshold_reached",
                        "combined_chars": self._combined_chars(result),
                        "target_chars": self.target_chars,
                    }
                )
                break

        # Deduplicate while preserving order
        result.source_urls = list(dict.fromkeys(result.source_urls))

        return result

    def _run_website_provider(self, result: WebResearchResult, website: str) -> None:
        if not website:
            result.provider_trace.append(
                {"provider": "website", "status": "skipped", "reason": "missing_website"}
            )
            return
        try:
            url = self._normalize_url(website)
            content = self._scrape_website(url)
            if content:
                truncated = self._truncate(content)
                result.website_content = truncated
                result.pages_fetched = self._request_count
                result.source_urls.append(url)
                result.provider_trace.append(
                    {
                        "provider": "website",
                        "status": "success",
                        "chars": len(truncated),
                        "pages_fetched": result.pages_fetched,
                    }
                )
                return
            result.provider_trace.append(
                {"provider": "website", "status": "no_content"}
            )
        except Exception as exc:
            logger.warning("Website provider failed for %s: %s", website, exc)
            result.errors.append(f"website provider failed: {exc}")
            result.provider_trace.append(
                {"provider": "website", "status": "error", "error": str(exc)}
            )

    def _run_brave_provider(self, result: WebResearchResult, company_name: str) -> None:
        if not self.brave_api_key:
            result.provider_trace.append(
                {"provider": "brave", "status": "skipped", "reason": "missing_api_key"}
            )
            return
        if not company_name:
            result.provider_trace.append(
                {"provider": "brave", "status": "skipped", "reason": "missing_company_name"}
            )
            return

        try:
            search_content, search_urls = self._brave_search(company_name)
            if search_content:
                result.search_results = search_content
                result.source_urls.extend(search_urls)
                result.provider_trace.append(
                    {
                        "provider": "brave",
                        "status": "success",
                        "chars": len(search_content),
                        "source_count": len(search_urls),
                    }
                )
                return
            result.provider_trace.append(
                {"provider": "brave", "status": "no_content"}
            )
        except Exception as exc:
            logger.warning("Brave provider failed for %s: %s", company_name, exc)
            result.errors.append(f"brave provider failed: {exc}")
            result.provider_trace.append(
                {"provider": "brave", "status": "error", "error": str(exc)}
            )

    @staticmethod
    def _combined_chars(result: WebResearchResult) -> int:
        return len(result.website_content or "") + len(result.search_results or "")

    @staticmethod
    def _parse_provider_order(raw: str) -> List[str]:
        providers = []
        for item in (raw or "").split(","):
            normalized = item.strip().lower()
            if normalized in _SUPPORTED_PROVIDERS and normalized not in providers:
                providers.append(normalized)
        return providers or ["website", "brave"]

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Ensure URL has a scheme and no trailing slash."""
        url = url.strip()
        if not url:
            return url
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url.rstrip("/")

    def _scrape_website(self, base_url: str) -> str:
        """Scrape the homepage and subpages of a website."""
        pages_content = []

        # Always try the homepage first
        homepage_content = self._fetch_and_parse(base_url)
        if homepage_content:
            pages_content.append(f"[Homepage]\n{homepage_content}")

        # Try subpages up to max_pages limit (homepage counts as 1)
        for subpage in _SUBPAGES:
            if len(pages_content) >= self.max_pages:
                break
            if self._request_count >= 5:
                logger.debug("Hit per-lead request limit (5)")
                break

            page_url = urljoin(base_url + "/", subpage.lstrip("/"))
            content = self._fetch_and_parse(page_url)
            if content:
                pages_content.append(f"[{subpage}]\n{content}")

        return "\n\n".join(pages_content)

    def _fetch_and_parse(self, url: str) -> str:
        """Fetch a single URL and extract clean text. Returns empty string on failure."""
        # Check cache first
        if url in self._cache:
            logger.debug("Cache hit: %s", url)
            return self._cache[url]

        # Check robots.txt
        if not self._is_allowed(url):
            logger.info("Blocked by robots.txt: %s", url)
            self._cache[url] = ""
            return ""

        # Rate limiting
        if self._request_count > 0:
            time.sleep(self.delay)

        self._request_count += 1

        try:
            response = httpx.get(
                url,
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "NotionCRMBot/1.0 (lead research)"},
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            logger.warning("Timeout fetching %s", url)
            self._cache[url] = ""
            return ""
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP %d fetching %s", e.response.status_code, url)
            self._cache[url] = ""
            return ""
        except httpx.RequestError as e:
            logger.warning("Request error fetching %s: %s", url, e)
            self._cache[url] = ""
            return ""

        content = self._extract_text(response.text)
        self._cache[url] = content
        return content

    @staticmethod
    def _extract_text(html: str) -> str:
        """Extract meaningful text from HTML, stripping nav, scripts, etc."""
        soup = BeautifulSoup(html, "lxml")

        # Remove unwanted tags
        for tag in soup.find_all(_STRIP_TAGS):
            tag.decompose()

        # Get text, collapsing whitespace
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines()]
        # Remove blank lines and very short lines (likely UI fragments)
        lines = [line for line in lines if len(line) > 2]
        return "\n".join(lines)

    def _is_allowed(self, url: str) -> bool:
        """Check if the URL is allowed by robots.txt."""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        if robots_url not in self._robot_parsers:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:
                # If we can't read robots.txt, assume allowed
                logger.debug("Could not read robots.txt for %s, assuming allowed", parsed.netloc)
                self._robot_parsers[robots_url] = None
                return True
            self._robot_parsers[robots_url] = rp

        parser = self._robot_parsers[robots_url]
        if parser is None:
            return True
        return parser.can_fetch("NotionCRMBot", url)

    def _brave_search(self, query: str) -> tuple[str, List[str]]:
        """Run a Brave Search API query. Returns formatted results and source URLs."""
        if not self.brave_api_key:
            return "", []

        try:
            response = httpx.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 5},
                headers={
                    "X-Subscription-Token": self.brave_api_key,
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as e:
            logger.warning("Brave search failed for '%s': %s", query, e)
            return "", []

        data = response.json()
        results = data.get("web", {}).get("results", [])
        if not results:
            return "", []

        lines = []
        urls: List[str] = []
        for r in results[:5]:
            title = r.get("title", "")
            description = r.get("description", "")
            url = r.get("url", "")
            lines.append(f"- {title}: {description} ({url})")
            if isinstance(url, str) and url.strip():
                urls.append(url.strip())

        return "\n".join(lines), urls

    @staticmethod
    def _truncate(text: str) -> str:
        """Truncate text to stay within token budget."""
        if len(text) <= _MAX_CONTENT_CHARS:
            return text
        return text[:_MAX_CONTENT_CHARS] + "\n\n[Content truncated for brevity]"
