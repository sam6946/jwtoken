from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from projects.models import FieldMission, FieldReport, MissionStatus, Project, ProjectAssignment


class FieldWorkflowAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.owner = User.objects.create_user(phone="+237677123611", password="Test-pass-2026!", first_name="Client", last_name="Kemta")
        self.manager = User.objects.create_user(phone="+237677123612", password="Test-pass-2026!", first_name="Chef", last_name="Projet", role=UserRole.PROJECT_MANAGER)
        self.agent = User.objects.create_user(phone="+237677123613", password="Test-pass-2026!", first_name="Agent", last_name="Un", role=UserRole.FIELD_AGENT)
        self.other_agent = User.objects.create_user(phone="+237677123614", password="Test-pass-2026!", first_name="Agent", last_name="Deux", role=UserRole.FIELD_AGENT)
        self.project = Project.objects.create(owner=self.owner, manager=self.manager, name="Maison test", city="Douala", project_type="Villa")
        self.project.field_agents.add(self.agent, self.other_agent)
        ProjectAssignment.objects.create(project=self.project, user=self.agent, assigned_by=self.manager)
        ProjectAssignment.objects.create(project=self.project, user=self.other_agent, assigned_by=self.manager)

    def _mission(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post("/api/v1/field-missions/", {
            "project": self.project.pk,
            "assigned_to": self.agent.pk,
            "title": "Vérification structure",
            "location": "Bonapriso",
            "checklist": [{"id": "safety", "label": "Sécurité", "required": True}],
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return FieldMission.objects.get(pk=response.data["id"])

    def test_strict_mission_to_validated_report_workflow(self):
        mission = self._mission()
        self.client.force_authenticate(self.agent)
        self.assertEqual(self.client.post(f"/api/v1/field-missions/{mission.pk}/accept/", {}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/field-missions/{mission.pk}/start/", {}, format="json").status_code, 200)
        report_response = self.client.post("/api/v1/field-reports/", {
            "mission": mission.pk,
            "summary": "Structure inspectée et conforme.",
            "observations": "Pas de défaut critique.",
            "progress_percentage": 45,
            "checklist_results": [{"id": "safety", "label": "Sécurité", "completed": True}],
            "client_reference": "report-offline-001",
        }, format="json", HTTP_IDEMPOTENCY_KEY="report-offline-001")
        self.assertEqual(report_response.status_code, 201, report_response.data)
        report_id = report_response.data["id"]
        duplicate = self.client.post("/api/v1/field-reports/", {
            "mission": mission.pk, "summary": "ignoré", "client_reference": "report-offline-001"
        }, format="json", HTTP_IDEMPOTENCY_KEY="report-offline-001")
        self.assertEqual(duplicate.status_code, 200, duplicate.data)
        self.assertEqual(self.client.post(f"/api/v1/field-reports/{report_id}/submit/", {}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/field-reports/{report_id}/approve/", {}, format="json").status_code, 403)

        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.post(f"/api/v1/field-reports/{report_id}/start-review/", {}, format="json").status_code, 200)
        approved = self.client.post(f"/api/v1/field-reports/{report_id}/approve/", {}, format="json")
        self.assertEqual(approved.status_code, 200, approved.data)
        mission.refresh_from_db()
        report = FieldReport.objects.get(pk=report_id)
        self.assertEqual(mission.status, MissionStatus.APPROVED)
        self.assertEqual(report.status, "APPROVED")

    def test_agent_cannot_see_another_agents_mission_or_change_project(self):
        mission = self._mission()
        self.client.force_authenticate(self.other_agent)
        self.assertEqual(self.client.get(f"/api/v1/field-missions/{mission.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/field-missions/").data["results"], [])
        self.assertIn(
            self.client.patch(f"/api/v1/projects/{self.project.pk}/", {"budget_total": "1"}, format="json").status_code,
            (403, 404),
        )
        self.assertEqual(self.client.post("/api/v1/project-assignments/", {"project": self.project.pk, "user": self.other_agent.pk}, format="json").status_code, 403)

    def test_issue_creation_is_idempotent_for_offline_retry(self):
        mission = self._mission()
        self.client.force_authenticate(self.agent)
        self.client.post(f"/api/v1/field-missions/{mission.pk}/accept/", {}, format="json")
        self.client.post(f"/api/v1/field-missions/{mission.pk}/start/", {}, format="json")
        payload = {
            "project": self.project.pk,
            "mission": mission.pk,
            "title": "Fissure observée",
            "description": "Fissure fine sur le mur nord.",
            "priority": "HIGH",
            "client_reference": "issue-offline-001",
        }
        first = self.client.post("/api/v1/project-issues/", payload, format="json", HTTP_IDEMPOTENCY_KEY="issue-offline-001")
        second = self.client.post("/api/v1/project-issues/", payload, format="json", HTTP_IDEMPOTENCY_KEY="issue-offline-001")
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(first.data["id"], second.data["id"])

    def test_field_dashboards_are_role_scoped(self):
        mission = self._mission()
        self.client.force_authenticate(self.manager)
        manager_dashboard = self.client.get("/api/v1/dashboard/field-operations/")
        self.assertEqual(manager_dashboard.status_code, 200, manager_dashboard.data)
        self.assertEqual(manager_dashboard.data["role"], UserRole.PROJECT_MANAGER)
        self.assertEqual(manager_dashboard.data["today_missions"], [])
        self.client.force_authenticate(self.agent)
        agent_dashboard = self.client.get("/api/v1/dashboard/field-operations/")
        self.assertEqual(agent_dashboard.status_code, 200, agent_dashboard.data)
        self.assertEqual(agent_dashboard.data["role"], UserRole.FIELD_AGENT)
        self.assertNotIn(mission.pk, [item["id"] for item in agent_dashboard.data["upcoming_missions"]])
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get("/api/v1/dashboard/field-operations/").status_code, 403)

    def test_manager_requests_correction_then_agent_restarts(self):
        mission = self._mission()
        self.client.force_authenticate(self.agent)
        self.client.post(f"/api/v1/field-missions/{mission.pk}/accept/", {}, format="json")
        self.client.post(f"/api/v1/field-missions/{mission.pk}/start/", {}, format="json")
        report = self.client.post("/api/v1/field-reports/", {
            "mission": mission.pk, "summary": "Visite réalisée.", "checklist_results": [{"id": "safety", "label": "Sécurité", "completed": True}],
        }, format="json")
        self.assertEqual(report.status_code, 201, report.data)
        report_id = report.data["id"]
        self.client.post(f"/api/v1/field-reports/{report_id}/submit/", {}, format="json")
        self.client.force_authenticate(self.manager)
        revision = self.client.post(f"/api/v1/field-reports/{report_id}/request-revision/", {"reason": "Ajoutez une photo nette de la zone contrôlée."}, format="json")
        self.assertEqual(revision.status_code, 200, revision.data)
        self.client.force_authenticate(self.agent)
        restarted = self.client.post(f"/api/v1/field-missions/{mission.pk}/start/", {}, format="json")
        self.assertEqual(restarted.status_code, 200, restarted.data)
        mission.refresh_from_db()
        self.assertEqual(mission.status, MissionStatus.IN_PROGRESS)
