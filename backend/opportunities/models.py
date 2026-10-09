from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class OpportunityStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    OPEN = "OPEN", "Ouverte"
    CLOSED = "CLOSED", "Clôturée"
    CANCELLED = "CANCELLED", "Annulée"


class ApplicationStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Envoyée"
    IN_REVIEW = "IN_REVIEW", "En étude"
    SHORTLISTED = "SHORTLISTED", "Présélectionnée"
    ACCEPTED = "ACCEPTED", "Acceptée"
    REJECTED = "REJECTED", "Refusée"
    WITHDRAWN = "WITHDRAWN", "Retirée"


class Opportunity(models.Model):
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_opportunities")
    title = models.CharField(max_length=180)
    project_type = models.CharField(max_length=100)
    city = models.CharField(max_length=100, db_index=True)
    budget_min = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=(MinValueValidator(Decimal("0")),))
    budget_max = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=(MinValueValidator(Decimal("0")),))
    description = models.TextField(max_length=5000)
    deadline = models.DateField(db_index=True)
    status = models.CharField(max_length=16, choices=OpportunityStatus.choices, default=OpportunityStatus.DRAFT, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("deadline", "-created_at")
        indexes = [models.Index(fields=("status", "deadline", "city"))]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(budget_min__isnull=True) | models.Q(budget_max__isnull=True) | models.Q(budget_min__lte=models.F("budget_max")),
                name="opportunity_budget_min_lte_max",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.status == OpportunityStatus.OPEN and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title


class Application(models.Model):
    opportunity = models.ForeignKey(Opportunity, on_delete=models.PROTECT, related_name="applications")
    company = models.ForeignKey("companies.CompanyProfile", on_delete=models.PROTECT, related_name="applications")
    message = models.TextField(max_length=5000)
    similar_projects = models.JSONField(default=list, blank=True)
    team_summary = models.CharField(max_length=500, blank=True)
    estimated_budget = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=(MinValueValidator(Decimal("0")),))
    duration_days = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=ApplicationStatus.choices, default=ApplicationStatus.SUBMITTED, db_index=True)
    internal_note = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("opportunity", "company"), name="uniq_opportunity_company_application")]
        indexes = [models.Index(fields=("company", "status", "created_at")), models.Index(fields=("opportunity", "status"))]

    def __str__(self) -> str:
        return f"{self.company.name} · {self.opportunity.title}"
