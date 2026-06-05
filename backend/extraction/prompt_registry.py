"""
Prompt Registry
───────────────
Central registry for clause extraction prompt templates.

Each clause type has a dedicated module in backend/extraction/prompts/
exporting SYSTEM_PROMPT and USER_PROMPT_TEMPLATE.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptConfig:
    """Holds the system prompt and user prompt template for a clause type."""
    system_prompt: str
    user_prompt_template: str
    clause_type: str

    def format(self, clause_text: str) -> str:
        """Build the full prompt string ready to send to the LLM."""
        return (self.system_prompt + self.user_prompt_template).format(
            clause_text=clause_text
        )


_CLAUSE_TYPES = [
    "liability",
    "termination",
    "payment",
    "confidentiality",
    "ip",
    "governing_law",
]

_cache: dict[str, PromptConfig] = {}


def _load(clause_type: str) -> PromptConfig:
    """Import the prompt module for *clause_type* and build a PromptConfig."""
    from backend.extraction.prompts import (
        liability,
        termination,
        payment,
        confidentiality,
        ip,
        governing_law,
    )

    modules = {
        "liability": liability,
        "termination": termination,
        "payment": payment,
        "confidentiality": confidentiality,
        "ip": ip,
        "governing_law": governing_law,
    }

    mod = modules[clause_type]
    return PromptConfig(
        system_prompt=mod.SYSTEM_PROMPT,
        user_prompt_template=mod.USER_PROMPT_TEMPLATE,
        clause_type=clause_type,
    )


def get_prompt(clause_type: str) -> PromptConfig:
    """Return the PromptConfig for *clause_type*, raising ValueError if unknown."""
    if clause_type not in _CLAUSE_TYPES:
        raise ValueError(f"No extraction prompt for clause type: {clause_type}")
    if clause_type not in _cache:
        _cache[clause_type] = _load(clause_type)
    return _cache[clause_type]


def list_clause_types() -> list[str]:
    """Return all registered clause type names."""
    return list(_CLAUSE_TYPES)
