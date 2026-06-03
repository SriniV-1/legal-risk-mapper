"""
FastAPI router that exposes a ``GET /metrics`` endpoint serving Prometheus
text exposition format.

Include in your application with::

    from backend.routers.metrics_router import metrics_router
    app.include_router(metrics_router)
"""
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from backend.services.metrics import get_metrics_text

metrics_router = APIRouter()

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


@metrics_router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> PlainTextResponse:
    """Serve all registered Prometheus metrics."""
    return PlainTextResponse(
        content=get_metrics_text(),
        media_type=PROMETHEUS_CONTENT_TYPE,
    )
