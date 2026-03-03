# CRM Agent — MCP Tools for Lead Analysis

This project provides CRM lead analysis as MCP tools. You ARE the LLM — the tools give you prompts to reason over and validators to clean up your answers.

## Quick Start: Analyzing a Lead

1. **Fetch lead data** from Notion using the Notion MCP (notion-search, notion-fetch)
2. **Run `detect_signals`** with the lead's notes — instant results, no LLM needed
3. **Run `score_icp_fit`** — gives you a scoring prompt with a 5-dimension rubric
4. **Reason over the ICP prompt** yourself, produce JSON matching the expected format
5. **Run `parse_icp_result`** with your JSON — validates and clamps scores
6. **Run `determine_priority`** with ICP score + signal results — often deterministic
7. If `needs_llm=True`, reason over the priority prompt, then call `parse_priority_result`
8. **Run `recommend_action`** with priority result — often deterministic
9. If `needs_llm=True`, reason over the action prompt, then call `parse_action_result`
10. **Run `get_config`** to get Notion property names, then write results back with `notion-update-page`

Or use **`run_full_analysis`** to get signals + all prompts in one call.

## Tool Types

| Tool | Type | LLM Needed? |
|------|------|-------------|
| `detect_signals` | Deterministic | No — runs regex patterns server-side |
| `determine_priority` | Hybrid | Sometimes — clear cases are deterministic |
| `recommend_action` | Hybrid | Sometimes — clear cases are deterministic |
| `score_icp_fit` | Prompt generator | Yes — you reason over the rubric |
| `generate_research_prompt` | Prompt generator | Yes — you produce prose brief |
| `parse_icp_result` | Validator | No — validates your JSON |
| `parse_priority_result` | Validator | No — validates + applies signal boost |
| `parse_action_result` | Validator | No — validates action/confidence |
| `get_config` | Info | No |
| `run_full_analysis` | Convenience | Partial — runs deterministic, returns prompts |

## Notion Property Mapping

Call `get_config` to see the exact Notion property names configured for this user's database. The output includes both input properties (what to read) and output properties (what to write back).

## ICP Scoring Format

When reasoning over the ICP prompt, produce this JSON:
```json
{
  "icp_score": 0-100,
  "dimension_scores": {
    "company_size_stage": 0-20,
    "market_industry_fit": 0-20,
    "budget_buying_signals": 0-20,
    "engagement_accessibility": 0-20,
    "strategic_alignment": 0-20
  },
  "confidence_score": 0-100,
  "icp_reasoning": "2-4 sentences",
  "data_gaps": "missing info or empty string"
}
```

## Priority Format (for edge cases)
```json
{
  "priority_tier": "high" | "medium" | "low",
  "priority_reasoning": "1-2 sentences"
}
```

## Action Format (for edge cases)
```json
{
  "next_action": "outreach_now|reengage|nurture|enrich_data|hold",
  "action_reasoning": "1-2 sentence rationale",
  "action_confidence": "high|medium|low"
}
```
