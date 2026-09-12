"""
Tests for input size limits (backend/services/limits.py) and the endpoints
that enforce or publish them.

The limits exist because the LLM routes run on Groq's free tier, where the
binding constraint on a single request is 8,000 tokens/minute counting prompt
plus completion. Blowing it returns a 429 halfway through an analysis, so
oversized input is rejected up front with 413 and an explanatory message.

Covers:
  - word counting and token estimation
  - ok / warn / over classification for both pipelines
  - enforce() raising 413 only past the hard cap
  - GET /limits shape (the frontend reads its disclaimer numbers from it)
  - 413 on /analyze, /analyze/upload, /benchmark and /redline
  - GET /warmup idempotency
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import limits as L

client = TestClient(app)


def words(n: int) -> str:
    """n whitespace-separated words of plausible contract prose."""
    return " ".join(["indemnification"] * n)


class TestCounting:
    def test_count_words_matches_whitespace_split(self):
        assert L.count_words("one two three") == 3
        assert L.count_words("  leading and trailing  ") == 3
        assert L.count_words("") == 0

    def test_estimate_tokens_uses_legal_prose_ratio(self):
        # 1.4 tokens/word — denser than plain English.
        assert L.estimate_tokens(words(1000)) == 1400


class TestClassification:
    @pytest.mark.parametrize("mode", ["llm", "local"])
    def test_small_input_is_ok(self, mode):
        r = L.check_size(words(50), mode)
        assert r["ok"] is True
        assert r["level"] == "ok"
        assert r["message"] is None

    def test_llm_warn_band(self):
        r = L.check_size(words(L.LLM_WARN_WORDS + 1), "llm")
        assert r["ok"] is True          # advisory only — the request still runs
        assert r["level"] == "warn"
        assert "tokens" in r["message"]

    def test_llm_over_cap(self):
        r = L.check_size(words(L.LLM_MAX_WORDS + 1), "llm")
        assert r["ok"] is False
        assert r["level"] == "over"
        assert f"{L.LLM_MAX_WORDS:,}" in r["message"]

    def test_boundary_at_max_is_allowed(self):
        """The cap is inclusive: exactly max_words must not be rejected."""
        assert L.check_size(words(L.LLM_MAX_WORDS), "llm")["ok"] is True
        assert L.check_size(words(L.LOCAL_MAX_WORDS), "local")["ok"] is True

    def test_local_budget_is_far_larger_than_llm(self):
        """Local analysis has no third-party quota, so it takes whole documents."""
        assert L.LOCAL_MAX_WORDS > L.LLM_MAX_WORDS
        assert L.check_size(words(L.LLM_MAX_WORDS + 500), "local")["ok"] is True

    def test_local_over_cap(self):
        r = L.check_size(words(L.LOCAL_MAX_WORDS + 1), "local")
        assert r["ok"] is False
        assert "risk analysis" in r["message"]


class TestEnforce:
    def test_enforce_passes_under_cap(self):
        assert L.enforce(words(10), "llm") is None

    def test_enforce_raises_413_over_cap(self):
        with pytest.raises(HTTPException) as exc:
            L.enforce(words(L.LLM_MAX_WORDS + 1), "llm")
        assert exc.value.status_code == 413
        assert "benchmarking" in exc.value.detail.lower()

    def test_enforce_warn_band_does_not_raise(self):
        assert L.enforce(words(L.LLM_WARN_WORDS + 1), "llm") is None


class TestLimitsEndpoint:
    def test_limits_endpoint_shape(self):
        """The frontend renders its disclaimer from these exact keys."""
        r = client.get("/limits")
        assert r.status_code == 200
        data = r.json()
        for mode in ("llm", "local"):
            assert data[mode]["warn_words"] > 0
            assert data[mode]["max_words"] >= data[mode]["warn_words"]
        assert data["tokens_per_word"] > 1
        tier = data["free_tier"]
        assert tier["model"]
        assert tier["tokens_per_minute"] > 0
        assert tier["requests_per_day"] > 0

    def test_limits_match_the_enforced_constants(self):
        """/limits is the single source of truth — it must not drift."""
        data = client.get("/limits").json()
        assert data["llm"]["max_words"] == L.LLM_MAX_WORDS
        assert data["local"]["max_words"] == L.LOCAL_MAX_WORDS


class TestEndpointEnforcement:
    def test_analyze_rejects_oversized_text(self):
        r = client.post("/analyze", json={"text": words(L.LOCAL_MAX_WORDS + 1)})
        assert r.status_code == 413
        assert f"{L.LOCAL_MAX_WORDS:,}" in r.json()["detail"]

    def test_analyze_upload_rejects_oversized_file(self):
        """Under the 10 MB byte cap but far over the word budget."""
        payload = words(L.LOCAL_MAX_WORDS + 1).encode()
        assert len(payload) < 10 * 1024 * 1024
        r = client.post(
            "/analyze/upload",
            files={"file": ("long.txt", payload, "text/plain")},
        )
        assert r.status_code == 413

    def test_benchmark_rejects_oversized_text(self):
        """413 must fire before any Groq or corpus call is attempted."""
        r = client.post("/benchmark", json={"text": words(L.LLM_MAX_WORDS + 1)})
        assert r.status_code == 413
        assert "free tier" in r.json()["detail"].lower()

    def test_redline_rejects_oversized_text(self):
        r = client.post("/redline", json={"text": words(L.LLM_MAX_WORDS + 1)})
        assert r.status_code == 413

    def test_benchmark_under_cap_is_not_rejected_for_size(self):
        """A normal clause must get past the size gate (corpus may still be down)."""
        r = client.post("/benchmark", json={
            "text": "Company's total liability shall not exceed the fees paid in the "
                    "twelve months preceding the claim, excluding gross negligence.",
        })
        assert r.status_code != 413


class TestWarmup:
    def test_warmup_reports_warm(self):
        r = client.get("/warmup")
        assert r.status_code == 200
        assert r.json()["warm"] is True

    def test_warmup_is_idempotent_and_cheap_once_warm(self):
        client.get("/warmup")
        r = client.get("/warmup")
        assert r.status_code == 200
        data = r.json()
        assert data["warm"] is True
        assert data["cold_start"] is False
