from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import UserRole

DEMO_CREDENTIALS = {
    UserRole.CUSTOMER: ("+12025550101", ("projects", "service_requests", "notifications")),
    UserRole.BTP_COMPANY: ("+12025550102", ("opportunities", "applications", "company")),
    UserRole.FIELD_AGENT: ("+12025550103", ("projects", "tasks", "notifications")),
    UserRole.PROJECT_MANAGER: ("+12025550104", ("projects", "tasks", "recent_activity")),
    UserRole.ADMIN: ("+12025550105", ("service_requests", "companies", "projects", "opportunities", "recent_activity")),
    UserRole.SUPER_ADMIN: ("+12025550106", ("service_requests", "companies", "projects", "opportunities")),
}


@override_settings(DEBUG=True)
class DemoAccountTests(TestCase):
    """Les comptes de démonstration doivent présenter un espace réellement rempli, sans jamais être réels."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo_accounts", verbosity=0)

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _access_token(self, phone: str) -> str:
        response = self.client.post(
            "/api/v1/auth/login/",
            {"phone": phone, "password": "KemtaDemo2026!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["access"]

    def test_every_demo_role_gets_a_populated_dashboard(self):
        for role, (phone, expected_collections) in DEMO_CREDENTIALS.items():
            with self.subTest(role=role):
                response = self.client.get(
                    "/api/v1/dashboard/",
                    HTTP_AUTHORIZATION=f"Bearer {self._access_token(phone)}",
                )
                self.assertEqual(response.status_code, 200, response.data)
                self.assertTrue(response.data["is_demo"])
                self.assertEqual(response.data["role"], role)
                self.assertTrue(response.data["permissions"], "Les permissions du rôle doivent être exposées.")
                for collection in expected_collections:
                    value = response.data[collection]
                    self.assertTrue(value, f"{role} : « {collection} » doit contenir des données de démonstration.")

    def test_demo_data_is_explicitly_labelled(self):
        token = self._access_token(DEMO_CREDENTIALS[UserRole.CUSTOMER][0])
        dashboard = self.client.get("/api/v1/dashboard/", HTTP_AUTHORIZATION=f"Bearer {token}").data
        self.assertTrue(dashboard["projects"][0]["name"].startswith("DÉMO"))
        self.assertTrue(dashboard["service_requests"][0]["request_code"].startswith("KEMTA-REQ-DEMO"))
        self.assertTrue(dashboard["notifications"][0]["title"].startswith("DÉMO"))

        token = self._access_token(DEMO_CREDENTIALS[UserRole.BTP_COMPANY][0])
        dashboard = self.client.get("/api/v1/dashboard/", HTTP_AUTHORIZATION=f"Bearer {token}").data
        company = dashboard["company"]
        self.assertFalse(company["verified"])
        self.assertFalse(company["is_published"])
        self.assertTrue(company["name"].startswith("DÉMO"))
        self.assertTrue(dashboard["opportunities"][0]["title"].startswith("DÉMO"))

    def test_seed_command_is_idempotent(self):
        call_command("seed_demo_accounts", verbosity=0)
        token = self._access_token(DEMO_CREDENTIALS[UserRole.BTP_COMPANY][0])
        dashboard = self.client.get("/api/v1/dashboard/", HTTP_AUTHORIZATION=f"Bearer {token}").data
        self.assertEqual(len(dashboard["applications"]), 1)
        self.assertEqual(dashboard["statistics"]["applications"], 1)
