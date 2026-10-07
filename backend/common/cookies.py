"""Pose du cookie de session KEMTA.

Le cookie de rafraîchissement est HttpOnly : il n'est jamais lisible par JavaScript.
Dans un aperçu embarqué (iframe), les navigateurs bloquent les cookies tiers ; l'attribut
``Partitioned`` (CHIPS) associé à ``SameSite=None`` leur permet de fonctionner sans exposer
le jeton. Ces options sont pilotées par les réglages ``REFRESH_COOKIE_*``.
"""
from http.cookies import Morsel

from django.conf import settings
from rest_framework_simplejwt.settings import api_settings

# Django < 6 ne connaît pas l'attribut Partitioned : on l'enregistre pour la sérialisation du cookie.
if "partitioned" not in Morsel._reserved:
    Morsel._reserved["partitioned"] = "Partitioned"
    Morsel._flags.add("partitioned")


def refresh_cookie_kwargs(request) -> dict:
    samesite = settings.REFRESH_COOKIE_SAMESITE or None
    secure = bool(settings.REFRESH_COOKIE_SECURE or request.is_secure())
    if samesite and samesite.lower() == "none":
        # SameSite=None n'est accepté par les navigateurs qu'avec Secure.
        secure = True
    return {
        "httponly": True,
        "secure": secure,
        "samesite": samesite,
        "path": settings.REFRESH_COOKIE_PATH,
        "max_age": int(api_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
    }


def set_refresh_cookie(response, value: str, request) -> None:
    kwargs = refresh_cookie_kwargs(request)
    if settings.REFRESH_COOKIE_PARTITIONED:
        try:
            response.set_cookie(key=settings.REFRESH_COOKIE_NAME, value=value, partitioned=True, **kwargs)
            return
        except TypeError:
            # Version de Django sans prise en charge : l'attribut est ajouté au morsel ci-dessous.
            pass
    response.set_cookie(key=settings.REFRESH_COOKIE_NAME, value=value, **kwargs)
    if settings.REFRESH_COOKIE_PARTITIONED:
        response.cookies[settings.REFRESH_COOKIE_NAME]["partitioned"] = True


def delete_refresh_cookie(response) -> None:
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        samesite=settings.REFRESH_COOKIE_SAMESITE or None,
    )
