from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils import timezone


class CompanyProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_profile")
    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True, db_index=True)
    description = models.TextField(max_length=4000, blank=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    services = models.JSONField(default=list, blank=True)
    intervention_areas = models.JSONField(default=list, blank=True)
    years_experience = models.PositiveSmallIntegerField(default=0)
    verified = models.BooleanField(default=False, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    views_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        indexes = [models.Index(fields=("is_published", "verified", "city"))]

    @property
    def profile_completion(self) -> int:
        completed = sum((bool(self.name), bool(self.city), len(self.description.strip()) >= 20, bool(self.services), bool(self.intervention_areas), self.years_experience > 0))
        return round(completed / 6 * 100)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:140] or "entreprise-btp"
            candidate = base
            suffix = 2
            while CompanyProfile.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base[:135]}-{suffix}"
                suffix += 1
            self.slug = candidate
        if self.verified:
            self.is_published = True
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class PortfolioItem(models.Model):
    company = models.ForeignKey(CompanyProfile, on_delete=models.CASCADE, related_name="portfolio")
    title = models.CharField(max_length=160)
    description = models.TextField(max_length=2000, blank=True)
    project_type = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to="companies/portfolio/%Y/%m/", blank=True)
    video_url = models.URLField(blank=True, max_length=500)
    position = models.PositiveSmallIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("position", "-created_at")
        indexes = [models.Index(fields=("company", "is_published", "position"))]

    def __str__(self) -> str:
        return f"{self.company.name} · {self.title}"
