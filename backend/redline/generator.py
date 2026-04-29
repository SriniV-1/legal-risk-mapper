"""
Redline Generator
─────────────────
Generates grounded contract edit suggestions using LLM + market benchmark data.
Each suggestion cites specific market statistics and real SEC filings.

Uses Ollama/Llama 3.1 8B by default (free, local).
Can be upgraded to Anthropic Sonnet for higher quality.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from backend.benchmarking.schemas import BenchmarkResult
from backend.extraction.extractor import _call_ollama, _extract_json, DEFAULT_MODEL
from backend.redline.schemas import RedlineResult, RedlineSuggestion

log = logging.getLogger(__name__)


def _build_market_context(benchmark: BenchmarkResult) -> str:
    """Format benchmark results into a readable market context block for the prompt."""
    lines = []
    lines.append("MARKET DATA (from real SEC EDGAR filings):")
    lines.append(f"  Sample size: {benchmark.sample_size} similar liability clauses")
    lines.append("")

    # Field distributions
    lines.append("  Field distributions in the market:")
    for field_name, dist in benchmark.field_distributions.items():
        if dist.total > 0 and not dist.value_counts:
            lines.append(f"    - {field_name}: {dist.true_pct:.0f}% of clauses have this ({dist.true_count}/{dist.total})")
        elif dist.value_counts:
            lines.append(f"    - {field_name}: {dist.value_counts}")

    # User percentiles
    if benchmark.user_percentiles:
        lines.append("")
        lines.append("  How the user's clause compares:")
        for field_name, pct in benchmark.user_percentiles.items():
            if pct is not None:
                user_val = None
                if benchmark.user_extraction:
                    if field_name == "has_cap":
                        user_val = benchmark.user_extraction.get("liability_cap", {}).get("has_cap")
                    elif field_name == "consequential_excluded":
                        user_val = benchmark.user_extraction.get("consequential_damages", {}).get("excluded")
                    else:
                        user_val = benchmark.user_extraction.get(field_name)
                lines.append(f"    - {field_name}: user={user_val}, market={pct:.0f}th percentile")

    # Cited examples
    if benchmark.cited_examples:
        lines.append("")
        lines.append("  Real-world examples from SEC filings:")
        for i, ex in enumerate(benchmark.cited_examples[:3], 1):
            company = ex.company or ex.contract_id
            lines.append(f"    Example {i} ({company}):")
            lines.append(f"      \"{ex.text_snippet[:200]}...\"")
            if ex.extracted_data:
                cap = ex.extracted_data.get("liability_cap", {})
                if cap.get("has_cap"):
                    lines.append(f"      Cap: {cap.get('cap_amount', 'present')}")

    return "\n".join(lines)


_REDLINE_PROMPT = """\
You are a transactional attorney reviewing a contract clause. Using the market benchmark data below, suggest specific edits to strengthen the clause for the client.

CRITICAL RULES:
1. Every suggestion MUST be grounded in the market data. Do NOT suggest edits that aren't supported by market statistics.
2. "original_text" must be an EXACT quote from the user's clause.
3. "proposed_text" must be a concrete replacement, not a vague instruction.
4. "justification" must cite a specific market statistic (e.g., "72% of similar clauses include...").
5. Only suggest 2-4 high-impact edits. Do not over-edit.
6. If the clause already aligns with market norms, say so and suggest fewer edits.
7. Respond with ONLY valid JSON. No markdown, no explanation outside JSON.

USER'S CLAUSE:
{clause_text}

USER'S CLAUSE EXTRACTION:
{user_extraction}

{market_context}

Respond with a JSON object:
{{
  "suggestions": [
    {{
      "original_text": "exact quote from the clause",
      "proposed_text": "suggested replacement text",
      "justification": "why this change is recommended, citing market data",
      "market_citation": "specific stat, e.g. '72% of similar clauses...'",
      "risk_addressed": "what risk this edit addresses",
      "priority": "high" | "medium" | "low"
    }}
  ],
  "summary": "1-2 sentence summary of key recommendations"
}}

JSON:"""


def generate_redlines(
    clause_text: str,
    benchmark: BenchmarkResult,
    model: str = DEFAULT_MODEL,
) -> RedlineResult:
    """
    Generate grounded redline suggestions for a clause.

    Args:
        clause_text: The user's original clause text.
        benchmark: Market benchmark result from the benchmarking pipeline.
        model: LLM model to use.

    Returns:
        RedlineResult with edit suggestions and justifications.
    """
    log.info("Generating redlines for %s clause (%d chars)", benchmark.clause_type, len(clause_text))

    market_context = _build_market_context(benchmark)
    user_ext_str = json.dumps(benchmark.user_extraction, indent=2) if benchmark.user_extraction else "Extraction failed"

    prompt = _REDLINE_PROMPT.format(
        clause_text=clause_text,
        user_extraction=user_ext_str,
        market_context=market_context,
    )

    try:
        raw_response = _call_ollama(prompt, model=model, max_tokens=3000)
        data = _extract_json(raw_response)
    except Exception as e:
        log.error("Redline generation failed: %s", e)
        return RedlineResult(
            clause_type=benchmark.clause_type,
            original_clause=clause_text,
            summary="Redline generation failed. Please try again.",
            model_used=model,
        )

    # Parse suggestions (coerce None → "" for all string fields)
    suggestions = []
    for s in data.get("suggestions", []):
        if not isinstance(s, dict):
            continue
        original = s.get("original_text") or ""
        proposed = s.get("proposed_text") or ""
        if not original and not proposed:
            continue
        suggestions.append(RedlineSuggestion(
            original_text=original,
            proposed_text=proposed,
            justification=s.get("justification") or "",
            market_citation=s.get("market_citation") or "",
            risk_addressed=s.get("risk_addressed") or "",
            priority=s.get("priority") or "medium",
        ))

    result = RedlineResult(
        clause_type=benchmark.clause_type,
        original_clause=clause_text,
        suggestions=suggestions,
        summary=data.get("summary", ""),
        model_used=model,
    )

    log.info("Generated %d redline suggestions", len(suggestions))
    return result
