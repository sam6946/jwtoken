from rest_framework import serializers

from companies.models import CompanyProfile, PortfolioItem


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


class CompanyProfileWriteSerializer(serializers.ModelSerializer):
    services = serializers.ListField(child=serializers.CharField(max_length=80), required=False, allow_empty=True, max_length=20)
    intervention_areas = serializers.ListField(child=serializers.CharField(max_length=100), required=False, allow_empty=True, max_length=20)

    class Meta:
        model = CompanyProfile
        fields = ("name", "description", "city", "services", "intervention_areas", "years_experience")

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Le nom doit comporter au moins 2 caractères.")
        return cleaned

    def validate_description(self, value: str) -> str:
        return value.strip()

    def validate_city(self, value: str) -> str:
        return value.strip()

    def validate_services(self, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))

    def validate_intervention_areas(self, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class PortfolioItemOwnerSerializer(PortfolioItemSerializer):
    class Meta(PortfolioItemSerializer.Meta):
        fields = PortfolioItemSerializer.Meta.fields + ("is_published",)
