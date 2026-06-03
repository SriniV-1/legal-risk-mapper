"""
Tests for response caching on the /analyze endpoint.
"""
import time

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.cache import cache_clear, cache_stats, _text_hash

client = TestClient(app)

CONTRACT_TEXT = (
    "Company is not liable for any damages whatsoever. "
    "No warranty is provided under any circumstances. "
    "Client indemnifies Company against all claims."
)
DIFFERENT_TEXT = (
    "Either party may terminate this agreement with thirty days written notice. "
    "All obligations survive termination of this agreement."
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure each test starts with a clean cache."""
    cache_clear()
    yield
    cache_clear()


class TestCacheHitMiss:
    def test_same_input_returns_cache_hit(self):
        # First call — should be a MISS
        r1 = client.post("/analyze", json={"text": CONTRACT_TEXT})
        assert r1.status_code == 200
        assert r1.headers.get("X-Cache") == "MISS"

        # Second call with identical text — should be a HIT
        r2 = client.post("/analyze", json={"text": CONTRACT_TEXT})
        assert r2.status_code == 200
        assert r2.headers.get("X-Cache") == "HIT"

        # Payloads should be identical
        assert r1.json()["total_risks"] == r2.json()["total_risks"]
        assert r1.json()["risks"] == r2.json()["risks"]

    def test_different_input_is_cache_miss(self):
        r1 = client.post("/analyze", json={"text": CONTRACT_TEXT})
        assert r1.headers.get("X-Cache") == "MISS"

        r2 = client.post("/analyze", json={"text": DIFFERENT_TEXT})
        assert r2.headers.get("X-Cache") == "MISS"

    def test_cached_call_is_faster(self):
        # Prime the cache
        client.post("/analyze", json={"text": CONTRACT_TEXT})

        start = time.perf_counter()
        client.post("/analyze", json={"text": CONTRACT_TEXT})
        cached_duration = time.perf_counter() - start

        # Cached call should be very fast (under 100 ms typically).
        # We use a generous threshold to avoid flaky CI.
        assert cached_duration < 1.0


class TestCacheClearEndpoint:
    def test_cache_clear_returns_evicted_count(self):
        # Insert two entries
        client.post("/analyze", json={"text": CONTRACT_TEXT})
        client.post("/analyze", json={"text": DIFFERENT_TEXT})

        r = client.post("/cache/clear")
        assert r.status_code == 200
        data = r.json()
        assert data["evicted"] == 2

    def test_after_clear_next_call_is_miss(self):
        client.post("/analyze", json={"text": CONTRACT_TEXT})
        client.post("/cache/clear")

        r = client.post("/analyze", json={"text": CONTRACT_TEXT})
        assert r.headers.get("X-Cache") == "MISS"


class TestCacheStatsInHealth:
    def test_health_includes_cache_stats(self):
        # Make one call to populate stats
        client.post("/analyze", json={"text": CONTRACT_TEXT})

        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "cache" in data
        assert "hits" in data["cache"]
        assert "misses" in data["cache"]
        assert "size" in data["cache"]
        assert data["cache"]["size"] >= 1


class TestCacheServiceUnit:
    def test_text_hash_is_deterministic(self):
        h1 = _text_hash("hello world")
        h2 = _text_hash("hello world")
        assert h1 == h2

    def test_text_hash_normalizes_whitespace(self):
        h1 = _text_hash("hello   world")
        h2 = _text_hash("hello world")
        assert h1 == h2

    def test_cache_stats_after_operations(self):
        from backend.services.cache import cache_get, cache_set
        cache_set("abc123", {"result": "test"})
        cache_get("abc123")  # hit
        cache_get("missing")  # miss

        stats = cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
