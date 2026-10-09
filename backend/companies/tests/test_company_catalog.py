from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from companies.models import CompanyProfile
from opportunities.models import Application, Opportunity, OpportunityStatus


class BtpCompanyAndOpportunityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.company_user = User.objects.create_user(
            phone="+237677123480",
            password="KemtA-secure!48271",
            first_name="Estelle",
            last_name="Mballa",
            role=UserRole.BTP_COMPANY,
            phone_verified=True,
        )
        self.admin = User.objects.create_superuser(
            phone="+237677123481",
            password="KemtA-secure!48271",
            first_name="KEMTA",
            last_name="Admin",
        )

    def _create_company(self) -> CompanyProfile:
        self.client.force_authenticate(user=self.company_user)
        response = self.client.put(
            "/api/v1/companies/me/",
            {
                "name": "Bâtir Cameroun",
                "city": "Douala",
                "description": "Entreprise spécialisée dans les travaux de gros œuvre et la rénovation de maisons au Cameroun.",
                "services": ["Gros œuvre", "Rénovation"],
                "intervention_areas": ["Douala", "Kribi"],
                "years_experience": 8,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        return CompanyProfile.objects.get(user=self.company_user)

    def test_company_profile_stays_private_until_verified(self):
        company = self._create_company()
        self.assertFalse(company.is_published)
        self.client.force_authenticate(user=None)
        private_response = self.client.get(f"/api/v1/companies/{company.slug}/")
        self.assertEqual(private_response.status_code, 404)

        company.verified = True
        company.save()
        public_response = self.client.get(f"/api/v1/companies/{company.slug}/")
        self.assertEqual(public_response.status_code, 200, public_response.data)
        self.assertTrue(public_response.data["verified"])
        self.assertEqual(public_response.data["services"], ["Gros œuvre", "Rénovation"])

    def test_unverified_company_cannot_apply_then_verified_company_can(self):
        company = self._create_company()
        opportunity = Opportunity.objects.create(
            created_by=self.admin,
            title="Construction d’une maison familiale",
            project_type="Maison individuelle",
            city="Yaoundé",
            budget_min=12000000,
            budget_max=18000000,
            description="Construction complète d’une maison familiale de plain-pied.",
            deadline=timezone.localdate() + timedelta(days=30),
            status=OpportunityStatus.OPEN,
        )
        self.client.force_authenticate(user=self.company_user)
        payload = {
            "opportunity": opportunity.pk,
            "message": "Notre équipe de 12 personnes propose une réalisation par phases.",
            "estimated_budget": "15000000",
            "duration_days": 120,
        }
        denied = self.client.post("/api/v1/applications/", payload, format="json")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(Application.objects.count(), 0)

        company.verified = True
        company.save()
        accepted = self.client.post("/api/v1/applications/", payload, format="json")
        self.assertEqual(accepted.status_code, 201, accepted.data)
        self.assertEqual(accepted.data["status"], "SUBMITTED")
        self.assertEqual(Application.objects.get().company, company)

    def test_public_opportunity_list_hides_drafts_and_expired_calls(self):
        Opportunity.objects.create(
            created_by=self.admin,
            title="Appel ouvert",
            project_type="Villa",
            city="Douala",
            description="Un projet dont les candidatures sont encore ouvertes.",
            deadline=timezone.localdate() + timedelta(days=10),
            status=OpportunityStatus.OPEN,
        )
        Opportunity.objects.create(
            created_by=self.admin,
            title="Brouillon interne",
            project_type="Maison",
            city="Yaoundé",
            description="Ne doit pas apparaître au public.",
            deadline=timezone.localdate() + timedelta(days=20),
            status=OpportunityStatus.DRAFT,
        )
        response = self.client.get("/api/v1/opportunities/?status=OPEN")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Appel ouvert")
