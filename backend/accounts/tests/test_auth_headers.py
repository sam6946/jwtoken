"""L'en-tête standard suffit, mais certains proxys d'aperçu le retirent en transit.

Le repli ``X-Kemta-Auth`` transporte le même jeton et doit obéir aux mêmes règles :
accepté quand il est activé, ignoré sinon.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User


@override_settings(SMS_PROVIDER="console")
class TokenHeaderFallbackTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(phone="+1202555099", password="MotDePasse2026!")

    def _token(self) -> str:
        return str(RefreshToken.for_user(self.user).access_token)

    def test_standard_header_authenticates(self):
        response = self.client.get("/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {self._token()}")
        self.assertEqual(response.status_code, 200, response.data)

    @override_settings(ALLOW_TOKEN_AUTH_HEADER_FALLBACK=True)
    def test_fallback_header_authenticates_when_enabled(self):
        response = self.client.get("/api/v1/auth/me/", HTTP_X_KEMTA_AUTH=f"Bearer {self._token()}")
        self.assertEqual(response.status_code, 200, response.data)

    @override_settings(ALLOW_TOKEN_AUTH_HEADER_FALLBACK=False)
    def test_fallback_header_is_ignored_when_disabled(self):
        response = self.client.get("/api/v1/auth/me/", HTTP_X_KEMTA_AUTH=f"Bearer {self._token()}")
        self.assertEqual(response.status_code, 401, response.data)

    @override_settings(ALLOW_TOKEN_AUTH_HEADER_FALLBACK=True)
    def test_invalid_fallback_token_is_rejected(self):
        response = self.client.get("/api/v1/auth/me/", HTTP_X_KEMTA_AUTH="Bearer jeton-invalide")
        self.assertEqual(response.status_code, 401, response.data)
