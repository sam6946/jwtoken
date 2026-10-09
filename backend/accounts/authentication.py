"""Authentification JWT de KEMTA.

L'en-tête standard reste ``Authorization: Bearer <jeton>``. Certains environnements
d'aperçu (proxy d'aperçu, tunnel) retirent cet en-tête précis en transit, alors que les
en-têtes personnalisés passent. Un second en-tête, de nom neutre, est donc accepté en
repli : il transporte exactement le même jeton et obéit aux mêmes règles de validation.
Le repli est désactivé par défaut hors développement via ``ALLOW_TOKEN_AUTH_HEADER_FALLBACK``.
"""
from django.conf import settings
from rest_framework_simplejwt.authentication import HTTP_HEADER_ENCODING, JWTAuthentication

FALLBACK_HEADER = "X-Kemta-Auth"
FALLBACK_HEADER_META = f"HTTP_{FALLBACK_HEADER.upper().replace('-', '_')}"


class KemtaJWTAuthentication(JWTAuthentication):
    """JWTAuthentication qui accepte un en-tête de repli quand l'original est filtré."""

    def get_header(self, request):
        header = super().get_header(request)
        if header is None and getattr(settings, "ALLOW_TOKEN_AUTH_HEADER_FALLBACK", False):
            header = request.META.get(FALLBACK_HEADER_META)
            if isinstance(header, str):
                # DRF compare le préfixe (« Bearer ») octet par octet.
                header = header.encode(HTTP_HEADER_ENCODING)
        return header
