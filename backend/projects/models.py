from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ProjectStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "En cours"
    PAUSED = "PAUSED", "En pause"
    COMPLETED = "COMPLETED", "Terminé"
    ARCHIVED = "ARCHIVED", "Archivé"


class PhaseStatus(models.TextChoices):
    COMPLETED = "COMPLETED", "Terminée"
    CURRENT = "CURRENT", "En cours"
    UPCOMING = "UPCOMING", "À venir"
    ISSUE = "ISSUE", "À vérifier"


class Project(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="projects")
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_projects",
    )
    field_agents = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="field_projects")
    service_request = models.OneToOneField(
        "service_requests.ServiceRequest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="project",
    )
    name = models.CharField(max_length=160)
    city = models.CharField(max_length=100, db_index=True)
    project_type = models.CharField(max_length=100)
    status = models.CharField(max_length=16, choices=ProjectStatus.choices, default=ProjectStatus.ACTIVE, db_index=True)
    progress = models.PositiveSmallIntegerField(default=0, validators=(MinValueValidator(0), MaxValueValidator(100)))
    current_phase = models.CharField(max_length=100, blank=True)
    budget_total = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=(MinValueValidator(Decimal("0")),))
    budget_spent = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=(MinValueValidator(Decimal("0")),))
    planned_start = models.DateField(null=True, blank=True)
    planned_end = models.DateField(null=True, blank=True)
    last_report_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=("owner", "status")),
            models.Index(fields=("manager", "status")),
            models.Index(fields=("status", "updated_at")),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(progress__gte=0, progress__lte=100), name="project_progress_0_100"),
        ]

    def __str__(self) -> str:
        return self.name


class ProjectPhase(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="phases")
    name = models.CharField(max_length=100)
    position = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=PhaseStatus.choices, default=PhaseStatus.UPCOMING, db_index=True)
    planned_start = models.DateField(null=True, blank=True)
    planned_end = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [models.UniqueConstraint(fields=("project", "position"), name="uniq_project_phase_position")]
        indexes = [models.Index(fields=("project", "status", "position"))]

    def __str__(self) -> str:
        return f"{self.project.name} · {self.name}"


class ProjectTask(models.Model):
    class Status(models.TextChoices):
        TODO = "TODO", "À faire"
        IN_PROGRESS = "IN_PROGRESS", "En cours"
        DONE = "DONE", "Terminée"
        BLOCKED = "BLOCKED", "Bloquée"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    phase = models.ForeignKey(ProjectPhase, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_tasks")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TODO, db_index=True)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("due_date", "created_at")
        indexes = [models.Index(fields=("project", "status", "due_date"))]

    def __str__(self) -> str:
        return self.title


class ProjectAssignmentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    PAUSED = "PAUSED", "Suspendue"
    ENDED = "ENDED", "Terminée"


class ProjectAssignment(models.Model):
    """Affectation explicite d'un agent, complément compatible de field_agents."""

    class Role(models.TextChoices):
        FIELD_AGENT = "FIELD_AGENT", "Agent terrain"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="project_assignments")
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.FIELD_AGENT)
    status = models.CharField(max_length=16, choices=ProjectAssignmentStatus.choices, default=ProjectAssignmentStatus.ACTIVE, db_index=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_project_assignments",
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("project", "user", "role"), name="uniq_project_assignment_role")]
        indexes = [
            models.Index(fields=("project", "status")),
            models.Index(fields=("user", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.project} · {self.user}"


class MissionStatus(models.TextChoices):
    PLANNED = "PLANNED", "Planifiée"
    ACCEPTED = "ACCEPTED", "Acceptée"
    IN_PROGRESS = "IN_PROGRESS", "En cours"
    SUBMITTED = "SUBMITTED", "Rapport soumis"
    UNDER_REVIEW = "UNDER_REVIEW", "En revue"
    APPROVED = "APPROVED", "Validée"
    REVISION_REQUIRED = "REVISION_REQUIRED", "Correction demandée"
    CANCELLED = "CANCELLED", "Annulée"


class MissionType(models.TextChoices):
    INSPECTION = "INSPECTION", "Visite d’inspection"
    PROGRESS_CHECK = "PROGRESS_CHECK", "Contrôle d’avancement"
    QUALITY_CONTROL = "QUALITY_CONTROL", "Contrôle qualité"
    ISSUE_FOLLOW_UP = "ISSUE_FOLLOW_UP", "Suivi de problème"
    OTHER = "OTHER", "Autre mission"


class FieldMission(models.Model):
    """Unité de travail terrain contrôlée par la machine d'état KEMTA."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="field_missions")
    phase = models.ForeignKey(ProjectPhase, null=True, blank=True, on_delete=models.SET_NULL, related_name="field_missions")
    task = models.ForeignKey(ProjectTask, null=True, blank=True, on_delete=models.SET_NULL, related_name="field_missions")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="field_missions")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_field_missions")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    mission_type = models.CharField(max_length=24, choices=MissionType.choices, default=MissionType.INSPECTION, db_index=True)
    status = models.CharField(max_length=24, choices=MissionStatus.choices, default=MissionStatus.PLANNED, db_index=True)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=180, blank=True)
    instructions = models.TextField(blank=True)
    # Chaque item conserve au minimum `id`, `label`, `required` et éventuellement `help`.
    checklist = models.JSONField(default=list, blank=True)
    requires_geo_confirmation = models.BooleanField(default=False)
    start_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    start_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_confirmed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    revision_reason = models.TextField(blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("scheduled_start", "-created_at")
        indexes = [
            models.Index(fields=("project", "status", "scheduled_start")),
            models.Index(fields=("assigned_to", "status", "scheduled_start")),
            models.Index(fields=("status", "scheduled_start")),
        ]

    def __str__(self) -> str:
        return f"{self.title} · {self.project}"


class FieldReportStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    SUBMITTED = "SUBMITTED", "Soumis"
    UNDER_REVIEW = "UNDER_REVIEW", "En revue"
    APPROVED = "APPROVED", "Validé"
    REVISION_REQUIRED = "REVISION_REQUIRED", "Correction demandée"


class FieldReport(models.Model):
    """Rapport d'une mission, distinct du rapport de projet à destination du client."""

    mission = models.OneToOneField(FieldMission, on_delete=models.CASCADE, related_name="field_report")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="field_reports")
    summary = models.TextField(blank=True)
    observations = models.TextField(blank=True)
    progress_percentage = models.PositiveSmallIntegerField(
        default=0,
        validators=(MinValueValidator(0), MaxValueValidator(100)),
    )
    checklist_results = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=24, choices=FieldReportStatus.choices, default=FieldReportStatus.DRAFT, db_index=True)
    review_comment = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_field_reports",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    client_reference = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("submitted_by", "client_reference"),
                condition=~Q(client_reference=""),
                name="uniq_field_report_client_reference",
            ),
        ]
        indexes = [models.Index(fields=("status", "updated_at"))]

    def __str__(self) -> str:
        return f"Rapport · {self.mission}"


class IssuePriority(models.TextChoices):
    LOW = "LOW", "Faible"
    MEDIUM = "MEDIUM", "Moyenne"
    HIGH = "HIGH", "Élevée"
    CRITICAL = "CRITICAL", "Critique"


class IssueStatus(models.TextChoices):
    OPEN = "OPEN", "Ouvert"
    IN_PROGRESS = "IN_PROGRESS", "En traitement"
    RESOLVED = "RESOLVED", "Résolu"
    CLOSED = "CLOSED", "Clos"


class ProjectIssue(models.Model):
    """Anomalie signalée sur le chantier par un agent ou le chef de projet."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="issues")
    mission = models.ForeignKey(FieldMission, null=True, blank=True, on_delete=models.SET_NULL, related_name="issues")
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_project_issues")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_project_issues",
    )
    title = models.CharField(max_length=180)
    description = models.TextField()
    priority = models.CharField(max_length=16, choices=IssuePriority.choices, default=IssuePriority.MEDIUM, db_index=True)
    status = models.CharField(max_length=16, choices=IssueStatus.choices, default=IssueStatus.OPEN, db_index=True)
    resolution_note = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    client_reference = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("reported_by", "client_reference"),
                condition=~Q(client_reference=""),
                name="uniq_project_issue_client_reference",
            ),
        ]
        indexes = [
            models.Index(fields=("project", "status", "priority")),
            models.Index(fields=("mission", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.title} · {self.project}"


class EvidenceType(models.TextChoices):
    PHOTO = "PHOTO", "Photo"
    VIDEO = "VIDEO", "Vidéo"


class Evidence(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = "PENDING", "À vérifier"
        VERIFIED = "VERIFIED", "Vérifiée"
        REJECTED = "REJECTED", "Refusée"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="evidences")
    phase = models.ForeignKey(ProjectPhase, null=True, blank=True, on_delete=models.SET_NULL, related_name="evidences")
    mission = models.ForeignKey(FieldMission, null=True, blank=True, on_delete=models.SET_NULL, related_name="evidences")
    issue = models.ForeignKey(ProjectIssue, null=True, blank=True, on_delete=models.SET_NULL, related_name="evidences")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_evidences")
    title = models.CharField(max_length=160)
    caption = models.TextField(blank=True)
    location = models.CharField(max_length=180, blank=True)
    evidence_type = models.CharField(max_length=12, choices=EvidenceType.choices, default=EvidenceType.PHOTO, db_index=True)
    image = models.ImageField(upload_to="evidence/original/%Y/%m/", blank=True)
    video = models.FileField(upload_to="evidence/video/%Y/%m/", blank=True)
    thumbnail = models.ImageField(upload_to="evidence/thumbnail/%Y/%m/", blank=True)
    medium = models.ImageField(upload_to="evidence/medium/%Y/%m/", blank=True)
    large = models.ImageField(upload_to="evidence/large/%Y/%m/", blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    verification_status = models.CharField(max_length=16, choices=VerificationStatus.choices, default=VerificationStatus.PENDING, db_index=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    client_reference = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("uploaded_by", "client_reference"),
                condition=~Q(client_reference=""),
                name="uniq_evidence_client_reference",
            ),
        ]
        indexes = [
            models.Index(fields=("project", "verification_status", "created_at")),
            models.Index(fields=("mission", "created_at")),
        ]

    def __str__(self) -> str:
        return self.title


class ProjectReport(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="reports")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_project_reports")
    title = models.CharField(max_length=180)
    summary = models.TextField()
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    document = models.FileField(upload_to="reports/%Y/%m/", blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("project", "created_at"))]

    def __str__(self) -> str:
        return self.title


class ExpenseCategory(models.TextChoices):
    MATERIALS = "MATERIALS", "Matériaux"
    LABOUR = "LABOUR", "Main-d’œuvre"
    EQUIPMENT = "EQUIPMENT", "Équipement"
    TRANSPORT = "TRANSPORT", "Transport"
    ADMIN = "ADMIN", "Frais administratifs"
    OTHER = "OTHER", "Autre"


class ExpenseStatus(models.TextChoices):
    DECLARED = "DECLARED", "Déclarée"
    VALIDATED = "VALIDATED", "Justifiée"
    REJECTED = "REJECTED", "Refusée"


class ProjectExpense(models.Model):
    """Dépense d'un chantier, avec son justificatif.

    Le reçu n'est jamais servi depuis le dossier média public : il est téléchargé
    via un point d'entrée API qui vérifie que le demandeur a accès au projet.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="expenses")
    label = models.CharField(max_length=180)
    category = models.CharField(max_length=16, choices=ExpenseCategory.choices, default=ExpenseCategory.OTHER, db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2, validators=(MinValueValidator(Decimal("0")),))
    spent_at = models.DateField()
    status = models.CharField(max_length=16, choices=ExpenseStatus.choices, default=ExpenseStatus.DECLARED, db_index=True)
    reference = models.CharField(max_length=60, blank=True)
    receipt = models.FileField(upload_to="expenses/receipts/%Y/%m/", blank=True)
    receipt_original_name = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_expenses",
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-spent_at", "-id")
        indexes = [
            models.Index(fields=("project", "spent_at")),
            models.Index(fields=("project", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.label} · {self.amount}"

    @property
    def has_receipt(self) -> bool:
        return bool(self.receipt)
