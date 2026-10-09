"""Espace propriétaire : budget, dépenses, reçus et demandes rattachées à un chantier.

Ces tests couvrent le parcours demandé côté client : compter ses projets avec KEMTA,
ouvrir le détail d'un projet et consulter ses justificatifs sans jamais exposer les
pièces d'un autre propriétaire.
"""
from datetime import date
from decimal import Decimal
import tempfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from projects.models import ExpenseStatus, Project, ProjectExpense, ProjectPhase, PhaseStatus
from service_requests.models import ServiceRequest, ServiceRequestStatus, ServiceType


class ProjectExpenseAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()
        self.owner = User.objects.create_user(
            phone="+237677123480", password="KemtA-secure!48271", first_name="Lydie", last_name="Tchana"
        )
        self.other_owner = User.objects.create_user(
            phone="+237677123481", password="KemtA-secure!48271", first_name="Paul", last_name="Ekwalla"
        )
        self.manager = User.objects.create_user(
            phone="+237677123482", password="KemtA-secure!48271", first_name="Alain", last_name="Foko",
            role=UserRole.PROJECT_MANAGER,
        )
        self.project = Project.objects.create(
            owner=self.owner,
            manager=self.manager,
            name="Maison familiale",
            city="Douala",
            project_type="Villa",
            budget_total=Decimal("25000000"),
            budget_spent=Decimal("4500000"),
        )
        ProjectPhase.objects.create(project=self.project, name="Fondations", position=1, status=PhaseStatus.CURRENT)
        self.expense = ProjectExpense.objects.create(
            project=self.project,
            label="Acompte fondations",
            category="LABOUR",
            amount=Decimal("4500000"),
            spent_at=date(2026, 8, 12),
            status=ExpenseStatus.VALIDATED,
            reference="REC-001",
        )
        self.expense.receipt.save(
            "rec-001.pdf",
            SimpleUploadedFile("rec-001.pdf", b"%PDF-1.4 contenu de test", content_type="application/pdf"),
            save=True,
        )

    def tearDown(self):
        self.media_override.disable()
        self.media_directory.cleanup()

    def test_owner_sees_project_count_budget_expenses_and_receipts(self):
        self.client.force_authenticate(user=self.owner)
        dashboard = self.client.get("/api/v1/dashboard/")
        self.assertEqual(dashboard.status_code, 200, dashboard.data)
        self.assertEqual(dashboard.data["statistics"]["projects"], 1)
        self.assertEqual(dashboard.data["statistics"]["receipts"], 1)

        detail = self.client.get(f"/api/v1/projects/{self.project.pk}/")
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data["budget"]["total"], "25000000.00")
        self.assertEqual(detail.data["budget"]["spent"], "4500000.00")
        self.assertEqual(detail.data["budget"]["remaining"], "20500000.00")
        self.assertEqual(detail.data["budget"]["receipt_count"], 1)
        self.assertEqual(len(detail.data["expenses"]), 1)
        # Chemin relatif à la racine de l'API : le client l'appelle avec son propre préfixe.
        self.assertEqual(detail.data["expenses"][0]["receipt_url"], f"/project-expenses/{self.expense.pk}/receipt/")
        self.assertEqual(len(detail.data["phases"]), 1)

    def test_owner_downloads_receipt_through_authenticated_endpoint(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f"/api/v1/project-expenses/{self.expense.pk}/receipt/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4 contenu de test")

    def test_receipt_is_not_reachable_from_public_media_url(self):
        # Le justificatif ne doit jamais être servi par le dossier média public.
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f"/media/{self.expense.receipt.name}")
        self.assertEqual(response.status_code, 404)

    def test_another_owner_cannot_read_expenses_receipt_or_project(self):
        self.client.force_authenticate(user=self.other_owner)
        # Le projet d'autrui est invisible : hors périmètre, donc 404 (aucune fuite d'existence).
        self.assertIn(self.client.get(f"/api/v1/projects/{self.project.pk}/").status_code, (403, 404))
        listing = self.client.get(f"/api/v1/project-expenses/?project={self.project.pk}")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["count"], 0)
        self.assertIn(self.client.get(f"/api/v1/project-expenses/{self.expense.pk}/receipt/").status_code, (403, 404))

    def test_project_detail_requires_authentication(self):
        self.assertEqual(self.client.get(f"/api/v1/projects/{self.project.pk}/").status_code, 401)

    def test_owner_cannot_record_expense(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            "/api/v1/project-expenses/",
            {
                "project": self.project.pk,
                "label": "Tentative",
                "category": "OTHER",
                "amount": "100000",
                "spent_at": "2026-09-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_records_expense_with_receipt(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            "/api/v1/project-expenses/",
            {
                "project": self.project.pk,
                "label": "Main-d’œuvre",
                "category": "LABOUR",
                "amount": "1200000",
                "spent_at": "2026-09-04",
                "receipt": SimpleUploadedFile("justificatif.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["has_receipt"])
        self.assertEqual(response.data["status"], ExpenseStatus.DECLARED)
        self.assertEqual(response.data["recorded_by_name"], "Alain Foko")

    def test_receipt_type_is_validated(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            "/api/v1/project-expenses/",
            {
                "project": self.project.pk,
                "label": "Fichier douteux",
                "amount": "1000",
                "spent_at": "2026-09-04",
                "receipt": SimpleUploadedFile("script.sh", b"#!/bin/sh", content_type="text/x-shellscript"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("receipt", response.data)

    def test_expense_without_receipt_returns_clear_error(self):
        expense = ProjectExpense.objects.create(
            project=self.project,
            label="Sans justificatif",
            amount=Decimal("500000"),
            spent_at=date(2026, 9, 5),
        )
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f"/api/v1/project-expenses/{expense.pk}/receipt/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Aucun justificatif", response.data["detail"])


class ProjectServiceRequestLinkTests(TestCase):
    """Une demande peut viser un chantier déjà suivi, et apparaît alors dans son détail."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.owner = User.objects.create_user(
            phone="+237677123483", password="KemtA-secure!48271", first_name="Lydie", last_name="Tchana"
        )
        self.other_owner = User.objects.create_user(
            phone="+237677123484", password="KemtA-secure!48271", first_name="Paul", last_name="Ekwalla"
        )
        self.project = Project.objects.create(owner=self.owner, name="Villa", city="Douala", project_type="Villa")

    def _payload(self, project_id, service_type="MAINTENANCE"):
        return {
            "service_type": service_type,
            "first_name": "Lydie",
            "last_name": "Tchana",
            "phone": "+237677123483",
            "city": "Douala",
            "description": "Demande de suivi sur un chantier existant.",
            "related_project": project_id,
        }

    def test_owner_attaches_request_to_own_project(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post("/api/v1/service-requests/", self._payload(self.project.pk), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["related_project"], self.project.pk)
        service_request = ServiceRequest.objects.get(pk=response.data["id"])
        self.assertEqual(service_request.owner, self.owner)

        detail = self.client.get(f"/api/v1/projects/{self.project.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.data["service_requests"]), 1)
        self.assertEqual(detail.data["service_requests"][0]["request_code"], service_request.request_code)

    def test_origin_request_appears_once_in_project_detail(self):
        origin = ServiceRequest.objects.create(
            owner=self.owner,
            service_type=ServiceType.BUILD,
            first_name="Lydie",
            last_name="Tchana",
            phone="+237677123483",
            status=ServiceRequestStatus.CONVERTED,
        )
        self.project.service_request = origin
        self.project.save(update_fields=("service_request", "updated_at"))
        attached = ServiceRequest.objects.create(
            owner=self.owner,
            service_type=ServiceType.MAINTENANCE,
            first_name="Lydie",
            last_name="Tchana",
            phone="+237677123483",
            related_project=self.project,
        )
        self.client.force_authenticate(user=self.owner)
        detail = self.client.get(f"/api/v1/projects/{self.project.pk}/")
        codes = [item["request_code"] for item in detail.data["service_requests"]]
        self.assertEqual(sorted(codes), sorted([origin.request_code, attached.request_code]))
        origin_entry = next(item for item in detail.data["service_requests"] if item["request_code"] == origin.request_code)
        self.assertTrue(origin_entry["is_origin"])

    def test_request_cannot_target_someone_else_project(self):
        self.client.force_authenticate(user=self.other_owner)
        response = self.client.post("/api/v1/service-requests/", self._payload(self.project.pk), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("related_project", response.data)
        self.assertFalse(ServiceRequest.objects.exists())
