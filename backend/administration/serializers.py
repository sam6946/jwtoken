from rest_framework import serializers

from accounts.models import User, UserRole
from administration.models import PlatformSetting, SupportMessage, SupportTicket
from common.models import AuditLog
from payments.models import Payment, Subscription, SubscriptionPlan
from projects.models import FieldMission, FieldReport, Project, ProjectIssue


class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    last_activity_at = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "phone",
            "email",
            "role",
            "phone_verified",
            "is_active",
            "is_staff",
            "created_at",
            "last_activity_at",
        )
        read_only_fields = fields

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.phone

    def get_last_activity_at(self, obj):
        return getattr(obj, "last_audit_at", None)


class AdminProjectSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()
    manager_name = serializers.SerializerMethodField()
    open_issues = serializers.IntegerField(read_only=True)

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "city",
            "project_type",
            "status",
            "progress",
            "current_phase",
            "planned_start",
            "planned_end",
            "last_report_at",
            "owner_name",
            "manager_name",
            "open_issues",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def _name(self, user):
        return f"{user.first_name} {user.last_name}".strip() if user else None

    def get_owner_name(self, obj):
        return self._name(obj.owner)

    def get_manager_name(self, obj):
        return self._name(obj.manager)


class AdminMissionSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = FieldMission
        fields = (
            "id",
            "title",
            "project",
            "project_name",
            "assigned_to",
            "assigned_to_name",
            "mission_type",
            "status",
            "scheduled_start",
            "started_at",
            "completed_at",
            "created_at",
        )
        read_only_fields = fields

    def get_assigned_to_name(self, obj):
        return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}".strip()


class AdminReportSerializer(serializers.ModelSerializer):
    mission_title = serializers.CharField(source="mission.title", read_only=True)
    project_name = serializers.CharField(source="mission.project.name", read_only=True)
    submitted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FieldReport
        fields = (
            "id",
            "mission",
            "mission_title",
            "project_name",
            "submitted_by_name",
            "status",
            "progress_percentage",
            "submitted_at",
            "reviewed_at",
            "review_comment",
            "updated_at",
        )
        read_only_fields = fields

    def get_submitted_by_name(self, obj):
        return f"{obj.submitted_by.first_name} {obj.submitted_by.last_name}".strip()


class AdminIssueSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    reported_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ProjectIssue
        fields = (
            "id",
            "project",
            "project_name",
            "title",
            "priority",
            "status",
            "reported_by_name",
            "created_at",
            "resolved_at",
        )
        read_only_fields = fields

    def get_reported_by_name(self, obj):
        return f"{obj.reported_by.first_name} {obj.reported_by.last_name}".strip()


class AdminPaymentSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()
    subscription_plan = serializers.CharField(
        source="subscription.plan.name", read_only=True, default=None
    )

    class Meta:
        model = Payment
        fields = (
            "id",
            "owner_name",
            "provider",
            "provider_reference",
            "amount",
            "currency",
            "status",
            "description",
            "subscription_plan",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_owner_name(self, obj):
        return (
            f"{obj.owner.first_name} {obj.owner.last_name}".strip() or obj.owner.phone
        )


class AdminSubscriptionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = Subscription
        fields = (
            "id",
            "company",
            "company_name",
            "plan",
            "plan_name",
            "status",
            "starts_at",
            "ends_at",
            "cancelled_at",
            "created_at",
        )
        read_only_fields = fields


class AdminPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = (
            "id",
            "code",
            "tier",
            "name",
            "description",
            "price",
            "currency",
            "billing_period_days",
            "features",
            "is_active",
            "updated_at",
        )
        read_only_fields = fields


class AdminAuditSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "event",
            "actor",
            "actor_name",
            "object_type",
            "object_id",
            "metadata",
            "request_id",
            "created_at",
        )
        read_only_fields = fields

    def get_actor_name(self, obj):
        return (
            f"{obj.actor.first_name} {obj.actor.last_name}".strip()
            if obj.actor
            else None
        )


class SupportMessageSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = SupportMessage
        fields = ("id", "author", "author_name", "body", "is_internal", "created_at")
        read_only_fields = ("id", "author", "author_name", "created_at")

    def get_author_name(self, obj):
        return f"{obj.author.first_name} {obj.author.last_name}".strip()


class SupportTicketSerializer(serializers.ModelSerializer):
    requester_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    messages = SupportMessageSerializer(many=True, read_only=True)

    class Meta:
        model = SupportTicket
        fields = (
            "id",
            "requester",
            "requester_name",
            "assigned_to",
            "assigned_to_name",
            "category",
            "subject",
            "description",
            "priority",
            "status",
            "resolution_summary",
            "resolved_at",
            "created_at",
            "updated_at",
            "messages",
        )
        read_only_fields = (
            "id",
            "requester_name",
            "assigned_to_name",
            "resolved_at",
            "created_at",
            "updated_at",
            "messages",
        )

    def get_requester_name(self, obj):
        return (
            f"{obj.requester.first_name} {obj.requester.last_name}".strip()
            or obj.requester.phone
        )

    def get_assigned_to_name(self, obj):
        return (
            f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}".strip()
            if obj.assigned_to
            else None
        )


class PlatformSettingSerializer(serializers.ModelSerializer):
    """Les secrets restent dans la configuration de déploiement, jamais dans cette table."""

    class Meta:
        model = PlatformSetting
        fields = ("id", "key", "value", "description", "updated_at")
        read_only_fields = ("id", "updated_at")

    def validate_key(self, value):
        normalized = value.lower()
        forbidden = (
            "secret",
            "password",
            "token",
            "api_key",
            "apikey",
            "credential",
            "private_key",
        )
        if any(marker in normalized for marker in forbidden):
            raise serializers.ValidationError(
                "Les secrets doivent rester dans la configuration de déploiement."
            )
        return value
