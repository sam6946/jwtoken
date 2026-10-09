from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class PlanTier(models.TextChoices):
    FREE = "FREE", "Gratuit"
    PRO = "PRO", "Pro"
    PREMIUM = "PREMIUM", "Premium"


class SubscriptionStatus(models.TextChoices):
    PENDING = "PENDING", "En attente"
    ACTIVE = "ACTIVE", "Active"
    PAST_DUE = "PAST_DUE", "En retard"
    CANCELLED = "CANCELLED", "Annulée"
    EXPIRED = "EXPIRED", "Expirée"


class PaymentStatus(models.TextChoices):
    CREATED = "CREATED", "Créé"
    PENDING = "PENDING", "En attente"
    SUCCEEDED = "SUCCEEDED", "Réussi"
    FAILED = "FAILED", "Échoué"
    CANCELLED = "CANCELLED", "Annulé"
    REFUNDED = "REFUNDED", "Remboursé"


class SubscriptionPlan(models.Model):
    code = models.CharField(max_length=24, unique=True)
    tier = models.CharField(max_length=12, choices=PlanTier.choices)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=300, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2, validators=(MinValueValidator(Decimal("0")),))
    currency = models.CharField(max_length=3, default="XAF")
    billing_period_days = models.PositiveSmallIntegerField(default=30)
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("price", "name")

    def __str__(self) -> str:
        return f"{self.name} · {self.price} {self.currency}"


class Subscription(models.Model):
    company = models.ForeignKey("companies.CompanyProfile", on_delete=models.PROTECT, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=16, choices=SubscriptionStatus.choices, default=SubscriptionStatus.PENDING, db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("company", "status", "ends_at"))]

    @property
    def is_current(self) -> bool:
        now = timezone.now()
        return self.status == SubscriptionStatus.ACTIVE and (self.ends_at is None or self.ends_at > now)

    def __str__(self) -> str:
        return f"{self.company.name} · {self.plan.name}"


class Payment(models.Model):
    class Provider(models.TextChoices):
        MTN_MOMO = "MTN_MOMO", "MTN Mobile Money"
        ORANGE_MONEY = "ORANGE_MONEY", "Orange Money"
        CARD = "CARD", "Carte bancaire"
        MANUAL = "MANUAL", "Manuel"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    subscription = models.ForeignKey(Subscription, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=20, choices=Provider.choices)
    idempotency_key = models.CharField(max_length=128, unique=True)
    provider_reference = models.CharField(max_length=160, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2, validators=(MinValueValidator(Decimal("0")),))
    currency = models.CharField(max_length=3, default="XAF")
    status = models.CharField(max_length=16, choices=PaymentStatus.choices, default=PaymentStatus.CREATED, db_index=True)
    description = models.CharField(max_length=180, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("owner", "status", "created_at"))]

    def __str__(self) -> str:
        return f"{self.amount} {self.currency} · {self.get_status_display()}"


class PaymentTransaction(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="transactions")
    provider_reference = models.CharField(max_length=160, blank=True, db_index=True)
    event_type = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=128, unique=True)
    payload_hash = models.CharField(max_length=64)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("payment", "created_at"))]

    def __str__(self) -> str:
        return f"{self.event_type} · {self.provider_reference}"
