from rest_framework import serializers

from service_requests.models import ServiceRequest


class DashboardServiceRequestSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()
    service_type_label = serializers.CharField(source="get_service_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    related_project_name = serializers.SerializerMethodField()

    class Meta:
        model = ServiceRequest
        fields = (
            "id", "request_code", "service_type", "service_type_label", "status", "status_label", "city",
            "owner_name", "related_project", "related_project_name", "created_at",
        )
        read_only_fields = fields

    def get_owner_name(self, obj: ServiceRequest) -> str:
        if obj.owner_id is None:
            return f"{obj.first_name} {obj.last_name}".strip()
        return f"{obj.owner.first_name} {obj.owner.last_name}".strip()

    def get_related_project_name(self, obj: ServiceRequest) -> str | None:
        return obj.related_project.name if obj.related_project_id else None
