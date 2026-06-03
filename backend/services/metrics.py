"""
Prometheus metrics for the ALRM backend.

Exposes custom counters and histograms for monitoring analysis performance,
cache behaviour, and risk detection patterns.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Sequence

from prometheus_client import Counter, Histogram, generate_latest, REGISTRY

if TYPE_CHECKING:
    from backend.models.schemas import RiskItem

# ---------------------------------------------------------------------------
# Custom metrics
# ---------------------------------------------------------------------------

analysis_duration = Histogram(
    "alrm_analysis_duration_seconds",
    "Latency of the /analyze endpoint in seconds",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

analysis_requests = Counter(
    "alrm_analysis_requests_total",
    "Total analysis requests partitioned by outcome",
    ["status"],
)

risk_detections = Counter(
    "alrm_risk_detections_total",
    "Total risk detections partitioned by category and severity",
    ["category", "severity"],
)

cache_hits = Counter(
    "alrm_cache_hits_total",
    "Total cache hits for analysis requests",
)

cache_misses = Counter(
    "alrm_cache_misses_total",
    "Total cache misses for analysis requests",
)

clauses_processed = Counter(
    "alrm_clauses_processed_total",
    "Total number of clauses processed across all analyses",
)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def record_analysis(
    duration_sec: float,
    risks: Sequence,
    cache_hit: bool,
) -> None:
    """Update all relevant metrics after a successful analysis.

    Parameters
    ----------
    duration_sec:
        Wall-clock time the analysis took, in seconds.
    risks:
        Sequence of risk items (anything with ``risk_type`` and ``severity``
        attributes — typically ``RiskItem`` instances).
    cache_hit:
        Whether the result was served from cache.
    """
    # Latency
    analysis_duration.observe(duration_sec)

    # Request outcome
    analysis_requests.labels(status="success").inc()

    # Cache
    if cache_hit:
        cache_hits.inc()
    else:
        cache_misses.inc()

    # Per-risk counters
    for risk in risks:
        severity = risk.severity
        # severity may be an enum — normalise to its value string
        if hasattr(severity, "value"):
            severity = severity.value
        risk_detections.labels(category=risk.risk_type, severity=severity).inc()

    # Clauses processed — count each risk as one clause
    clauses_processed.inc(len(risks))


def record_error() -> None:
    """Record a failed analysis request."""
    analysis_requests.labels(status="error").inc()


def get_metrics_text() -> str:
    """Return all metrics in Prometheus text exposition format."""
    return generate_latest(REGISTRY).decode("utf-8")
