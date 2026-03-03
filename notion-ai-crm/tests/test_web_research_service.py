"""
Tests for WebResearchService.

All tests use mocks — no live network calls.
"""

import pytest
from unittest.mock import patch, MagicMock

from services.web_research_service import WebResearchService, WebResearchResult


# --- URL Normalization ---

class TestNormalizeUrl:
    """Test URL normalization logic."""

    def test_adds_https_scheme(self):
        assert WebResearchService._normalize_url("example.com") == "https://example.com"

    def test_preserves_http_scheme(self):
        assert WebResearchService._normalize_url("http://example.com") == "http://example.com"

    def test_preserves_https_scheme(self):
        assert WebResearchService._normalize_url("https://example.com") == "https://example.com"

    def test_strips_trailing_slash(self):
        assert WebResearchService._normalize_url("https://example.com/") == "https://example.com"

    def test_strips_multiple_trailing_slashes(self):
        assert WebResearchService._normalize_url("example.com///") == "https://example.com"

    def test_strips_whitespace(self):
        assert WebResearchService._normalize_url("  example.com  ") == "https://example.com"

    def test_empty_url(self):
        assert WebResearchService._normalize_url("") == ""

    def test_url_with_path(self):
        assert WebResearchService._normalize_url("example.com/about") == "https://example.com/about"


# --- Content Extraction ---

class TestExtractText:
    """Test HTML content extraction."""

    def test_extracts_body_text(self):
        html = "<html><body><h1>Hello</h1><p>World</p></body></html>"
        text = WebResearchService._extract_text(html)
        assert "Hello" in text
        assert "World" in text

    def test_strips_script_tags(self):
        html = "<html><body><p>Real content</p><script>var x = 1;</script></body></html>"
        text = WebResearchService._extract_text(html)
        assert "Real content" in text
        assert "var x" not in text

    def test_strips_style_tags(self):
        html = "<html><body><p>Visible</p><style>.hidden{display:none}</style></body></html>"
        text = WebResearchService._extract_text(html)
        assert "Visible" in text
        assert "hidden" not in text

    def test_strips_nav_and_footer(self):
        html = """
        <html><body>
            <nav><a href="/">Home</a><a href="/about">About</a></nav>
            <main><p>Main content here</p></main>
            <footer><p>Copyright 2024</p></footer>
        </body></html>
        """
        text = WebResearchService._extract_text(html)
        assert "Main content" in text
        assert "Copyright" not in text

    def test_removes_short_lines(self):
        html = "<html><body><p>OK</p><p>This is a longer meaningful line</p></body></html>"
        text = WebResearchService._extract_text(html)
        # "OK" is only 2 chars, should be filtered out (len > 2 check)
        assert "OK" not in text
        assert "longer meaningful line" in text


# --- Robots.txt Compliance ---

class TestRobotsTxt:
    """Test robots.txt checking."""

    @patch("services.web_research_service.urllib.robotparser.RobotFileParser")
    def test_respects_disallow(self, mock_rp_class):
        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = False
        mock_rp_class.return_value = mock_rp

        service = WebResearchService(timeout=5, delay=0)
        allowed = service._is_allowed("https://example.com/secret")

        assert not allowed
        mock_rp.can_fetch.assert_called_once_with("NotionCRMBot", "https://example.com/secret")

    @patch("services.web_research_service.urllib.robotparser.RobotFileParser")
    def test_allows_when_permitted(self, mock_rp_class):
        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = True
        mock_rp_class.return_value = mock_rp

        service = WebResearchService(timeout=5, delay=0)
        allowed = service._is_allowed("https://example.com/public")

        assert allowed

    @patch("services.web_research_service.urllib.robotparser.RobotFileParser")
    def test_allows_when_robots_txt_unreadable(self, mock_rp_class):
        mock_rp = MagicMock()
        mock_rp.read.side_effect = Exception("Connection refused")
        mock_rp_class.return_value = mock_rp

        service = WebResearchService(timeout=5, delay=0)
        allowed = service._is_allowed("https://example.com/page")

        assert allowed  # Default to allowed when robots.txt is unreachable


# --- Graceful Failure ---

class TestGracefulFailure:
    """Test that errors don't crash the service."""

    @patch("services.web_research_service.httpx.get")
    @patch.object(WebResearchService, "_is_allowed", return_value=True)
    def test_timeout_returns_empty(self, _mock_allowed, mock_get):
        import httpx
        mock_get.side_effect = httpx.TimeoutException("Timed out")

        service = WebResearchService(timeout=5, delay=0)
        result = service._fetch_and_parse("https://example.com")

        assert result == ""

    @patch("services.web_research_service.httpx.get")
    @patch.object(WebResearchService, "_is_allowed", return_value=True)
    def test_connection_error_returns_empty(self, _mock_allowed, mock_get):
        import httpx
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        service = WebResearchService(timeout=5, delay=0)
        result = service._fetch_and_parse("https://example.com")

        assert result == ""

    @patch("services.web_research_service.httpx.get")
    @patch.object(WebResearchService, "_is_allowed", return_value=True)
    def test_http_error_returns_empty(self, _mock_allowed, mock_get):
        import httpx
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )
        mock_get.return_value = mock_response

        service = WebResearchService(timeout=5, delay=0)
        result = service._fetch_and_parse("https://example.com")

        assert result == ""

    @patch.object(WebResearchService, "_scrape_website", return_value="")
    def test_research_lead_returns_result_on_failure(self, _mock_scrape):
        service = WebResearchService(timeout=5, delay=0)
        result = service.research_lead({
            "company_name": "Test Corp",
            "website": "https://example.com",
        })

        assert isinstance(result, WebResearchResult)
        assert not result.has_content


# --- Cache Behavior ---

class TestCache:
    """Test in-memory caching."""

    @patch("services.web_research_service.httpx.get")
    @patch.object(WebResearchService, "_is_allowed", return_value=True)
    def test_cache_hit_skips_http(self, _mock_allowed, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Cached content here</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        service = WebResearchService(timeout=5, delay=0)

        # First call — makes HTTP request
        result1 = service._fetch_and_parse("https://example.com")
        assert "Cached content" in result1
        assert mock_get.call_count == 1

        # Second call — should use cache, no new HTTP request
        result2 = service._fetch_and_parse("https://example.com")
        assert result2 == result1
        assert mock_get.call_count == 1  # Still 1, no new request

    @patch("services.web_research_service.httpx.get")
    @patch.object(WebResearchService, "_is_allowed", return_value=True)
    def test_different_urls_not_cached(self, _mock_allowed, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Some content</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        service = WebResearchService(timeout=5, delay=0)

        service._fetch_and_parse("https://example.com")
        service._fetch_and_parse("https://other.com")
        assert mock_get.call_count == 2


# --- Content Truncation ---

class TestTruncation:
    """Test content truncation at character limit."""

    def test_short_content_not_truncated(self):
        text = "Short content"
        assert WebResearchService._truncate(text) == text

    def test_long_content_truncated(self):
        text = "x" * 15_000
        result = WebResearchService._truncate(text)
        assert len(result) < 15_000
        assert result.endswith("[Content truncated for brevity]")

    def test_exact_limit_not_truncated(self):
        text = "x" * 12_000
        result = WebResearchService._truncate(text)
        assert result == text
        assert "[truncated]" not in result


# --- WebResearchResult ---

class TestWebResearchResult:
    """Test the result data structure."""

    def test_has_content_with_website(self):
        result = WebResearchResult(website_content="Some content")
        assert result.has_content

    def test_has_content_with_search(self):
        result = WebResearchResult(search_results="Some results")
        assert result.has_content

    def test_no_content_when_empty(self):
        result = WebResearchResult()
        assert not result.has_content

    def test_to_prompt_section_with_both(self):
        result = WebResearchResult(
            website_content="Website text",
            search_results="Search text",
            source_urls=["https://example.com"],
        )
        section = result.to_prompt_section()
        assert "WEBSITE CONTENT:" in section
        assert "Website text" in section
        assert "SEARCH RESULTS:" in section
        assert "Search text" in section
        assert "SOURCES:" in section
        assert "https://example.com" in section

    def test_to_prompt_section_empty(self):
        result = WebResearchResult()
        section = result.to_prompt_section()
        assert "No web research data" in section


# --- Full Integration (mocked) ---

class TestResearchLead:
    """Test the research_lead method end-to-end with mocks."""

    @patch("services.web_research_service.httpx.get")
    @patch.object(WebResearchService, "_is_allowed", return_value=True)
    def test_scrapes_homepage_and_subpages(self, _mock_allowed, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Great company content</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        service = WebResearchService(timeout=5, delay=0, max_pages=2)
        result = service.research_lead({
            "company_name": "Test Corp",
            "website": "https://example.com",
        })

        assert result.has_content
        assert "Great company content" in result.website_content
        assert result.pages_fetched >= 1

    def test_no_website_still_works(self):
        service = WebResearchService(timeout=5, delay=0)
        result = service.research_lead({
            "company_name": "No Website Corp",
            "website": "",
        })

        assert isinstance(result, WebResearchResult)
        # No website, no brave key — should have no content but not crash
        assert not result.has_content


class TestBraveSearch:
    """Test Brave API response parsing."""

    @patch("services.web_research_service.httpx.get")
    def test_brave_search_returns_text_and_urls(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "T1", "description": "D1", "url": "https://a.example"},
                    {"title": "T2", "description": "D2", "url": "https://b.example"},
                ]
            }
        }
        mock_get.return_value = mock_response

        service = WebResearchService(timeout=5, delay=0, brave_api_key="test-key")
        text, urls = service._brave_search("acme")

        assert "T1" in text
        assert "T2" in text
        assert urls == ["https://a.example", "https://b.example"]


class TestWaterfallBehavior:
    """Test provider waterfall stop/continue logic."""

    @patch.object(WebResearchService, "_scrape_website", return_value="x" * 5000)
    @patch.object(WebResearchService, "_brave_search", return_value=("Brave details", ["https://b.example"]))
    def test_stops_after_threshold_when_run_all_disabled(self, mock_brave, _mock_scrape):
        service = WebResearchService(
            timeout=5,
            delay=0,
            brave_api_key="test-key",
            provider_order=["website", "brave"],
            target_chars=1000,
            run_all_providers=False,
        )
        result = service.research_lead(
            {"company_name": "Acme", "website": "https://example.com"}
        )

        mock_brave.assert_not_called()
        assert result.website_content
        assert result.search_results == ""
        assert any(
            item.get("provider") == "waterfall"
            and item.get("status") == "stop_threshold_reached"
            for item in result.provider_trace
        )

    @patch.object(WebResearchService, "_scrape_website", return_value="x" * 5000)
    @patch.object(WebResearchService, "_brave_search", return_value=("Brave details", ["https://b.example"]))
    def test_run_all_executes_all_providers(self, mock_brave, _mock_scrape):
        service = WebResearchService(
            timeout=5,
            delay=0,
            brave_api_key="test-key",
            provider_order=["website", "brave"],
            target_chars=1000,
            run_all_providers=True,
        )
        result = service.research_lead(
            {"company_name": "Acme", "website": "https://example.com"}
        )

        mock_brave.assert_called_once_with("Acme")
        assert "Brave details" in result.search_results

    def test_parse_provider_order_filters_unknown_and_duplicates(self):
        order = WebResearchService._parse_provider_order("website,unknown,brave,website")
        assert order == ["website", "brave"]
