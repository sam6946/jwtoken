from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from administration.models import SupportTicket
from notifications.models import Notification
from projects.models import Project


class AdministrationAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = User.objects.create_user(
            phone="+237677129901",
            password="Admin-test-2026!",
            first_name="Admin",
            last_name="Kemta",
            role=UserRole.ADMIN,
        )
        self.super_admin = User.objects.create_user(
            phone="+237677129902",
            password="Admin-test-2026!",
            first_name="Super",
            last_name="Kemta",
            role=UserRole.SUPER_ADMIN,
        )
        self.customer = User.objects.create_user(
            phone="+237677129903",
            password="Admin-test-2026!",
            first_name="Client",
            last_name="Kemta",
        )
        Project.objects.create(
            owner=self.customer,
            name="Projet audit",
            city="Douala",
            project_type="Villa",
        )

    def test_admin_dashboard_and_lists_are_protected(self):
        self.client.force_authenticate(self.admin)
        dashboard = self.client.get("/api/v1/admin/dashboard/?period=7")
        self.assertEqual(dashboard.status_code, 200, dashboard.data)
        self.assertEqual(dashboard.data["statistics"]["users_total"], 3)
        projects = self.client.get("/api/v1/admin/projects/?search=audit")
        self.assertEqual(projects.status_code, 200, projects.data)
        self.assertEqual(projects.data["count"], 1)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get("/api/v1/admin/dashboard/").status_code, 403)

    def test_admin_can_suspend_customer_but_not_administrator(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f"/api/v1/admin/users/{self.customer.pk}/status/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)
        self.assertEqual(
            self.client.post(
                f"/api/v1/admin/users/{self.super_admin.pk}/status/",
                {"is_active": False},
                format="json",
            ).status_code,
            403,
        )

    def test_notification_requires_idempotency_key_and_deduplicates(self):
        self.client.force_authenticate(self.admin)
        payload = {
            "recipients": [self.customer.pk],
            "title": "Information",
            "body": "Une information utile.",
        }
        self.assertEqual(
            self.client.post(
                "/api/v1/admin/notifications/send/", payload, format="json"
            ).status_code,
            400,
        )
        first = self.client.post(
            "/api/v1/admin/notifications/send/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="notice-001",
        )
        self.assertEqual(first.status_code, 200, first.data)
        repeated = self.client.post(
            "/api/v1/admin/notifications/send/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="notice-001",
        )
        self.assertEqual(repeated.status_code, 200, repeated.data)
        self.assertEqual(Notification.objects.filter(user=self.customer).count(), 1)

    def test_support_and_settings_have_separate_privileges(self):
        self.client.force_authenticate(self.admin)
        ticket = self.client.post(
            "/api/v1/admin/support-tickets/",
            {
                "requester": self.customer.pk,
                "subject": "Besoin d’aide",
                "description": "Demande de support.",
            },
            format="json",
        )
        self.assertEqual(ticket.status_code, 201, ticket.data)
        self.assertEqual(SupportTicket.objects.count(), 1)
        self.assertEqual(
            self.client.post(
                "/api/v1/admin/settings/",
                {"key": "platform_name", "value": {"name": "KEMTA"}},
                format="json",
            ).status_code,
            403,
        )
        self.client.force_authenticate(self.super_admin)
        self.assertEqual(
            self.client.post(
                "/api/v1/admin/settings/",
                {"key": "platform_name", "value": {"name": "KEMTA"}},
                format="json",
            ).status_code,
            201,
        )
