"""
Tests for the extraction pipeline — prompt templates, schema mapping, extractor registry.
Does NOT require Ollama (tests structure, not LLM inference).
"""
import pytest

from backend.extraction.extractor import (
    extract_liability, extract_termination, extract_payment,
    extract_confidentiality, extract_ip, extract_governing_law,
)
from backend.extraction.prompt_registry import get_prompt, list_clause_types
from backend.extraction.schemas import EXTRACTION_SCHEMAS


class TestExtractorRegistry:
    """Every clause type has a prompt and schema."""

    def test_all_types_have_prompts(self):
        for clause_type in EXTRACTION_SCHEMAS:
            cfg = get_prompt(clause_type)
            assert cfg is not None, f"Missing prompt for {clause_type}"

    def test_prompts_are_non_empty(self):
        for clause_type in list_clause_types():
            cfg = get_prompt(clause_type)
            full_prompt = cfg.system_prompt + cfg.user_prompt_template
            assert len(full_prompt) > 100, f"Prompt for {clause_type} is suspiciously short"

    def test_prompts_mention_json(self):
        for clause_type in list_clause_types():
            cfg = get_prompt(clause_type)
            full_prompt = cfg.system_prompt + cfg.user_prompt_template
            assert "json" in full_prompt.lower() or "JSON" in full_prompt, (
                f"Prompt for {clause_type} should instruct JSON output"
            )

    def test_prompts_mention_source_text(self):
        for clause_type in list_clause_types():
            cfg = get_prompt(clause_type)
            full_prompt = cfg.system_prompt + cfg.user_prompt_template
            assert "source_text" in full_prompt.lower() or "source text" in full_prompt.lower(), (
                f"Prompt for {clause_type} should require source_text grounding"
            )


class TestConvenienceWrappers:
    """Each clause type has a convenience function."""

    def test_wrappers_exist(self):
        assert callable(extract_liability)
        assert callable(extract_termination)
        assert callable(extract_payment)
        assert callable(extract_confidentiality)
        assert callable(extract_ip)
        assert callable(extract_governing_law)


class TestBenchmarkingIntegration:
    """Aggregator field registry covers all clause types."""

    def test_field_registry_complete(self):
        from backend.benchmarking.aggregator import _FIELD_REGISTRY
        for clause_type in EXTRACTION_SCHEMAS:
            assert clause_type in _FIELD_REGISTRY, (
                f"Missing field registry for {clause_type}"
            )

    def test_field_registry_has_bool_and_cat(self):
        from backend.benchmarking.aggregator import _FIELD_REGISTRY
        for clause_type, (bools, cats) in _FIELD_REGISTRY.items():
            assert isinstance(bools, (list, tuple)), f"{clause_type} bool_fields not a list"
            assert isinstance(cats, (list, tuple)), f"{clause_type} cat_fields not a list"
            assert len(bools) > 0, f"{clause_type} has no boolean fields"


class TestBenchmarkerRouting:
    """Benchmarker imports extractors for all clause types."""

    def test_all_extractors_importable(self):
        """Verify that benchmarker imports all 6 extractor functions."""
        import backend.benchmarking.benchmarker as bm
        for clause_type in EXTRACTION_SCHEMAS:
            fn_name = f"extract_{clause_type}"
            assert hasattr(bm, fn_name), (
                f"Benchmarker missing import for {fn_name}"
            )
