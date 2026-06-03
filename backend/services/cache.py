"""
In-memory LRU cache with TTL for contract analysis results.

Key:   SHA-256 hash of cleaned input text
Value: serialized analysis result (dict)
TTL:   1 hour
Max:   100 entries
Thread-safe via threading.Lock.
"""
import hashlib
import threading
import time
from collections import OrderedDict
from typing import Optional

_MAX_ENTRIES = 100
_TTL_SECONDS = 3600  # 1 hour

_lock = threading.Lock()
_cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()  # key -> (expires_at, result)
_hits = 0
_misses = 0


def _text_hash(text: str) -> str:
    """Return SHA-256 hex digest of whitespace-normalized text."""
    cleaned = " ".join(text.split())
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def _evict_expired() -> None:
    """Remove expired entries (caller must hold _lock)."""
    now = time.time()
    expired = [k for k, (exp, _) in _cache.items() if exp <= now]
    for k in expired:
        del _cache[k]


def cache_get(text_hash: str) -> Optional[dict]:
    """Look up a cached result by text hash. Returns None on miss."""
    global _hits, _misses
    with _lock:
        _evict_expired()
        entry = _cache.get(text_hash)
        if entry is None:
            _misses += 1
            return None
        expires_at, result = entry
        if expires_at <= time.time():
            del _cache[text_hash]
            _misses += 1
            return None
        # Move to end (most-recently used)
        _cache.move_to_end(text_hash)
        _hits += 1
        return result


def cache_set(text_hash: str, result: dict) -> None:
    """Store an analysis result in the cache."""
    with _lock:
        _evict_expired()
        # If already present, remove so we can re-insert at the end
        if text_hash in _cache:
            del _cache[text_hash]
        # Evict oldest if at capacity
        while len(_cache) >= _MAX_ENTRIES:
            _cache.popitem(last=False)
        _cache[text_hash] = (time.time() + _TTL_SECONDS, result)


def cache_clear() -> int:
    """Clear all entries. Returns the number of evicted entries."""
    global _hits, _misses
    with _lock:
        count = len(_cache)
        _cache.clear()
        _hits = 0
        _misses = 0
        return count


def cache_stats() -> dict:
    """Return cache statistics: hits, misses, size, hit_rate."""
    with _lock:
        _evict_expired()
        total = _hits + _misses
        return {
            "hits": _hits,
            "misses": _misses,
            "size": len(_cache),
            "max_size": _MAX_ENTRIES,
            "ttl_seconds": _TTL_SECONDS,
            "hit_rate": round(_hits / total, 4) if total > 0 else 0.0,
        }
