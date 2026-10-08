"""Serializers du parcours entreprise.

Les serializers existants sont **étendus**, pas remplacés :
- `CompanyProfileSerializer` reste la vue publique du catalogue (aucune donnée
  légale n'y est ajoutée) ;
- `CompanyProfileWriteSerializer` accepte simplement les nouveaux champs, tous
  facultatifs, pour ne pas casser les appels existants ;
- les fichiers de vérification ajoutent les vues propriétaire et administration.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.phones import normalize_phone
from companies.models import (
    CompanyDocument,
    CompanyDocumentType,
    CompanyProfile,
    CompanyType,
    CompanyVerificationStatus,
    PortfolioItem,
)


class PortfolioItemSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioItem
        fields = ("id", "title", "description", "project_type", "city", "image", "image_url", "video_url", "position", "created_at")
        read_only_fields = ("id", "created_at", "image_url")

    def get_image_url(self, obj: PortfolioItem) -> str | None:
        return obj.image.url if obj.image else None


class CompanyProfileSerializer(serializers.ModelSerializer):
    profile_completion = serializers.IntegerField(read_only=True)
    portfolio_count = serializers.SerializerMethodField()
    portfolio = PortfolioItemSerializer(many=True, read_only=True)
    verified = serializers.BooleanField(read_only=True)
    is_published = serializers.BooleanField(read_only=True)
    views_count = serializers.IntegerField(read_only=True)

    def get_portfolio_count(self, obj: CompanyProfile) -> int:
        return sum(1 for item in obj.portfolio.all() if item.is_published)

    class Meta:
        model = CompanyProfile
        fields = (
            "id", "user", "name", "slug", "description", "city", "services", "intervention_areas",
            "years_experience", "verified", "is_published", "profile_completion", "portfolio_count", "views_count", "portfolio",
            "created_at", "updated_at",
        )
        read_only_fields = fields


class CompanyProfileOwnerSerializer(CompanyProfileSerializer):
    """Vue propriétaire : ajoute les informations légales et l'état du dossier.

    Ces champs ne sont jamais exposés par le catalogue public
    (`CompanyProfileSerializer`), ni les documents justificatifs.
    """

    verification_status_label = serializers.CharField(source="get_verification_status_display", read_only=True)
    verification_level_label = serializers.CharField(source="get_verification_level_display", read_only=True)
    documents_count = serializers.SerializerMethodField()

    def get_documents_count(self, obj: CompanyProfile) -> int:
        return obj.documents.count()

    class Meta(CompanyProfileSerializer.Meta):
        fields = CompanyProfileSerializer.Meta.fields + (
            "legal_name", "company_type", "sector", "country", "address", "phone", "email", "website",
            "registration_number", "tax_number", "verification_status", "verification_status_label",
            "verification_level", "verification_level_label", "advanced_verified", "verification_submitted_at",
            "verification_reviewed_at", "verification_rejection_reason", "documents_count",
        )
        read_only_fields = fields


class CompanyProfileWriteSerializer(serializers.ModelSerializer):
    services = serializers.ListField(child=serializers.CharField(max_length=80), required=False, allow_empty=True, max_length=20)
    intervention_areas = serializers.ListField(child=serializers.CharField(max_length=100), required=False, allow_empty=True, max_length=20)
    legal_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    company_type = serializers.ChoiceField(choices=CompanyType.choices, required=False, allow_blank=True)
    sector = serializers.CharField(max_length=80, required=False, allow_blank=True)
    country = serializers.CharField(max_length=80, required=False, allow_blank=True)
    address = serializers.CharField(max_length=200, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    website = serializers.URLField(max_length=300, required=False, allow_blank=True)
    registration_number = serializers.CharField(max_length=80, required=False, allow_blank=True)
    tax_number = serializers.CharField(max_length=80, required=False, allow_blank=True)

    class Meta:
        model = CompanyProfile
        fields = (
            "name", "legal_name", "company_type", "sector", "country", "address", "phone", "email", "website",
            "registration_number", "tax_number", "description", "city", "services", "intervention_areas", "years_experience",
        )

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Le nom doit comporter au moins 2 caractères.")
        return cleaned

    def validate_description(self, value: str) -> str:
        return value.strip()

    def validate_city(self, value: str) -> str:
        return value.strip()

    def validate_legal_name(self, value: str) -> str:
        return value.strip()

    def validate_sector(self, value: str) -> str:
        return value.strip()

    def validate_address(self, value: str) -> str:
        return value.strip()

    def validate_country(self, value: str) -> str:
        return value.strip() or "Cameroun"

    def validate_phone(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""
        try:
            return normalize_phone(cleaned)
        except DjangoValidationError as exc:
            raise serializers.ValidationError("Indiquez un numéro au format international, par exemple +237 6 XX XX XX XX.") from exc

    def validate_services(self, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))

    def validate_intervention_areas(self, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class PortfolioItemOwnerSerializer(PortfolioItemSerializer):
    class Meta(PortfolioItemSerializer.Meta):
        fields = PortfolioItemSerializer.Meta.fields + ("is_published",)


class CompanyDocumentSerializer(serializers.ModelSerializer):
    """Pièce du dossier : jamais d'URL de stockage, seulement des métadonnées."""

    document_type_label = serializers.CharField(source="get_document_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    file_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    def get_file_name(self, obj: CompanyDocument) -> str:
        return obj.original_name or obj.file.name.rsplit("/", 1)[-1]

    def get_file_url(self, obj: CompanyDocument) -> str:
        return f"/api/v1/companies/me/documents/{obj.pk}/file/"

    class Meta:
        model = CompanyDocument
        fields = (
            "id", "document_type", "document_type_label", "status", "status_label", "file_name", "file_url",
            "file_size", "content_type", "rejection_reason", "uploaded_at", "reviewed_at", "expires_at",
        )
        read_only_fields = fields


class CompanyDocumentUploadSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=CompanyDocumentType.choices)
    file = serializers.FileField()
    expires_at = serializers.DateField(required=False, allow_null=True)


class CompanyVerificationDecisionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("start_review", "approve", "reject", "request_correction", "suspend"))
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    document_type = serializers.ChoiceField(choices=CompanyDocumentType.choices, required=False, allow_blank=True)
    advanced = serializers.BooleanField(required=False, default=False)


class CompanyReviewQueueSerializer(serializers.ModelSerializer):
    """Vue administration d'un dossier en attente."""

    owner_name = serializers.SerializerMethodField()
    owner_phone = serializers.CharField(source="user.phone", read_only=True)
    owner_email = serializers.CharField(source="user.email", read_only=True)
    status_label = serializers.CharField(source="get_verification_status_display", read_only=True)
    level_label = serializers.CharField(source="get_verification_level_display", read_only=True)
    documents = CompanyDocumentSerializer(many=True, read_only=True)

    def get_owner_name(self, obj: CompanyProfile) -> str:
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.phone

    class Meta:
        model = CompanyProfile
        fields = (
            "id", "name", "legal_name", "slug", "city", "address", "country", "company_type", "sector",
            "registration_number", "tax_number", "phone", "email", "website", "description", "profile_completion",
            "verified", "is_published", "verification_status", "status_label", "verification_level", "level_label",
            "advanced_verified", "verification_submitted_at", "verification_reviewed_at", "verification_rejection_reason",
            "owner_name", "owner_phone", "owner_email", "documents", "created_at",
        )
        read_only_fields = fields
