from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationType(models.TextChoices):
    PROJECT = "PROJECT", "Projet"
    TASK = "TASK", "Tâche"
    EVIDENCE = "EVIDENCE", "Preuve terrain"
    PAYMENT = "PAYMENT", "Paiement"
    SUBSCRIPTION = "SUBSCRIPTION", "Abonnement"
    APPLICATION = "APPLICATION", "Candidature"
    OPPORTUNITY = "OPPORTUNITY", "Opportunité"
    SECURITY = "SECURITY", "Sécurité"
    GENERAL = "GENERAL", "Général"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices, default=NotificationType.GENERAL, db_index=True)
    title = models.CharField(max_length=180)
    body = models.CharField(max_length=500, blank=True)
    action_url = models.CharField(max_length=300, blank=True)
    data = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=128, null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("user", "read_at", "created_at"))]
        constraints = [
            models.UniqueConstraint(fields=("user", "dedupe_key"), condition=models.Q(dedupe_key__isnull=False), name="uniq_notification_dedupe_key"),
        ]

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def __str__(self) -> str:
        return f"{self.title} → {self.user_id}"
