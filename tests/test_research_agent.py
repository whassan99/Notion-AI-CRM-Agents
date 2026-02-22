from agents.research_agent import ResearchAgent
from services.web_research_service import WebResearchResult


class _StubClaude:
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return "Research brief body"

    def generate_structured(self, prompt: str, system_prompt: str = "") -> str:
        return "Research brief body"


class _StubWebResearch:
    def __init__(self, result: WebResearchResult):
        self.result = result

    def research_lead(self, lead):
        return self.result


def test_research_agent_adds_sources_section_and_citations():
    web_result = WebResearchResult(
        website_content="Website facts",
        search_results="Search facts",
        pages_fetched=2,
        source_urls=["https://example.com", "https://news.example/item"],
    )
    agent = ResearchAgent(_StubClaude(), web_research_service=_StubWebResearch(web_result))
    result = agent.run(
        {
            "company_name": "Acme",
            "website": "https://example.com",
            "notes": "Strong buying signal from VP Sales.",
        }
    )

    assert "## SOURCES" in result["research_brief"]
    assert "https://example.com" in result["research_brief"]
    assert result["research_source_count"] >= 2
    assert "CRM Notes" in result["research_citations"]


def test_research_confidence_high_with_rich_evidence():
    web_result = WebResearchResult(
        website_content="Website facts",
        search_results="Search facts",
        pages_fetched=3,
        source_urls=["https://example.com"],
    )
    agent = ResearchAgent(_StubClaude(), web_research_service=_StubWebResearch(web_result))
    result = agent.run(
        {
            "company_name": "Acme",
            "website": "https://example.com",
            "notes": "x" * 140,
        }
    )
    assert result["research_confidence"] == "high"


def test_research_confidence_low_with_minimal_data():
    agent = ResearchAgent(_StubClaude(), web_research_service=None)
    result = agent.run(
        {
            "company_name": "",
            "website": "",
            "notes": "",
        }
    )
    assert result["research_confidence"] == "low"
