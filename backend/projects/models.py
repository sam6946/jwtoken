from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
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


class Evidence(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = "PENDING", "À vérifier"
        VERIFIED = "VERIFIED", "Vérifiée"
        REJECTED = "REJECTED", "Refusée"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="evidences")
    phase = models.ForeignKey(ProjectPhase, null=True, blank=True, on_delete=models.SET_NULL, related_name="evidences")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_evidences")
    title = models.CharField(max_length=160)
    caption = models.TextField(blank=True)
    location = models.CharField(max_length=180, blank=True)
    image = models.ImageField(upload_to="evidence/original/%Y/%m/")
    thumbnail = models.ImageField(upload_to="evidence/thumbnail/%Y/%m/", blank=True)
    medium = models.ImageField(upload_to="evidence/medium/%Y/%m/", blank=True)
    large = models.ImageField(upload_to="evidence/large/%Y/%m/", blank=True)
    verification_status = models.CharField(max_length=16, choices=VerificationStatus.choices, default=VerificationStatus.PENDING, db_index=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("project", "verification_status", "created_at"))]

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
    """Dépense engagée sur un chantier, avec son justificatif.

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
