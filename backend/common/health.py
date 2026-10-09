from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import JsonResponse


def health(request):
    return JsonResponse({"status": "ok", "service": "kemta-api"})


def readiness(request):
    checks: dict[str, str] = {}
    status_code = 200
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except DatabaseError:
        checks["database"] = "unavailable"
        status_code = 503
    try:
        cache.set("health:ready", "ok", timeout=5)
        if cache.get("health:ready") != "ok":
            raise RuntimeError("cache check failed")
        checks["cache"] = "ok"
    except Exception:
        checks["cache"] = "unavailable"
        status_code = 503
    return JsonResponse({"status": "ready" if status_code == 200 else "not_ready", "checks": checks}, status=status_code)
