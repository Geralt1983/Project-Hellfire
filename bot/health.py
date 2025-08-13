import json, time, aiohttp.web
def build_app(shared):
    async def metrics(request):
        from prometheus_client import REGISTRY, generate_latest, CONTENT_TYPE_LATEST
        output = generate_latest(REGISTRY)
        return aiohttp.web.Response(body=output, headers={"Content-Type":CONTENT_TYPE_LATEST})
    async def health(request):
        now=time.time(); last=shared["watchdog"].last_metrics_ts; age=now-last
        status = "ok" if age <= shared["age_limit"] and shared["watchdog"].paused_until <= now else "unhealthy"
        code = 200 if status=="ok" else 503
        body = {"status":status,"watchdog":"green" if shared["watchdog"].paused_until<=now else "red","metrics_age_sec": int(age)}
        return aiohttp.web.json_response(body, status=code)
    app=aiohttp.web.Application()
    app.add_routes([aiohttp.web.get("/metrics", metrics), aiohttp.web.get("/health", health)])
    return app
