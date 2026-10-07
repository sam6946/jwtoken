from django.utils import timezone
from rest_framework import serializers

from opportunities.models import Application, ApplicationStatus, Opportunity, OpportunityStatus


class OpportunitySerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Opportunity
        fields = (
            "id", "title", "project_type", "city", "budget_min", "budget_max", "description",
            "deadline", "status", "published_at", "created_at", "created_by_name",
        )
        read_only_fields = ("id", "published_at", "created_at", "created_by_name")

    def get_created_by_name(self, obj: Opportunity) -> str:
        return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()

    def validate(self, attrs):
        deadline = attrs.get("deadline", getattr(self.instance, "deadline", None))
        status_value = attrs.get("status", getattr(self.instance, "status", OpportunityStatus.DRAFT))
        if status_value == OpportunityStatus.OPEN and deadline and deadline < timezone.localdate():
            raise serializers.ValidationError({"deadline": "La date limite doit être future pour ouvrir une opportunité."})
        return attrs


class ApplicationSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    opportunity_title = serializers.CharField(source="opportunity.title", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Application
        fields = (
            "id", "opportunity", "opportunity_title", "company", "company_name", "message",
            "similar_projects", "team_summary", "estimated_budget", "duration_days", "status", "status_label",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "company", "company_name", "opportunity_title", "status", "status_label", "created_at", "updated_at")

    def validate_similar_projects(self, value):
        if not isinstance(value, list) or len(value) > 20:
            raise serializers.ValidationError("La liste de projets similaires est invalide.")
        cleaned = []
        for entry in value:
            if not isinstance(entry, str) or len(entry.strip()) > 180:
                raise serializers.ValidationError("Chaque projet similaire doit être une courte description.")
            if entry.strip():
                cleaned.append(entry.strip())
        return cleaned

    def validate(self, attrs):
        opportunity = attrs.get("opportunity")
        if opportunity and (opportunity.status != OpportunityStatus.OPEN or opportunity.deadline < timezone.localdate()):
            raise serializers.ValidationError({"opportunity": "Cette opportunité n’accepte plus de candidatures."})
        if len(attrs.get("message", "").strip()) < 8:
            raise serializers.ValidationError({"message": "Présentez votre approche en quelques mots."})
        return attrs


class ApplicationStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ("status", "internal_note")

    def validate_status(self, value: str) -> str:
        if value not in ApplicationStatus.values:
            raise serializers.ValidationError("Statut de candidature invalide.")
        return value
