"""HTTP endpoints for Prometheus metrics and application health checks."""

import time
from typing import Any, Dict

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest


def build_app(shared: Dict[str, Any]) -> web.Application:
    """Create an ``aiohttp`` application exposing /metrics and /health."""

    async def metrics(_: web.Request) -> web.Response:
        """Return Prometheus metrics for scraping."""
        output = generate_latest(REGISTRY)
        return web.Response(body=output, headers={"Content-Type": CONTENT_TYPE_LATEST})

    async def health(_: web.Request) -> web.Response:
        """Return JSON describing application health."""
        now = time.time()
        watchdog = shared["watchdog"]
        age = now - watchdog.last_metrics_ts
        paused = watchdog.paused_until > now

        status = "ok" if age <= shared["age_limit"] and not paused else "unhealthy"
        body = {
            "status": status,
            "watchdog": "green" if not paused else "red",
            "metrics_age_sec": int(age),
        }
        code = 200 if status == "ok" else 503
        return web.json_response(body, status=code)

    app = web.Application()
    app.add_routes([web.get("/metrics", metrics), web.get("/health", health)])
    return app
