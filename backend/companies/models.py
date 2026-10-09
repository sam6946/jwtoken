from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils import timezone


class CompanyType(models.TextChoices):
    SARL = "SARL", "SARL"
    SA = "SA", "SA"
    SAS = "SAS", "SAS"
    ETS = "ETS", "Établissement"
    EI = "EI", "Entreprise individuelle"
    GIE = "GIE", "GIE"
    COOPERATIVE = "COOPERATIVE", "Coopérative"
    AUTRE = "AUTRE", "Autre"


class CompanyVerificationStatus(models.TextChoices):
    """États du dossier de vérification d'une entreprise.

    DRAFT remplace l'absence de dossier : la société existe (créée à
    l'inscription) mais n'a pas encore soumis ses informations.
    """

    DRAFT = "DRAFT", "Informations à compléter"
    PENDING = "PENDING", "Vérification en attente"
    UNDER_REVIEW = "UNDER_REVIEW", "En cours d’examen"
    VERIFIED = "VERIFIED", "Entreprise vérifiée"
    REJECTED = "REJECTED", "Vérification non validée"
    SUSPENDED = "SUSPENDED", "Vérification suspendue"


class CompanyVerificationLevel(models.TextChoices):
    ACCOUNT = "ACCOUNT", "Compte créé"
    PROFILE = "PROFILE", "Profil complété"
    BUSINESS_VERIFIED = "BUSINESS_VERIFIED", "Entreprise vérifiée"
    ADVANCED = "ADVANCED", "Vérification renforcée"


class CompanyDocumentType(models.TextChoices):
    RCCM = "RCCM", "RCCM"
    NIU = "NIU", "NIU"
    REGISTRATION_CERTIFICATE = "REGISTRATION_CERTIFICATE", "Document d’immatriculation"
    IDENTITY_DOCUMENT = "IDENTITY_DOCUMENT", "Pièce d’identité du représentant légal"
    ADDRESS_PROOF = "ADDRESS_PROOF", "Preuve d’adresse"
    OTHER = "OTHER", "Autre document"


class CompanyDocumentStatus(models.TextChoices):
    PENDING = "PENDING", "À vérifier"
    APPROVED = "APPROVED", "Validé"
    REJECTED = "REJECTED", "À corriger"


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
    # Informations légales et coordonnées professionnelles (facultatives à la
    # création : le dossier de vérification les exige au moment de la soumission).
    legal_name = models.CharField(max_length=160, blank=True)
    company_type = models.CharField(max_length=20, choices=CompanyType.choices, blank=True)
    sector = models.CharField(max_length=80, blank=True, db_index=True)
    country = models.CharField(max_length=80, default="Cameroun")
    address = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(max_length=300, blank=True)
    registration_number = models.CharField(max_length=80, blank=True)
    tax_number = models.CharField(max_length=80, blank=True)
    # Dossier de vérification KEMTA.
    verification_status = models.CharField(max_length=20, choices=CompanyVerificationStatus.choices, default=CompanyVerificationStatus.DRAFT, db_index=True)
    verification_level = models.CharField(max_length=20, choices=CompanyVerificationLevel.choices, default=CompanyVerificationLevel.ACCOUNT, db_index=True)
    advanced_verified = models.BooleanField(default=False)
    verification_submitted_at = models.DateTimeField(null=True, blank=True)
    verification_reviewed_at = models.DateTimeField(null=True, blank=True)
    verification_rejection_reason = models.CharField(max_length=500, blank=True)
    verification_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="company_verifications_reviewed"
    )
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

    PROMOTABLE_STATUSES = frozenset({
        CompanyVerificationStatus.DRAFT,
        CompanyVerificationStatus.PENDING,
        CompanyVerificationStatus.UNDER_REVIEW,
    })

    @property
    def legal_details_complete(self) -> bool:
        """Champs exigés pour soumettre le dossier de vérification."""
        return all((
            bool((self.legal_name or self.name).strip()),
            bool(self.company_type),
            bool(self.sector.strip()),
            bool(self.city.strip()),
            bool(self.address.strip()),
            bool(self.country.strip()),
        ))

    @property
    def verification_in_review(self) -> bool:
        return self.verification_status in {CompanyVerificationStatus.PENDING, CompanyVerificationStatus.UNDER_REVIEW}

    def compute_verification_level(self) -> str:
        if self.verification_status == CompanyVerificationStatus.VERIFIED:
            return CompanyVerificationLevel.ADVANCED if self.advanced_verified else CompanyVerificationLevel.BUSINESS_VERIFIED
        if self.legal_details_complete:
            return CompanyVerificationLevel.PROFILE
        return CompanyVerificationLevel.ACCOUNT

    def sync_verification_fields(self) -> None:
        """Garde `verified`, `is_published` et le niveau cohérents avec le dossier.

        Le booléen `verified` reste la source de vérité du catalogue public et des
        permissions existantes : il est seulement dérivé du nouveau statut, jamais
        remplacé.
        """
        # Compatibilité ascendante : du code existant peut encore poser
        # `verified = True` sans toucher au dossier ; on promeut alors le statut.
        # Une décision explicite (refus, suspension) n'est jamais écrasée.
        if self.verified and self.verification_status in self.PROMOTABLE_STATUSES:
            self.verification_status = CompanyVerificationStatus.VERIFIED
            self.legal_name = self.legal_name or self.name
        if self.verification_status == CompanyVerificationStatus.VERIFIED:
            self.verified = True
        if self.verification_status in {
            CompanyVerificationStatus.REJECTED,
            CompanyVerificationStatus.SUSPENDED,
            CompanyVerificationStatus.DRAFT,
        }:
            self.verified = False
        if self.verification_status == CompanyVerificationStatus.SUSPENDED:
            self.is_published = False
        self.verification_level = self.compute_verification_level()

    def save(self, *args, **kwargs):
        self.sync_verification_fields()
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


class CompanyDocument(models.Model):
    """Pièce justificative du dossier de vérification d'une entreprise.

    Les fichiers sont privés : ils ne sont servis que par un endpoint authentifié
    contrôlant les droits (propriétaire du dossier ou équipe KEMTA), jamais par
    l'URL de stockage.
    """

    company = models.ForeignKey(CompanyProfile, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=32, choices=CompanyDocumentType.choices, db_index=True)
    file = models.FileField(upload_to="companies/documents/%Y/%m/")
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=120, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=CompanyDocumentStatus.choices, default=CompanyDocumentStatus.PENDING, db_index=True)
    rejection_reason = models.CharField(max_length=500, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="company_documents_reviewed"
    )
    expires_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("document_type", "-uploaded_at")
        indexes = [models.Index(fields=("company", "document_type", "status"))]
        constraints = [
            # Un seul document par type imposé ; les pièces « autres » restent libres.
            models.UniqueConstraint(
                fields=("company", "document_type"),
                condition=~models.Q(document_type="OTHER"),
                name="uniq_company_document_type",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.company.name} · {self.get_document_type_display()}"
