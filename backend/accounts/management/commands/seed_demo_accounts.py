from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User, UserRole
from companies.models import CompanyProfile, PortfolioItem
from common.models import AuditLog
from notifications.models import Notification, NotificationType
from opportunities.models import Application, ApplicationStatus, Opportunity, OpportunityStatus
from projects.models import (
    ExpenseCategory,
    ExpenseStatus,
    FieldMission,
    FieldReport,
    FieldReportStatus,
    MissionStatus,
    MissionType,
    PhaseStatus,
    ProjectAssignment,
    Project,
    ProjectExpense,
    ProjectPhase,
    ProjectStatus,
    ProjectTask,
)
from service_requests.models import ServiceRequest, ServiceRequestStatus, ServiceType


def _pdf_text(value: str) -> str:
    return value.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_demo_receipt_pdf(lines: list[str]) -> bytes:
    """Construit un PDF minimal valide : justificatif fictif de démonstration.

    Aucune bibliothèque externe n’est requise, et le document rappelle qu’il est fictif.
    """
    parts = [f"BT /F1 15 Tf 60 790 Td ({_pdf_text(lines[0])}) Tj ET"]
    y = 752
    for line in lines[1:]:
        parts.append(f"BT /F1 11 Tf 60 {y} Td ({_pdf_text(line)}) Tj ET")
        y -= 20
    content = "\n".join(parts).encode("latin-1", "replace")
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    )
    document = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document += f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_offset = len(document)
    document += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    document += b"0000000000 65535 f \n"
    for offset in offsets:
        document += f"{offset:010d} 00000 n \n".encode("ascii")
    document += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")
    return bytes(document)


def attach_demo_receipt(expense: ProjectExpense, project_name: str) -> None:
    """Joint le justificatif fictif une seule fois (le seed reste idempotent)."""
    if expense.receipt:
        return
    lines = [
        "KEMTA — JUSTIFICATIF DE DÉPENSE (DÉMONSTRATION)",
        "Document fictif généré pour prévisualiser la plateforme.",
        "Aucune valeur comptable réelle : ne pas utiliser comme pièce justificative.",
        "",
        f"Projet : {project_name}",
        f"Dépense : {expense.label}",
        f"Catégorie : {expense.get_category_display()}",
        f"Montant : {expense.amount:,.0f} FCFA".replace(",", " "),
        f"Date : {expense.spent_at:%d/%m/%Y}",
        f"Référence : {expense.reference or '—'}",
        f"Statut : {expense.get_status_display()}",
    ]
    expense.receipt.save(
        f"{expense.reference.lower() or 'recu-demo'}.pdf",
        ContentFile(build_demo_receipt_pdf(lines)),
        save=True,
    )


def seed_project_expenses(project: Project, entries, recorded_by) -> list[ProjectExpense]:
    """Crée les dépenses de démonstration et vérifie qu’elles justifient le budget déclaré."""
    expenses = []
    for entry in entries:
        expense, _ = ProjectExpense.objects.update_or_create(
            project=project,
            reference=entry["reference"],
            defaults={
                "label": entry["label"],
                "category": entry["category"],
                "amount": entry["amount"],
                "spent_at": entry["spent_at"],
                "status": entry["status"],
                "notes": entry.get("notes", ""),
                "recorded_by": recorded_by,
            },
        )
        attach_demo_receipt(expense, project.name)
        expenses.append(expense)
    total = sum((expense.amount for expense in expenses), start=Decimal("0"))
    if project.budget_spent is not None and total != project.budget_spent:
        raise CommandError(
            f"Les dépenses de démonstration de « {project.name} » totalisent {total} "
            f"alors que le budget déclaré est {project.budget_spent}."
        )
    return expenses


DEMO_PASSWORD = "KemtaDemo2026!"
DEMO_ACCOUNTS = (
    {
        "phone": "+12025550101",
        "email": "demo.client@kemta.invalid",
        "last_name": "Client",
        "role": UserRole.CUSTOMER,
        "label": "Client / propriétaire",
    },
    {
        "phone": "+12025550102",
        "email": "demo.btp@kemta.invalid",
        "last_name": "Entreprise BTP",
        "role": UserRole.BTP_COMPANY,
        "label": "Entreprise BTP",
    },
    {
        "phone": "+12025550103",
        "email": "demo.terrain@kemta.invalid",
        "last_name": "Agent terrain",
        "role": UserRole.FIELD_AGENT,
        "label": "Agent terrain",
    },
    {
        "phone": "+12025550104",
        "email": "demo.gestion@kemta.invalid",
        "last_name": "Chef de projet",
        "role": UserRole.PROJECT_MANAGER,
        "label": "Chef de projet",
    },
    {
        "phone": "+12025550105",
        "email": "demo.admin@kemta.invalid",
        "last_name": "Administrateur",
        "role": UserRole.ADMIN,
        "label": "Administrateur",
    },
    {
        "phone": "+12025550106",
        "email": "demo.superadmin@kemta.invalid",
        "last_name": "Super administrateur",
        "role": UserRole.SUPER_ADMIN,
        "label": "Super-administrateur",
    },
)


class Command(BaseCommand):
    help = "Crée des comptes et données de démonstration, uniquement en environnement DEBUG."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Refusé : les comptes démo ne peuvent être créés qu’avec DJANGO_DEBUG=true.")

        users = {}
        now = timezone.now()
        for account in DEMO_ACCOUNTS:
            phone = account["phone"]
            email = account["email"]
            user = User.objects.filter(phone=phone).first()
            if user and (user.email != email or user.first_name != "Demo"):
                raise CommandError(f"Le numéro de démonstration {phone} est déjà utilisé par un autre compte ; aucun changement effectué.")

            if user is None:
                manager = User.objects.create_superuser if account["role"] == UserRole.SUPER_ADMIN else User.objects.create_user
                defaults = dict(
                    is_staff=account["role"] in {UserRole.ADMIN, UserRole.SUPER_ADMIN},
                    is_superuser=account["role"] == UserRole.SUPER_ADMIN,
                )
                user = manager(
                    phone=phone,
                    password=DEMO_PASSWORD,
                    first_name="Demo",
                    last_name=account["last_name"],
                    email=email,
                    role=account["role"],
                    phone_verified=True,
                    terms_accepted_at=now,
                    **defaults,
                )
            else:
                user.first_name = "Demo"
                user.last_name = account["last_name"]
                user.email = email
                user.role = account["role"]
                user.phone_verified = True
                user.terms_accepted_at = user.terms_accepted_at or now
                user.is_active = True
                user.is_staff = account["role"] in {UserRole.ADMIN, UserRole.SUPER_ADMIN}
                user.is_superuser = account["role"] == UserRole.SUPER_ADMIN
                user.set_password(DEMO_PASSWORD)
                user.save()
            users[account["role"]] = user

        company, _ = CompanyProfile.objects.get_or_create(
            user=users[UserRole.BTP_COMPANY],
            defaults={"name": "DÉMO — Bâtisseurs du Littoral", "slug": "demo-batisseurs-littoral"},
        )
        company.name = "DÉMO — Bâtisseurs du Littoral"
        company.description = "Entreprise fictive de démonstration. Ce profil n’est pas une entreprise réelle ni une recommandation KEMTA."
        company.city = "Douala"
        company.services = ["Gros œuvre", "Rénovation"]
        company.intervention_areas = ["Douala", "Littoral"]
        company.years_experience = 8
        company.verified = False
        company.is_published = False
        company.save()

        PortfolioItem.objects.update_or_create(
            company=company,
            title="DÉMO — Exemple de réalisation",
            defaults={
                "description": "Fiche fictive destinée à prévisualiser l’espace entreprise.",
                "project_type": "Exemple illustratif",
                "city": "Douala",
                "position": 1,
                "is_published": True,
            },
        )

        project, _ = Project.objects.get_or_create(
            owner=users[UserRole.CUSTOMER],
            name="DÉMO — Maison familiale à Douala",
            defaults={
                "manager": users[UserRole.PROJECT_MANAGER],
                "city": "Douala",
                "project_type": "Maison familiale",
                "status": ProjectStatus.ACTIVE,
                "progress": 42,
                "current_phase": "Murs & structure",
                "budget_total": Decimal("25000000"),
                "budget_spent": Decimal("10500000"),
                "planned_start": timezone.localdate() - timedelta(days=75),
                "planned_end": timezone.localdate() + timedelta(days=150),
            },
        )
        project.manager = users[UserRole.PROJECT_MANAGER]
        project.progress = 42
        project.current_phase = "Murs & structure"
        project.save(update_fields=("manager", "progress", "current_phase", "updated_at"))
        project.field_agents.add(users[UserRole.FIELD_AGENT])
        ProjectAssignment.objects.update_or_create(
            project=project,
            user=users[UserRole.FIELD_AGENT],
            role=ProjectAssignment.Role.FIELD_AGENT,
            defaults={"status": "ACTIVE", "assigned_by": users[UserRole.PROJECT_MANAGER]},
        )

        phases = (
            (1, "DÉMO — Étude & préparation", PhaseStatus.COMPLETED),
            (2, "DÉMO — Fondations", PhaseStatus.COMPLETED),
            (3, "DÉMO — Murs & structure", PhaseStatus.CURRENT),
            (4, "DÉMO — Toiture", PhaseStatus.UPCOMING),
        )
        phase_objects = {}
        for position, name, phase_status in phases:
            phase, _ = ProjectPhase.objects.update_or_create(
                project=project,
                position=position,
                defaults={"name": name, "status": phase_status},
            )
            phase_objects[position] = phase

        ProjectTask.objects.update_or_create(
            project=project,
            title="DÉMO — Vérifier l’avancement de la structure",
            defaults={
                "phase": phase_objects[3],
                "assigned_to": users[UserRole.FIELD_AGENT],
                "description": "Tâche fictive fournie uniquement pour explorer l’interface.",
                "status": ProjectTask.Status.IN_PROGRESS,
                "due_date": timezone.localdate() + timedelta(days=7),
            },
        )
        ProjectTask.objects.update_or_create(
            project=project,
            title="DÉMO — Relever les compteurs et l’avancement du jour",
            defaults={
                "phase": phase_objects[3],
                "assigned_to": users[UserRole.FIELD_AGENT],
                "description": "Tâche de démonstration : consigner les mesures relevées sur le chantier.",
                "status": ProjectTask.Status.TODO,
                "due_date": timezone.localdate() + timedelta(days=2),
            },
        )
        ProjectTask.objects.update_or_create(
            project=project,
            title="DÉMO — Préparer la prochaine visite de chantier",
            defaults={
                "phase": phase_objects[3],
                "assigned_to": users[UserRole.PROJECT_MANAGER],
                "description": "Tâche de démonstration : confirmer le prochain point de suivi.",
                "status": ProjectTask.Status.TODO,
                "due_date": timezone.localdate() + timedelta(days=3),
            },
        )
        active_mission, _ = FieldMission.objects.update_or_create(
            project=project,
            title="DÉMO — Contrôle structure du jour",
            defaults={
                "phase": phase_objects[3],
                "assigned_to": users[UserRole.FIELD_AGENT],
                "created_by": users[UserRole.PROJECT_MANAGER],
                "mission_type": MissionType.PROGRESS_CHECK,
                "status": MissionStatus.IN_PROGRESS,
                "scheduled_start": timezone.now(),
                "location": "Chantier Bonapriso, Douala",
                "instructions": "[DÉMO] Vérifier les murs porteurs et joindre les constats photo.",
                "checklist": [
                    {"id": "structure", "label": "Contrôler les murs porteurs", "required": True},
                    {"id": "safety", "label": "Observer les protections de chantier", "required": True},
                ],
            },
        )
        review_mission, _ = FieldMission.objects.update_or_create(
            project=project,
            title="DÉMO — Visite qualité fondations",
            defaults={
                "phase": phase_objects[2],
                "assigned_to": users[UserRole.FIELD_AGENT],
                "created_by": users[UserRole.PROJECT_MANAGER],
                "mission_type": MissionType.QUALITY_CONTROL,
                "status": MissionStatus.SUBMITTED,
                "scheduled_start": timezone.now() - timedelta(days=1),
                "location": "Chantier Bonapriso, Douala",
                "checklist": [],
            },
        )
        FieldReport.objects.update_or_create(
            mission=review_mission,
            defaults={
                "submitted_by": users[UserRole.FIELD_AGENT],
                "summary": "[DÉMO] Contrôle fondations effectué, rapport en attente de validation.",
                "observations": "Aucune anomalie critique observée.",
                "progress_percentage": 42,
                "status": FieldReportStatus.SUBMITTED,
                "submitted_at": timezone.now() - timedelta(hours=2),
            },
        )

        demo_request, _ = ServiceRequest.objects.get_or_create(
            request_code="KEMTA-REQ-DEMO-01",
            defaults={
                "owner": users[UserRole.CUSTOMER],
                "service_type": ServiceType.BUILD,
                "first_name": "Demo",
                "last_name": "Client",
                "phone": users[UserRole.CUSTOMER].phone,
                "email": users[UserRole.CUSTOMER].email or "",
                "city": "Douala",
                "project_type": "DÉMO — Maison familiale",
                "description": "[DÉMO] Demande fictive pour prévisualiser le traitement d’un projet.",
                "metadata": {"demo": True},
                "status": ServiceRequestStatus.NEW,
            },
        )
        if demo_request.owner_id not in {None, users[UserRole.CUSTOMER].pk}:
            raise CommandError("Le code de demande démo est déjà associé à une autre personne.")
        demo_request.owner = users[UserRole.CUSTOMER]
        demo_request.service_type = ServiceType.BUILD
        demo_request.first_name = "Demo"
        demo_request.last_name = "Client"
        demo_request.phone = users[UserRole.CUSTOMER].phone
        demo_request.email = users[UserRole.CUSTOMER].email or ""
        demo_request.city = "Douala"
        demo_request.project_type = "DÉMO — Maison familiale"
        demo_request.description = "[DÉMO] Demande fictive pour prévisualiser le traitement d’un projet."
        demo_request.metadata = {"demo": True}
        demo_request.status = ServiceRequestStatus.NEW
        demo_request.save()
        # La demande d'origine est rattachée au chantier qu’elle a permis d’ouvrir.
        project.service_request = demo_request
        project.save(update_fields=("service_request", "updated_at"))

        # --- Dépenses et justificatifs du projet principal (fictifs) ---
        seed_project_expenses(
            project,
            [
                {
                    "reference": "DEMO-REC-001",
                    "label": "DÉMO — Acompte fondations",
                    "category": ExpenseCategory.LABOUR,
                    "amount": Decimal("4500000"),
                    "spent_at": timezone.localdate() - timedelta(days=64),
                    "status": ExpenseStatus.VALIDATED,
                    "notes": "Ligne fictive : sert à illustrer une dépense justifiée.",
                },
                {
                    "reference": "DEMO-REC-002",
                    "label": "DÉMO — Ciment et fer à béton",
                    "category": ExpenseCategory.MATERIALS,
                    "amount": Decimal("3800000"),
                    "spent_at": timezone.localdate() - timedelta(days=48),
                    "status": ExpenseStatus.VALIDATED,
                    "notes": "Ligne fictive : matériaux de gros œuvre.",
                },
                {
                    "reference": "DEMO-REC-003",
                    "label": "DÉMO — Main-d’œuvre élévation des murs",
                    "category": ExpenseCategory.LABOUR,
                    "amount": Decimal("2200000"),
                    "spent_at": timezone.localdate() - timedelta(days=19),
                    "status": ExpenseStatus.DECLARED,
                    "notes": "Ligne fictive : justificatif en cours de rapprochement.",
                },
            ],
            recorded_by=users[UserRole.PROJECT_MANAGER],
        )

        # --- Deuxième chantier du même propriétaire (fictif, livré) ---
        delivered, _ = Project.objects.get_or_create(
            owner=users[UserRole.CUSTOMER],
            name="DÉMO — Villa livrée à Kribi",
            defaults={
                "manager": users[UserRole.PROJECT_MANAGER],
                "city": "Kribi",
                "project_type": "Villa",
                "status": ProjectStatus.COMPLETED,
                "progress": 100,
                "current_phase": "DÉMO — Livraison",
                "budget_total": Decimal("18000000"),
                "budget_spent": Decimal("17400000"),
                "planned_start": timezone.localdate() - timedelta(days=420),
                "planned_end": timezone.localdate() - timedelta(days=95),
            },
        )
        delivered.manager = users[UserRole.PROJECT_MANAGER]
        delivered.progress = 100
        delivered.status = ProjectStatus.COMPLETED
        delivered.current_phase = "DÉMO — Livraison"
        delivered.budget_total = Decimal("18000000")
        delivered.budget_spent = Decimal("17400000")
        delivered.save()
        delivered.field_agents.add(users[UserRole.FIELD_AGENT])
        ProjectAssignment.objects.update_or_create(
            project=delivered,
            user=users[UserRole.FIELD_AGENT],
            role=ProjectAssignment.Role.FIELD_AGENT,
            defaults={"status": "ACTIVE", "assigned_by": users[UserRole.PROJECT_MANAGER]},
        )
        for position, name in enumerate(
            ("DÉMO — Étude & préparation", "DÉMO — Gros œuvre", "DÉMO — Livraison"), start=1
        ):
            ProjectPhase.objects.update_or_create(
                project=delivered,
                position=position,
                defaults={"name": name, "status": PhaseStatus.COMPLETED},
            )
        seed_project_expenses(
            delivered,
            [
                {
                    "reference": "DEMO-REC-101",
                    "label": "DÉMO — Gros œuvre et second œuvre",
                    "category": ExpenseCategory.MATERIALS,
                    "amount": Decimal("14400000"),
                    "spent_at": timezone.localdate() - timedelta(days=210),
                    "status": ExpenseStatus.VALIDATED,
                    "notes": "Ligne fictive : chantier livré.",
                },
                {
                    "reference": "DEMO-REC-102",
                    "label": "DÉMO — Finitions et livraison",
                    "category": ExpenseCategory.OTHER,
                    "amount": Decimal("3000000"),
                    "spent_at": timezone.localdate() - timedelta(days=120),
                    "status": ExpenseStatus.VALIDATED,
                    "notes": "Ligne fictive : dernière situation de travaux.",
                },
            ],
            recorded_by=users[UserRole.PROJECT_MANAGER],
        )

        # --- Demandes rattachées à un chantier existant (fictives) ---
        related_request, _ = ServiceRequest.objects.get_or_create(
            request_code="KEMTA-REQ-DEMO-02",
            defaults={"owner": users[UserRole.CUSTOMER]},
        )
        related_request.owner = users[UserRole.CUSTOMER]
        related_request.service_type = ServiceType.MAINTENANCE
        related_request.first_name = "Demo"
        related_request.last_name = "Client"
        related_request.phone = users[UserRole.CUSTOMER].phone
        related_request.email = users[UserRole.CUSTOMER].email or ""
        related_request.city = "Douala"
        related_request.project_type = "Entretien"
        related_request.description = (
            "[DÉMO] Demande fictive rattachée au chantier « DÉMO — Maison familiale à Douala » "
            "pour illustrer le suivi des demandes d’un projet."
        )
        related_request.metadata = {"demo": True, "maintenanceServices": ["Visite de contrôle"]}
        related_request.status = ServiceRequestStatus.IN_REVIEW
        related_request.related_project = project
        related_request.save()

        delivered_request, _ = ServiceRequest.objects.get_or_create(
            request_code="KEMTA-REQ-DEMO-03",
            defaults={"owner": users[UserRole.CUSTOMER]},
        )
        delivered_request.owner = users[UserRole.CUSTOMER]
        delivered_request.service_type = ServiceType.BUILD
        delivered_request.first_name = "Demo"
        delivered_request.last_name = "Client"
        delivered_request.phone = users[UserRole.CUSTOMER].phone
        delivered_request.email = users[UserRole.CUSTOMER].email or ""
        delivered_request.city = "Kribi"
        delivered_request.project_type = "Villa"
        delivered_request.description = (
            "[DÉMO] Demande fictive à l’origine du chantier « DÉMO — Villa livrée à Kribi »."
        )
        delivered_request.metadata = {"demo": True}
        delivered_request.status = ServiceRequestStatus.CONVERTED
        delivered_request.related_project = None
        delivered_request.save()
        delivered.service_request = delivered_request
        delivered.save(update_fields=("service_request", "updated_at"))

        opportunity, _ = Opportunity.objects.update_or_create(
            created_by=users[UserRole.ADMIN],
            title="DÉMO — Rénovation pilote à Douala",
            defaults={
                "project_type": "Rénovation (exemple)",
                "city": "Douala",
                "budget_min": Decimal("5000000"),
                "budget_max": Decimal("8000000"),
                "description": "[DÉMO] Opportunité entièrement fictive. Aucun appel d’offres réel n’est associé à cette annonce.",
                "deadline": timezone.localdate() + timedelta(days=45),
                "status": OpportunityStatus.OPEN,
            },
        )
        Application.objects.update_or_create(
            opportunity=opportunity,
            company=company,
            defaults={
                "message": "[DÉMO] Réponse fictive affichée uniquement pour prévisualiser le suivi d’une candidature.",
                "similar_projects": ["DÉMO — Exemple de réalisation"],
                "team_summary": "Équipe fictive de démonstration.",
                "estimated_budget": Decimal("6500000"),
                "duration_days": 30,
                "status": ApplicationStatus.SUBMITTED,
                "internal_note": "Fixture de démonstration uniquement.",
            },
        )

        notification_content = {
            UserRole.CUSTOMER: (NotificationType.PROJECT, "DÉMO — Votre projet a une mise à jour", "Exemple fictif de notification client."),
            UserRole.BTP_COMPANY: (NotificationType.OPPORTUNITY, "DÉMO — Une opportunité est disponible", "Exemple fictif ; le profil de l’entreprise reste non publié."),
            UserRole.FIELD_AGENT: (NotificationType.TASK, "DÉMO — Une tâche terrain vous est assignée", "Consultez l’exemple de mission dans votre espace."),
            UserRole.PROJECT_MANAGER: (NotificationType.PROJECT, "DÉMO — Un projet est sous votre suivi", "Exemple fictif de notification gestionnaire."),
            UserRole.ADMIN: (NotificationType.GENERAL, "DÉMO — Une demande attend une revue", "Exemple fictif de demande dans la file d’administration."),
            UserRole.SUPER_ADMIN: (NotificationType.GENERAL, "DÉMO — Les données de prévisualisation sont prêtes", "Aucune de ces données n’est une activité réelle."),
        }
        audit_events = {
            UserRole.CUSTOMER: ("project.updated", "project", str(project.pk)),
            UserRole.BTP_COMPANY: ("application.submitted", "application", str(opportunity.pk)),
            UserRole.FIELD_AGENT: ("project_task.created", "project_task", str(project.pk)),
            UserRole.PROJECT_MANAGER: ("project.updated", "project", str(project.pk)),
            UserRole.ADMIN: ("service_request.created", "service_request", str(demo_request.pk)),
            UserRole.SUPER_ADMIN: ("opportunity.created", "opportunity", str(opportunity.pk)),
        }
        for role, user in users.items():
            notification_type, title, body = notification_content[role]
            Notification.objects.update_or_create(
                user=user,
                dedupe_key="kemta-demo-dashboard-v1",
                defaults={
                    "notification_type": notification_type,
                    "title": title,
                    "body": body,
                    "action_url": "/dashboard/",
                    "data": {"demo": True},
                    "read_at": None,
                },
            )
            event, object_type, object_id = audit_events[role]
            AuditLog.objects.get_or_create(
                actor=user,
                event=event,
                object_type=object_type,
                object_id=object_id,
                defaults={"metadata": {"demo": True}},
            )

        self.stdout.write(self.style.SUCCESS("Comptes et données de démonstration créés ou actualisés (local uniquement)."))
        self.stdout.write(f"Mot de passe commun : {DEMO_PASSWORD}")
        self.stdout.write("Indicatif de démonstration : +1 ; numéros réservés fictifs 202-555-0101 à 202-555-0106.")
        for account in DEMO_ACCOUNTS:
            self.stdout.write(f"  {account['label']}: {account['phone']}  ·  {account['email']}")
        self.stdout.write("Les projets et le profil BTP portent la mention DÉMO ; le profil BTP n’est ni vérifié ni publié.")
