"""Parcours de création et de vérification des comptes entreprise.

Couvre les cinq étapes du parcours et les décisions d'administration, en
s'assurant au passage que l'existant (profil entreprise, catalogue, candidatures)
n'est pas modifié.
"""
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from common.models import AuditLog
from companies.models import (
    CompanyDocument,
    CompanyDocumentStatus,
    CompanyDocumentType,
    CompanyProfile,
    CompanyVerificationLevel,
    CompanyVerificationStatus,
)
from notifications.models import Notification

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def pdf_file(name: str = "piece.pdf"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, PDF_BYTES, content_type="application/pdf")


@override_settings(DEBUG=True, SMS_PROVIDER="console")
class CompanyVerificationFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.owner_phone = "+237677900101"
        self.company_user = User.objects.create_user(
            phone=self.owner_phone,
            password="KemtA-secure!48271",
            first_name="Nadine",
            last_name="Etoga",
            email="contact@batir-demo.invalid",
            role=UserRole.BTP_COMPANY,
            phone_verified=True,
        )
        self.admin = User.objects.create_superuser(
            phone="+237677900102",
            password="KemtA-secure!48271",
            first_name="KEMTA",
            last_name="Admin",
        )
        self.other_company_user = User.objects.create_user(
            phone="+237677900103",
            password="KemtA-secure!48271",
            first_name="Autre",
            last_name="Entreprise",
            role=UserRole.BTP_COMPANY,
            phone_verified=True,
        )

    # --- Utilitaires -------------------------------------------------------
    def _register_company_account(self, phone: str = "+237 677 90 01 10", name: str = "Bâtir Demo SARL") -> dict:
        otp_response = self.client.post("/api/v1/auth/otp/request/", {"phone": phone, "purpose": "REGISTER"}, format="json")
        self.assertEqual(otp_response.status_code, 200, otp_response.data)
        verify_response = self.client.post(
            "/api/v1/auth/otp/verify/",
            {"phone": phone, "code": otp_response.data["debug_code"], "purpose": "REGISTER"},
            format="json",
        )
        self.assertEqual(verify_response.status_code, 200, verify_response.data)
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "phone": phone,
                "verification_token": verify_response.data["verification_token"],
                "first_name": "Paul",
                "last_name": "Mvondo",
                "email": "paul@demo.invalid",
                "password": "KemtA-secure!48271",
                "role": UserRole.BTP_COMPANY,
                "company_name": name,
                "terms_accepted": True,
            },
            format="json",
        )
        # 200 : comportement existant de l'endpoint d'inscription, inchangé.
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def _create_company(self, user=None) -> CompanyProfile:
        user = user or self.company_user
        self.client.force_authenticate(user=user)
        response = self.client.patch(
            "/api/v1/companies/me/",
            {
                "name": "Bâtir Demo SARL",
                "legal_name": "Bâtir Demo SARL",
                "company_type": "SARL",
                "sector": "Construction",
                "country": "Cameroun",
                "city": "Douala",
                "address": "Rue des Palmiers, Bonapriso",
                "description": "Entreprise de construction et de rénovation basée à Douala depuis dix ans.",
                "services": ["Gros œuvre"],
                "intervention_areas": ["Douala"],
                "years_experience": 10,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        return CompanyProfile.objects.get(user=user)

    def _upload(self, document_type: str, name: str = "piece.pdf"):
        response = self.client.post(
            "/api/v1/companies/me/documents/",
            {"document_type": document_type, "file": pdf_file(name)},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response

    def _upload_required_documents(self):
        for document_type in (CompanyDocumentType.RCCM, CompanyDocumentType.NIU, CompanyDocumentType.IDENTITY_DOCUMENT):
            self._upload(document_type, f"{document_type.lower()}.pdf")

    # --- Étape 1 : création du compte --------------------------------------
    def test_company_registration_creates_profile_shell_and_keeps_customer_flow_intact(self):
        self._register_company_account()
        user = User.objects.get(phone="+237677900110")
        self.assertTrue(user.phone_verified)
        self.assertEqual(user.role, UserRole.BTP_COMPANY)
        company = CompanyProfile.objects.get(user=user)
        self.assertEqual(company.name, "Bâtir Demo SARL")
        self.assertEqual(company.verification_status, CompanyVerificationStatus.DRAFT)
        self.assertEqual(company.verification_level, CompanyVerificationLevel.ACCOUNT)
        self.assertFalse(company.verified)

        # Un compte client classique n'est pas concerné par la création de profil.
        cache.clear()
        self.client.force_authenticate(user=None)
        otp = self.client.post("/api/v1/auth/otp/request/", {"phone": "+237677900111", "purpose": "REGISTER"}, format="json")
        verified = self.client.post(
            "/api/v1/auth/otp/verify/",
            {"phone": "+237677900111", "code": otp.data["debug_code"], "purpose": "REGISTER"},
            format="json",
        )
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "phone": "+237677900111",
                "verification_token": verified.data["verification_token"],
                "first_name": "Client",
                "last_name": "Classique",
                "password": "KemtA-secure!48271",
                "role": UserRole.CUSTOMER,
                "terms_accepted": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        customer = User.objects.get(phone="+237677900111")
        self.assertFalse(CompanyProfile.objects.filter(user=customer).exists())

    # --- Étape 2 et 3 : profil entreprise ----------------------------------
    def test_partial_save_allows_continuing_later(self):
        self.client.force_authenticate(user=self.company_user)
        response = self.client.patch("/api/v1/companies/me/", {"name": "Bâtir Demo"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        company = CompanyProfile.objects.get(user=self.company_user)
        self.assertEqual(company.legal_name, "")
        self.assertEqual(company.verification_status, CompanyVerificationStatus.DRAFT)

        # Le PUT complet existant continue de fonctionner à l'identique.
        put_response = self.client.put(
            "/api/v1/companies/me/",
            {
                "name": "Bâtir Demo SARL",
                "city": "Douala",
                "description": "Entreprise spécialisée dans les travaux de gros œuvre et la rénovation de maisons.",
                "services": ["Gros œuvre", "Rénovation"],
                "intervention_areas": ["Douala", "Kribi"],
                "years_experience": 8,
            },
            format="json",
        )
        self.assertEqual(put_response.status_code, 200, put_response.data)
        self.assertEqual(put_response.data["name"], "Bâtir Demo SARL")

    def test_verification_snapshot_reports_missing_items(self):
        self.client.force_authenticate(user=self.company_user)
        self.client.patch("/api/v1/companies/me/", {"name": "Bâtir Demo"}, format="json")
        response = self.client.get("/api/v1/companies/me/verification/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], CompanyVerificationStatus.DRAFT)
        self.assertFalse(response.data["can_submit"])
        self.assertIn("Nom légal", response.data["missing_profile_fields"])
        self.assertIn("RCCM", response.data["missing_documents"])
        states = {step["key"]: step["state"] for step in response.data["checklist"]}
        self.assertEqual(states["ACCOUNT"], "DONE")
        self.assertEqual(states["PHONE"], "DONE")
        self.assertEqual(states["PROFILE"], "PENDING")

    # --- Étape 4 : documents ------------------------------------------------
    def test_document_upload_replaces_and_stays_private(self):
        company = self._create_company()
        self._upload(CompanyDocumentType.RCCM, "rccm-v1.pdf")
        document = CompanyDocument.objects.get(company=company, document_type=CompanyDocumentType.RCCM)
        self.assertEqual(document.status, CompanyDocumentStatus.PENDING)

        # Remplacement : un seul document par type.
        self._upload(CompanyDocumentType.RCCM, "rccm-v2.pdf")
        self.assertEqual(CompanyDocument.objects.filter(company=company, document_type=CompanyDocumentType.RCCM).count(), 1)
        document.refresh_from_db()
        self.assertEqual(document.original_name, "rccm-v2.pdf")

        # Le propriétaire peut ouvrir sa pièce…
        own_response = self.client.get(f"/api/v1/companies/me/documents/{document.pk}/file/")
        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(own_response["Content-Type"], "application/pdf")
        self.assertTrue(own_response.streaming or own_response.has_header("Content-Disposition"))

        # … l'équipe KEMTA aussi, mais pas une autre entreprise ni un visiteur.
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get(f"/api/v1/companies/me/documents/{document.pk}/file/").status_code, 200)
        self.client.force_authenticate(user=self.other_company_user)
        self.assertEqual(self.client.get(f"/api/v1/companies/me/documents/{document.pk}/file/").status_code, 403)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(f"/api/v1/companies/me/documents/{document.pk}/file/").status_code, 401)

    def test_document_type_and_file_are_validated(self):
        self._create_company()
        from django.core.files.uploadedfile import SimpleUploadedFile

        bad_type = self.client.post(
            "/api/v1/companies/me/documents/",
            {"document_type": "PAYSAGE", "file": pdf_file()},
            format="multipart",
        )
        self.assertEqual(bad_type.status_code, 400)

        bad_file = self.client.post(
            "/api/v1/companies/me/documents/",
            {"document_type": CompanyDocumentType.RCCM, "file": SimpleUploadedFile("notes.txt", b"bonjour", content_type="text/plain")},
            format="multipart",
        )
        self.assertEqual(bad_file.status_code, 400)

    # --- Étape 5 : soumission et vérification -------------------------------
    def test_submission_requires_profile_and_documents(self):
        company = self._create_company()
        self.client.force_authenticate(user=self.company_user)
        incomplete = self.client.post("/api/v1/companies/me/verification/submit/", {}, format="json")
        self.assertEqual(incomplete.status_code, 400)
        self.assertIn("documents", incomplete.data)

        self._upload_required_documents()
        accepted = self.client.post("/api/v1/companies/me/verification/submit/", {}, format="json")
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(accepted.data["status"], CompanyVerificationStatus.PENDING)
        company.refresh_from_db()
        self.assertIsNotNone(company.verification_submitted_at)
        self.assertTrue(AuditLog.objects.filter(event="company.verification_submitted", object_id=str(company.pk)).exists())
        self.assertTrue(Notification.objects.filter(user=self.admin, title__icontains="à vérifier").exists())

        # Deuxième envoi : refusé proprement.
        again = self.client.post("/api/v1/companies/me/verification/submit/", {}, format="json")
        self.assertEqual(again.status_code, 400)

    def test_only_kemta_can_review_and_decisions_update_the_company(self):
        company = self._create_company()
        self._upload_required_documents()
        self.client.post("/api/v1/companies/me/verification/submit/", {}, format="json")

        # La file d'attente est réservée à l'équipe KEMTA.
        self.assertEqual(self.client.get("/api/v1/companies/verification/queue/").status_code, 403)
        self.client.force_authenticate(user=self.admin)
        queue = self.client.get("/api/v1/companies/verification/queue/")
        self.assertEqual(queue.status_code, 200, queue.data)
        self.assertEqual(queue.data["count"], 1)
        self.assertEqual(len(queue.data["results"][0]["documents"]), 3)

        # Prise en charge puis validation.
        started = self.client.post(f"/api/v1/companies/{company.pk}/verification/", {"action": "start_review"}, format="json")
        self.assertEqual(started.status_code, 200, started.data)
        company.refresh_from_db()
        self.assertEqual(company.verification_status, CompanyVerificationStatus.UNDER_REVIEW)

        approved = self.client.post(f"/api/v1/companies/{company.pk}/verification/", {"action": "approve"}, format="json")
        self.assertEqual(approved.status_code, 200, approved.data)
        company.refresh_from_db()
        self.assertEqual(company.verification_status, CompanyVerificationStatus.VERIFIED)
        self.assertTrue(company.verified)
        self.assertTrue(company.is_published)
        self.assertEqual(company.verification_level, CompanyVerificationLevel.BUSINESS_VERIFIED)
        self.assertEqual(company.verification_reviewed_by, self.admin)
        self.assertTrue(AuditLog.objects.filter(event="company.verified").exists())
        self.assertTrue(Notification.objects.filter(user=self.company_user, title="Entreprise vérifiée").exists())

        # Le profil devient public et le reste après une mise à jour de la vitrine.
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(f"/api/v1/companies/{company.slug}/").status_code, 200)
        self.client.force_authenticate(user=self.company_user)
        self.client.patch("/api/v1/companies/me/", {"city": "Yaoundé"}, format="json")
        company.refresh_from_db()
        self.assertTrue(company.verified)

    def test_rejection_requires_a_reason_and_targeted_correction(self):
        company = self._create_company()
        self._upload_required_documents()
        self.client.post("/api/v1/companies/me/verification/submit/", {}, format="json")
        self.client.force_authenticate(user=self.admin)

        without_reason = self.client.post(f"/api/v1/companies/{company.pk}/verification/", {"action": "reject"}, format="json")
        self.assertEqual(without_reason.status_code, 400)

        correction = self.client.post(
            f"/api/v1/companies/{company.pk}/verification/",
            {"action": "request_correction", "document_type": CompanyDocumentType.RCCM, "reason": "Le document RCCM fourni est illisible."},
            format="json",
        )
        self.assertEqual(correction.status_code, 200, correction.data)
        company.refresh_from_db()
        self.assertEqual(company.verification_status, CompanyVerificationStatus.REJECTED)
        rccm = CompanyDocument.objects.get(company=company, document_type=CompanyDocumentType.RCCM)
        self.assertEqual(rccm.status, CompanyDocumentStatus.REJECTED)
        self.assertIn("illisible", rccm.rejection_reason)
        self.assertTrue(AuditLog.objects.filter(event="company.document_rejected").exists())

        # L'entreprise ne corrige que l'élément visé, puis resoumet.
        self.client.force_authenticate(user=self.company_user)
        snapshot = self.client.get("/api/v1/companies/me/verification/")
        self.assertEqual(snapshot.data["rejection_reason"], "Le document RCCM fourni est illisible.")
        corrected = next(item for item in snapshot.data["documents"] if item["document_type"] == CompanyDocumentType.RCCM)
        self.assertEqual(corrected["rejection_reason"], "Le document RCCM fourni est illisible.")
        self._upload(CompanyDocumentType.RCCM, "rccm-corrige.pdf")
        resubmitted = self.client.post("/api/v1/companies/me/verification/submit/", {}, format="json")
        self.assertEqual(resubmitted.status_code, 200, resubmitted.data)
        company.refresh_from_db()
        self.assertEqual(company.verification_status, CompanyVerificationStatus.PENDING)
        self.assertEqual(company.verification_rejection_reason, "")
        rccm.refresh_from_db()
        self.assertEqual(rccm.status, CompanyDocumentStatus.PENDING)

    def test_suspension_withdraws_verification_and_public_profile(self):
        company = self._create_company()
        self._upload_required_documents()
        self.client.post("/api/v1/companies/me/verification/submit/", {}, format="json")
        self.client.force_authenticate(user=self.admin)
        self.client.post(f"/api/v1/companies/{company.pk}/verification/", {"action": "approve"}, format="json")

        suspended = self.client.post(
            f"/api/v1/companies/{company.pk}/verification/",
            {"action": "suspend", "reason": "Documents non conformes après contrôle."},
            format="json",
        )
        self.assertEqual(suspended.status_code, 200, suspended.data)
        company.refresh_from_db()
        self.assertEqual(company.verification_status, CompanyVerificationStatus.SUSPENDED)
        self.assertFalse(company.verified)
        self.assertFalse(company.is_published)
        self.assertTrue(AuditLog.objects.filter(event="company.suspended").exists())
        self.assertTrue(Notification.objects.filter(user=self.company_user, title="Vérification suspendue").exists())
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(f"/api/v1/companies/{company.slug}/").status_code, 404)

    def test_catalog_cache_follows_verification_decisions(self):
        """Le catalogue public ne sert jamais une décision périmée."""
        cache.clear()
        company = self._create_company()
        company.is_published = True
        company.save()
        self.client.force_authenticate(user=None)
        self.assertIn(company.slug, self._catalog_slugs())  # réponse mise en cache

        self.client.force_authenticate(user=self.admin)
        self.client.post(
            f"/api/v1/companies/{company.pk}/verification/",
            {"action": "suspend", "reason": "Contrôle de conformité en cours."},
            format="json",
        )
        self.client.force_authenticate(user=None)
        self.assertNotIn(company.slug, self._catalog_slugs())

        self.client.force_authenticate(user=self.admin)
        self.client.post(f"/api/v1/companies/{company.pk}/verification/", {"action": "approve"}, format="json")
        self.client.force_authenticate(user=None)
        self.assertIn(company.slug, self._catalog_slugs())
        self.assertEqual(self.client.get(f"/api/v1/companies/{company.slug}/").status_code, 200)

    def _catalog_slugs(self) -> list[str]:
        response = self.client.get("/api/v1/companies/")
        self.assertEqual(response.status_code, 200)
        return [item["slug"] for item in response.data["results"]]

    def test_verified_company_level_can_be_advanced(self):
        company = self._create_company()
        self._upload_required_documents()
        self.client.post("/api/v1/companies/me/verification/submit/", {}, format="json")
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f"/api/v1/companies/{company.pk}/verification/",
            {"action": "approve", "advanced": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        company.refresh_from_db()
        self.assertEqual(company.verification_level, CompanyVerificationLevel.ADVANCED)

    def test_existing_company_features_still_work(self):
        """Non-régression : profil, catalogue et candidatures inchangés."""
        company = self._create_company()
        company.verified = True
        company.save()
        self.assertEqual(company.is_published, True)
        self.client.force_authenticate(user=None)
        catalog = self.client.get("/api/v1/companies/")
        self.assertEqual(catalog.status_code, 200)
        self.assertGreaterEqual(catalog.data["count"], 1)

        # Les nouvelles données légales ne fuient pas dans le catalogue public.
        public = self.client.get(f"/api/v1/companies/{company.slug}/")
        self.assertEqual(public.status_code, 200)
        self.assertNotIn("legal_name", public.data)
        self.assertNotIn("registration_number", public.data)
