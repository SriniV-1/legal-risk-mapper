"""
Tests for the `layers` parameter in analyze_risks() — ablation study support.

Verifies that each pipeline layer can be activated independently and that
the parameter is backward compatible (default = all layers).
"""
import pytest

from backend.services.risk_analyzer import analyze_risks, VALID_LAYERS


# ── Shared test text ──────────────────────────────────────────────────────────
# Chosen to trigger regex rules reliably (indemnify, GDPR, auto-renewal,
# sole discretion) regardless of ML / semantic model availability.
_MIXED_TEXT = (
    "The Client shall indemnify and hold harmless the Company from all claims. "
    "All parties must comply with GDPR regulations. "
    "This agreement automatically renews each year. "
    "Pricing may change at the Company's sole discretion."
)


class TestLayersParameter:
    """Core layer-selection behavior."""

    def test_default_runs_all_layers(self):
        """Calling without `layers` activates the full production pipeline.

        In production mode (layers=None), ML is preferred over regex (not
        both simultaneously), whereas explicit layers=["regex","ml",...]
        runs both.  We just verify the default returns results and doesn't
        break.
        """
        default = analyze_risks(_MIXED_TEXT)
        assert isinstance(default, list)
        assert len(default) > 0

    def test_regex_only_produces_regex_sources(self):
        """With layers=['regex'], every detection must come from the regex layer."""
        risks = analyze_risks(_MIXED_TEXT, layers=["regex"])
        assert len(risks) > 0, "Regex should find risks in the test text"
        for r in risks:
            sources = r.get("sources", [])
            assert "regex" in sources, f"Expected regex source, got {sources}"
            assert "ml_classifier" not in sources
            assert "semantic" not in sources

    def test_ml_only_produces_ml_sources(self):
        """With layers=['ml'], detections should come from the ML classifier.

        If the ML model is not available, the function should return an
        empty list (no fallback to regex when regex layer is disabled).
        """
        risks = analyze_risks(_MIXED_TEXT, layers=["ml"])
        for r in risks:
            sources = r.get("sources", [])
            assert "ml_classifier" in sources, f"Expected ml_classifier source, got {sources}"
            assert "regex" not in sources

    def test_semantic_only_produces_semantic_sources(self):
        """With layers=['semantic'], detections come from semantic similarity.

        If embeddings are unavailable, returns [].
        """
        risks = analyze_risks(_MIXED_TEXT, layers=["semantic"])
        for r in risks:
            sources = r.get("sources", [])
            assert "semantic" in sources, f"Expected semantic source, got {sources}"
            assert "regex" not in sources
            assert "ml_classifier" not in sources

    def test_regex_only_no_semantic_fields(self):
        """Regex-only results should not carry semantic-specific metadata."""
        risks = analyze_risks(_MIXED_TEXT, layers=["regex"])
        for r in risks:
            # semantic_similarity should be absent or None
            assert r.get("semantic_similarity") is None or "semantic_similarity" not in r

    def test_invalid_layer_raises(self):
        """Unknown layer names should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid layer"):
            analyze_risks(_MIXED_TEXT, layers=["regex", "bogus_layer"])

    def test_empty_layers_list_returns_empty(self):
        """An empty layers list means nothing runs — should return []."""
        risks = analyze_risks(_MIXED_TEXT, layers=[])
        assert risks == []

    def test_regex_plus_ml_no_semantic(self):
        """regex+ml should not include any semantic-only detections."""
        risks = analyze_risks(_MIXED_TEXT, layers=["regex", "ml"])
        for r in risks:
            sources = r.get("sources", [])
            assert "semantic" not in sources, (
                f"semantic should not appear in sources for regex+ml config: {sources}"
            )

    def test_backward_compatible_no_layers_arg(self):
        """Existing callers that don't pass `layers` must not break."""
        # This call must not raise
        risks = analyze_risks(_MIXED_TEXT)
        assert isinstance(risks, list)

    def test_all_valid_layers_accepted(self):
        """Every name in VALID_LAYERS is accepted individually."""
        for layer in VALID_LAYERS:
            # Should not raise
            analyze_risks("This is a test clause with no risk.", layers=[layer])
