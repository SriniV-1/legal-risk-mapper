"""
LLM-Based Clause Extractor
───────────────────────────
Extracts structured fields from contract clauses using a pluggable LLM backend.
Prompts are loaded from backend.extraction.prompts via the prompt registry.

LLM routing: GROQ_API_KEY → Groq (llama-3.3-70b-versatile), else Ollama local.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional

import requests
from pydantic import BaseModel, ValidationError

from backend.extraction.schemas import (
    EXTRACTION_SCHEMAS, LiabilityExtraction, TerminationExtraction,
    PaymentExtraction, ConfidentialityExtraction, IPExtraction, GoverningLawExtraction,
)
from backend.extraction.prompt_registry import get_prompt
from backend.services.circuit_breaker import groq_breaker, CircuitOpenError

log = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = os.environ.get("LRM_EXTRACTION_MODEL", "llama3.1:8b")

# ── LLM clients ─────────────────────────────────────────────────────────────


def _call_ollama(
    prompt: str, model: str = DEFAULT_MODEL,
    temperature: float = 0.1, max_tokens: int = 2000,
) -> str:
    """Call Ollama API and return the response text."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def _call_groq(
    prompt: str, model: str = "llama-3.3-70b-versatile", max_tokens: int = 2000,
) -> str:
    """Call Groq API and return the response text. Requires GROQ_API_KEY."""
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set")

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens, temperature=0,
    )
    return response.choices[0].message.content


def _call_llm(
    prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = 2000,
) -> str:
    """Route to Groq (if GROQ_API_KEY set) or Ollama (fallback)."""
    if os.environ.get("GROQ_API_KEY"):
        groq_model = "llama-3.3-70b-versatile" if model == DEFAULT_MODEL else model
        return _call_groq(prompt, model=groq_model, max_tokens=max_tokens)
    return _call_ollama(prompt, model=model, max_tokens=max_tokens)


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling common formatting issues."""
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    brace_start = text.find("{")
    if brace_start >= 0:
        depth = 0
        for i, ch in enumerate(text[brace_start:], brace_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start : i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"Could not extract valid JSON from response: {text[:200]}...")


# ── Extraction ───────────────────────────────────────────────────────────────

def extract_clause(
    clause_text: str, clause_type: str = "liability",
    model: str = DEFAULT_MODEL, max_retries: int = 3,
) -> Optional[BaseModel]:
    """Extract structured fields from a clause using the LLM.

    Returns a Pydantic model instance with extracted fields, or None on failure.
    """
    prompt_config = get_prompt(clause_type)
    schema_cls = EXTRACTION_SCHEMAS[clause_type]
    prompt = prompt_config.format(clause_text=clause_text)

    for attempt in range(max_retries):
        try:
            start = time.monotonic()
            raw_response = groq_breaker.call(_call_llm, prompt, model=model)
            elapsed = time.monotonic() - start
            data = _extract_json(raw_response)
            result = schema_cls.model_validate(data)
            log.debug("Extraction succeeded (attempt %d, %.1fs): %s",
                      attempt + 1, elapsed, clause_type)
            return result

        except CircuitOpenError:
            log.warning("Circuit breaker OPEN — skipping extraction for %s", clause_type)
            return None

        except (requests.RequestException, ValueError, ValidationError) as e:
            log.warning("Extraction attempt %d/%d failed for %s: %s",
                        attempt + 1, max_retries, clause_type, e)
            if attempt < max_retries - 1:
                time.sleep(1)

    log.error("Extraction failed after %d attempts for %s", max_retries, clause_type)
    return None


# ── Convenience wrappers ─────────────────────────────────────────────────────

def extract_liability(clause_text: str, model: str = DEFAULT_MODEL) -> Optional[LiabilityExtraction]:
    return extract_clause(clause_text, clause_type="liability", model=model)

def extract_termination(clause_text: str, model: str = DEFAULT_MODEL) -> Optional[TerminationExtraction]:
    return extract_clause(clause_text, clause_type="termination", model=model)

def extract_payment(clause_text: str, model: str = DEFAULT_MODEL) -> Optional[PaymentExtraction]:
    return extract_clause(clause_text, clause_type="payment", model=model)

def extract_confidentiality(clause_text: str, model: str = DEFAULT_MODEL) -> Optional[ConfidentialityExtraction]:
    return extract_clause(clause_text, clause_type="confidentiality", model=model)

def extract_ip(clause_text: str, model: str = DEFAULT_MODEL) -> Optional[IPExtraction]:
    return extract_clause(clause_text, clause_type="ip", model=model)

def extract_governing_law(clause_text: str, model: str = DEFAULT_MODEL) -> Optional[GoverningLawExtraction]:
    return extract_clause(clause_text, clause_type="governing_law", model=model)


# ── Batch extraction ─────────────────────────────────────────────────────────

def batch_extract(
    clauses: list[dict], clause_type: str = "liability", model: str = DEFAULT_MODEL,
) -> list[dict]:
    """Extract structured data from a list of clause dicts.
    Each dict must have 'text' and optionally 'contract_id', 'chunk_id'.
    """
    results = []
    total = len(clauses)

    for i, clause in enumerate(clauses):
        extraction = extract_clause(clause["text"], clause_type=clause_type, model=model)
        result = {
            "contract_id": clause.get("contract_id", ""),
            "chunk_id": clause.get("id", clause.get("chunk_id")),
            "clause_type": clause_type,
            "success": extraction is not None,
            "extracted_data": extraction.model_dump() if extraction else None,
        }
        results.append(result)

        if (i + 1) % 10 == 0 or i == total - 1:
            success_count = sum(1 for r in results if r["success"])
            log.info("Batch extraction: %d/%d done (%d succeeded)",
                     i + 1, total, success_count)

    return results
