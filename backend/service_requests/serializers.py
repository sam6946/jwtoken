from rest_framework import serializers

from accounts.phones import normalize_phone
from projects.models import Project
from service_requests.models import ServiceRequest


class ServiceRequestCreateSerializer(serializers.ModelSerializer):
    metadata = serializers.JSONField(required=False)
    related_project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
        allow_null=True,
    )
    related_project_name = serializers.SerializerMethodField()

    class Meta:
        model = ServiceRequest
        fields = (
            "id",
            "request_code",
            "service_type",
            "first_name",
            "last_name",
            "phone",
            "email",
            "city",
            "project_type",
            "description",
            "related_project",
            "related_project_name",
            "metadata",
            "status",
            "created_at",
        )
        read_only_fields = ("id", "request_code", "status", "created_at", "related_project_name")

    def get_related_project_name(self, obj: ServiceRequest) -> str | None:
        return obj.related_project.name if obj.related_project_id else None

    def validate_related_project(self, value):
        """Une demande ne peut viser que l’un de ses propres projets."""
        if value is None:
            return value
        user = self.context["request"].user
        if not user.is_authenticated:
            raise serializers.ValidationError("Connectez-vous pour rattacher une demande à un projet.")
        if value.owner_id != user.id:
            raise serializers.ValidationError("Vous ne pouvez rattacher une demande qu’à votre propre projet.")
        return value

    def validate_phone(self, value: str) -> str:
        return normalize_phone(value)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Les détails du projet doivent être un objet JSON.")
        if len(value) > 40:
            raise serializers.ValidationError("Le nombre de détails est trop important.")
        return value

    def validate_description(self, value: str) -> str:
        if len(value) > 5000:
            raise serializers.ValidationError("Le message ne peut pas dépasser 5 000 caractères.")
        return value


class ServiceRequestAdminSerializer(serializers.ModelSerializer):
    service_type_label = serializers.CharField(source="get_service_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ServiceRequest
        fields = "__all__"
        read_only_fields = ("request_code", "created_at", "updated_at")
