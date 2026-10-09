import logging
import re
import uuid

from django.conf import settings

from .logging import request_id_var

logger = logging.getLogger("kemta")

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        candidate = request.headers.get("X-Request-ID", "")
        request_id = candidate if _REQUEST_ID_PATTERN.fullmatch(candidate) else uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)


class ApiDiagnosticsMiddleware:
    """Journalise, en mode debug uniquement, le contexte d'authentification des appels API.

    Aucun secret n'est écrit : seules la présence d'un en-tête ou d'un cookie et l'origine
    de la requête sont consignées, ce qui permet de diagnostiquer les sessions perdues.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not settings.DEBUG or not request.path.startswith("/api/v1/"):
            return response
        logger.info(
            "api.auth path=%s status=%s auth_header=%s authorization=%s refresh_cookie=%s client=%s origin=%s fetch_site=%s fetch_mode=%s fetch_dest=%s ua=%s",
            request.path,
            response.status_code,
            "yes" if request.headers.get("Authorization") or request.headers.get("X-Kemta-Auth") else "no",
            "Authorization" if request.headers.get("Authorization") else ("X-Kemta-Auth" if request.headers.get("X-Kemta-Auth") else "-"),
            "yes" if request.COOKIES.get(settings.REFRESH_COOKIE_NAME) else "no",
            request.headers.get("X-Kemta-Client", "-"),
            request.headers.get("Origin", "-"),
            request.headers.get("Sec-Fetch-Site", "-"),
            request.headers.get("Sec-Fetch-Mode", "-"),
            request.headers.get("Sec-Fetch-Dest", "-"),
            request.headers.get("User-Agent", "-")[:60],
        )
        return response
