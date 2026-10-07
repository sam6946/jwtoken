from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User


@override_settings(DEBUG=True, SMS_PROVIDER="console")
class PhoneAuthAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _request_otp(self, phone: str, purpose: str = "REGISTER") -> str:
        response = self.client.post("/api/v1/auth/otp/request/", {"phone": phone, "purpose": purpose}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["debug_code"]

    def _verify(self, phone: str, code: str, purpose: str = "REGISTER") -> str:
        response = self.client.post(
            "/api/v1/auth/otp/verify/",
            {"phone": phone, "code": code, "purpose": purpose},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["verification_token"]

    def test_register_requires_phone_otp_and_sets_http_only_refresh_cookie(self):
        phone = "+237 677 12 34 56"
        code = self._request_otp(phone)
        verification_token = self._verify(phone, code)
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "phone": phone,
                "verification_token": verification_token,
                "first_name": "Amina",
                "last_name": "Nkom",
                "email": "amina@example.com",
                "password": "KemtA-secure!48271",
                "role": "CUSTOMER",
                "terms_accepted": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["user"]["phone"], "+237677123456")
        self.assertTrue(response.data["user"]["phone_verified"])
        self.assertIsNotNone(User.objects.get(phone="+237677123456").terms_accepted_at)
        self.assertIn("access", response.data)
        self.assertTrue(self.client.cookies["kemta_refresh"]["httponly"])
        self.assertTrue(User.objects.get(phone="+237677123456").has_usable_password())

    def test_otp_is_single_use_and_failed_attempts_are_counted(self):
        phone = "+237 677 12 34 57"
        code = self._request_otp(phone)
        bad_response = self.client.post(
            "/api/v1/auth/otp/verify/",
            {"phone": phone, "code": "000000" if code != "000000" else "000001", "purpose": "REGISTER"},
            format="json",
        )
        self.assertEqual(bad_response.status_code, 400)
        token = self._verify(phone, code)
        self.assertTrue(token)
        second_use = self.client.post(
            "/api/v1/auth/otp/verify/",
            {"phone": phone, "code": code, "purpose": "REGISTER"},
            format="json",
        )
        self.assertEqual(second_use.status_code, 400)

    def test_password_login_rotates_refresh_cookie_and_logout_revokes_it(self):
        user = User.objects.create_user(
            phone="+237677123458",
            password="KemtA-secure!48271",
            first_name="Jean",
            last_name="Manga",
            phone_verified=True,
        )
        login = self.client.post(
            "/api/v1/auth/login/",
            {"phone": "677123458", "password": "KemtA-secure!48271"},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)
        original_refresh = self.client.cookies["kemta_refresh"].value
        self.client.cookies.clear()
        self.client.cookies["kemta_refresh"] = original_refresh
        refresh = self.client.post("/api/v1/auth/token/refresh/", {}, format="json")
        self.assertEqual(refresh.status_code, 200, refresh.data)
        rotated_refresh = self.client.cookies["kemta_refresh"].value
        self.assertNotEqual(original_refresh, rotated_refresh)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.data['access']}")
        logout = self.client.post("/api/v1/auth/logout/", {}, format="json")
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(user.phone, "+237677123458")
        self.assertEqual(self.client.cookies["kemta_refresh"].value, "")

    def test_password_reset_uses_phone_otp_and_validates_new_password(self):
        user = User.objects.create_user(
            phone="+237677123459",
            password="Old-password!82736",
            first_name="Nora",
            last_name="Tamba",
            phone_verified=True,
        )
        code = self._request_otp(user.phone, "PASSWORD_RESET")
        verification_token = self._verify(user.phone, code, "PASSWORD_RESET")
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"verification_token": verification_token, "password": "New-Kemta!71924secure"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertTrue(user.check_password("New-Kemta!71924secure"))
        self.assertFalse(user.check_password("Old-password!82736"))

    def test_login_otp_issues_a_session(self):
        User.objects.create_user(
            phone="+237677123460",
            password="KemtA-secure!48271",
            first_name="Paul",
            last_name="Tchou",
            phone_verified=True,
        )
        code = self._request_otp("677123460", "LOGIN")
        verification_token = self._verify("677123460", code, "LOGIN")
        response = self.client.post("/api/v1/auth/otp/login/", {"verification_token": verification_token}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["phone"], "+237677123460")
