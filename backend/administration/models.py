from django.conf import settings
from django.db import models
from django.utils import timezone


class SupportTicketStatus(models.TextChoices):
    OPEN = "OPEN", "Ouvert"
    IN_PROGRESS = "IN_PROGRESS", "En traitement"
    WAITING_CUSTOMER = "WAITING_CUSTOMER", "En attente du client"
    RESOLVED = "RESOLVED", "Résolu"
    CLOSED = "CLOSED", "Clos"


class SupportTicketPriority(models.TextChoices):
    LOW = "LOW", "Faible"
    MEDIUM = "MEDIUM", "Moyenne"
    HIGH = "HIGH", "Élevée"
    CRITICAL = "CRITICAL", "Critique"


class SupportTicket(models.Model):
    """Support transversal, distinct des incidents techniques d'un chantier."""

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_support_tickets",
    )
    category = models.CharField(max_length=80, default="GENERAL", db_index=True)
    subject = models.CharField(max_length=180)
    description = models.TextField()
    priority = models.CharField(
        max_length=16,
        choices=SupportTicketPriority.choices,
        default=SupportTicketPriority.MEDIUM,
        db_index=True,
    )
    status = models.CharField(
        max_length=24,
        choices=SupportTicketStatus.choices,
        default=SupportTicketStatus.OPEN,
        db_index=True,
    )
    resolution_summary = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=("status", "priority", "created_at")),
            models.Index(fields=("requester", "status")),
        ]


class SupportMessage(models.Model):
    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="messages"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_messages",
    )
    body = models.TextField()
    is_internal = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=("ticket", "is_internal", "created_at"))]


class PlatformSetting(models.Model):
    """Paramètre non secret, administré exclusivement par un Super Admin."""

    key = models.CharField(max_length=80, unique=True)
    value = models.JSONField(default=dict, blank=True)
    description = models.CharField(max_length=300, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_platform_settings",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("key",)
