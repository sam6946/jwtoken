import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class ServiceType(models.TextChoices):
    BUILD = "BUILD", "Suivi de chantier"
    TAKEOVER = "TAKEOVER", "Suivi d’un chantier existant"
    MAINTENANCE = "MAINTENANCE", "Entretien immobilier"
    OTHER = "OTHER", "Autre besoin"


class ServiceRequestStatus(models.TextChoices):
    NEW = "NEW", "Nouvelle"
    IN_REVIEW = "IN_REVIEW", "En étude"
    CONTACTED = "CONTACTED", "Contactée"
    CONVERTED = "CONVERTED", "Projet créé"
    CLOSED = "CLOSED", "Clôturée"


def generate_request_code() -> str:
    return f"KEMTA-REQ-{secrets.token_hex(3).upper()}"


class ServiceRequest(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="service_requests",
    )
    request_code = models.CharField(max_length=24, unique=True, default=generate_request_code, editable=False)
    service_type = models.CharField(max_length=20, choices=ServiceType.choices, db_index=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=16, db_index=True)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    project_type = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    related_project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="service_requests",
        help_text="Projet déjà suivi par KEMTA auquel se rattache cette demande.",
    )
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=ServiceRequestStatus.choices, default=ServiceRequestStatus.NEW, db_index=True)
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "created_at")),
            models.Index(fields=("owner", "created_at")),
            models.Index(fields=("service_type", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.request_code} · {self.get_service_type_display()}"


class ServiceRequestAttachment(models.Model):
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="service-requests/%Y/%m/")
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return self.original_name
