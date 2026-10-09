from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from projects.models import Project, ProjectPhase, ProjectTask, PhaseStatus


class ProjectAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.owner = User.objects.create_user(
            phone="+237677123470", password="KemtA-secure!48271", first_name="Lydie", last_name="Tchana", phone_verified=True
        )
        self.manager = User.objects.create_user(
            phone="+237677123471", password="KemtA-secure!48271", first_name="Alain", last_name="Foko", role=UserRole.PROJECT_MANAGER
        )
        self.field_agent = User.objects.create_user(
            phone="+237677123472", password="KemtA-secure!48271", first_name="Michel", last_name="Ngo", role=UserRole.FIELD_AGENT
        )

    def test_manager_creates_project_with_a_real_phase_timeline(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            "/api/v1/projects/",
            {
                "owner": self.owner.pk,
                "name": "Maison familiale",
                "city": "Douala",
                "project_type": "Villa",
                "budget_total": "25000000.00",
                "field_agents": [self.field_agent.pk],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        project = Project.objects.get(pk=response.data["id"])
        self.assertEqual(project.owner, self.owner)
        self.assertEqual(project.manager, self.manager)
        self.assertEqual(project.phases.count(), 8)
        self.assertEqual(project.current_phase, "Étude & préparation")
        self.assertEqual(project.phases.get(position=1).status, PhaseStatus.CURRENT)
        self.assertEqual(project.field_agents.get(), self.field_agent)

    def test_customer_can_view_only_owned_projects(self):
        project = Project.objects.create(
            owner=self.owner, name="Villa", city="Yaoundé", project_type="Maison", current_phase="Fondations"
        )
        other_owner = User.objects.create_user(
            phone="+237677123473", password="KemtA-secure!48271", first_name="Nina", last_name="Biloa"
        )
        other_project = Project.objects.create(
            owner=other_owner, name="Immeuble", city="Kribi", project_type="Immeuble"
        )
        self.client.force_authenticate(user=self.owner)
        own_response = self.client.get(f"/api/v1/projects/{project.pk}/")
        private_response = self.client.get(f"/api/v1/projects/{other_project.pk}/")
        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(own_response.data["name"], "Villa")
        self.assertEqual(private_response.status_code, 404)

    def test_customer_cannot_create_or_change_a_project(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            "/api/v1/projects/",
            {"owner": self.owner.pk, "name": "Projet", "city": "Douala", "project_type": "Maison"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Project.objects.count(), 0)

    def test_field_agent_can_advance_an_assigned_task_only(self):
        project = Project.objects.create(owner=self.owner, name="Villa", city="Douala", project_type="Maison")
        project.field_agents.add(self.field_agent)
        own_task = ProjectTask.objects.create(project=project, assigned_to=self.field_agent, title="Relevé de structure")
        other_task = ProjectTask.objects.create(project=project, assigned_to=self.manager, title="Validation du budget")
        self.client.force_authenticate(user=self.field_agent)

        allowed = self.client.patch(f"/api/v1/project-tasks/{own_task.pk}/", {"status": "DONE"}, format="json")
        self.assertEqual(allowed.status_code, 200, allowed.data)
        own_task.refresh_from_db()
        self.assertEqual(own_task.status, "DONE")

        denied = self.client.patch(f"/api/v1/project-tasks/{other_task.pk}/", {"status": "DONE"}, format="json")
        # La tâche d’un collègue n’est même pas exposée à l’agent terrain (403 ou 404 selon le filtrage).
        self.assertIn(denied.status_code, (403, 404))
        other_task.refresh_from_db()
        self.assertEqual(other_task.status, "TODO")

    def test_dashboard_returns_project_and_permission_data_in_one_response(self):
        project = Project.objects.create(
            owner=self.owner,
            name="Maison familiale",
            city="Douala",
            project_type="Villa",
            progress=42,
            current_phase="Structure & murs",
        )
        ProjectPhase.objects.create(project=project, name="Structure & murs", position=1, status=PhaseStatus.CURRENT)
        self.client.force_authenticate(user=self.owner)
        response = self.client.get("/api/v1/dashboard/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["statistics"]["projects"], 1)
        self.assertEqual(response.data["projects"][0]["current_phase"], "Structure & murs")
        self.assertIn("VIEW_PROJECT", response.data["permissions"])
        self.assertIn("notifications", response.data)
