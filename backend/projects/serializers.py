from rest_framework import serializers

from service_requests.models import ServiceRequest

from accounts.models import KemtaPermission, User, UserRole
from accounts.permissions import has_kemta_permission
from projects.models import (
    Evidence,
    EvidenceType,
    ExpenseStatus,
    FieldMission,
    FieldReport,
    FieldReportStatus,
    MissionStatus,
    Project,
    ProjectAssignment,
    ProjectExpense,
    ProjectIssue,
    ProjectPhase,
    ProjectReport,
    ProjectTask,
)


class ProjectPhaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPhase
        fields = ("id", "name", "position", "status", "planned_start", "planned_end", "completed_at")
        read_only_fields = fields


class ProjectSerializer(serializers.ModelSerializer):
    phases = ProjectPhaseSerializer(many=True, read_only=True)
    owner = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), write_only=True)
    field_agents = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=UserRole.FIELD_AGENT), many=True, required=False)

    class Meta:
        model = Project
        fields = (
            "id", "owner", "name", "city", "project_type", "status", "progress", "current_phase",
            "budget_total", "budget_spent", "planned_start", "planned_end", "last_report_at", "phases", "field_agents",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "last_report_at", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated and not has_kemta_permission(user, KemtaPermission.VIEW_FINANCE):
            self.fields.pop("budget_total", None)
            self.fields.pop("budget_spent", None)


class ProjectTaskSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    phase_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = ProjectTask
        fields = (
            "id", "project", "project_name", "phase", "phase_name", "assigned_to", "assigned_to_name",
            "title", "description", "status", "due_date", "created_at", "updated_at",
        )
        read_only_fields = ("id", "project_name", "phase_name", "assigned_to_name", "created_at", "updated_at")

    def get_phase_name(self, obj: ProjectTask) -> str | None:
        return obj.phase.name if obj.phase_id else None

    def get_assigned_to_name(self, obj: ProjectTask) -> str | None:
        if obj.assigned_to_id is None:
            return None
        return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}".strip()


class ProjectExpenseSerializer(serializers.ModelSerializer):
    """Dépense d'un chantier. Le reçu est exposé par une URL d'API contrôlée, jamais par /media/."""

    category_label = serializers.CharField(source="get_category_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    has_receipt = serializers.BooleanField(read_only=True)
    receipt_url = serializers.SerializerMethodField()
    recorded_by_name = serializers.SerializerMethodField()
    # Le fichier s'envoie par ce champ mais n'est jamais relu ici : la consultation passe
    # exclusivement par `receipt_url`, qui vérifie les droits sur le projet.
    receipt = serializers.FileField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = ProjectExpense
        fields = (
            "id", "project", "label", "category", "category_label", "amount", "spent_at", "status", "status_label",
            "reference", "notes", "receipt", "has_receipt", "receipt_url", "recorded_by_name", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "category_label", "status_label", "has_receipt", "receipt_url", "recorded_by_name", "created_at", "updated_at",
        )

    def get_receipt_url(self, obj: ProjectExpense) -> str | None:
        """Chemin relatif à la racine de l'API, comme les autres routes consommées par le client."""
        if not obj.receipt:
            return None
        return f"/project-expenses/{obj.pk}/receipt/"

    def get_recorded_by_name(self, obj: ProjectExpense) -> str | None:
        if obj.recorded_by_id is None:
            return None
        return f"{obj.recorded_by.first_name} {obj.recorded_by.last_name}".strip() or obj.recorded_by.phone

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le montant d’une dépense doit être supérieur à zéro.")
        return value

    def validate_receipt(self, value):
        if value is None:
            return value
        if value.size > 8 * 1024 * 1024:
            raise serializers.ValidationError("Un justificatif ne peut pas dépasser 8 Mo.")
        name = (getattr(value, "name", "") or "").lower()
        if not name.endswith((".pdf", ".jpg", ".jpeg", ".png", ".webp")):
            raise serializers.ValidationError("Le justificatif doit être un PDF ou une image (JPG, PNG, WebP).")
        return value


class ServiceRequestSummarySerializer(serializers.ModelSerializer):
    """Demande liée à un projet, telle que vue par son propriétaire."""

    service_type_label = serializers.CharField(source="get_service_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    is_origin = serializers.SerializerMethodField()

    class Meta:
        model = ServiceRequest
        fields = ("id", "request_code", "service_type", "service_type_label", "status", "status_label", "description", "created_at", "is_origin")
        read_only_fields = fields

    def get_is_origin(self, obj) -> bool:
        project = self.context.get("project")
        return bool(project is not None and project.service_request_id == obj.pk)


class ProjectDetailSerializer(ProjectSerializer):
    """Vue complète d'un projet : budget, dépenses, reçus et demandes liées."""

    expenses = serializers.SerializerMethodField()
    service_requests = serializers.SerializerMethodField()
    budget = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ("owner_name", "expenses", "service_requests", "budget")

    def _can_view_finance(self) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and has_kemta_permission(user, KemtaPermission.VIEW_FINANCE))

    def get_owner_name(self, obj: Project) -> str:
        return f"{obj.owner.first_name} {obj.owner.last_name}".strip() or obj.owner.phone

    def get_expenses(self, obj: Project):
        if not self._can_view_finance():
            return []
        expenses = obj.expenses.select_related("recorded_by").all()
        return ProjectExpenseSerializer(expenses, many=True, context=self.context).data

    def get_service_requests(self, obj: Project):
        """Demandes du chantier : celles rattachées, plus la demande d’origine (sans doublon)."""
        requests = {item.pk: item for item in obj.service_requests.select_related("owner").all()}
        if obj.service_request_id and obj.service_request_id not in requests:
            requests[obj.service_request_id] = obj.service_request
        ordered = sorted(requests.values(), key=lambda item: item.created_at, reverse=True)
        return ServiceRequestSummarySerializer(ordered, many=True, context={**self.context, "project": obj}).data

    def get_budget(self, obj: Project):
        if not self._can_view_finance():
            return None
        expenses = list(obj.expenses.all())
        declared = sum((expense.amount for expense in expenses), start=0)
        justified = sum((expense.amount for expense in expenses if expense.status == ExpenseStatus.VALIDATED), start=0)
        total = obj.budget_total
        spent = obj.budget_spent if obj.budget_spent is not None else declared
        remaining = None if total is None else max(total - spent, 0)
        return {
            "total": str(total) if total is not None else None,
            "spent": str(spent) if spent is not None else None,
            "remaining": str(remaining) if remaining is not None else None,
            "expenses_total": str(declared),
            "justified_total": str(justified),
            "expense_count": len(expenses),
            "receipt_count": sum(1 for expense in expenses if expense.receipt),
            "currency": "XAF",
        }


class EvidenceSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    medium_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source="project.name", read_only=True)
    phase_name = serializers.SerializerMethodField()
    mission_title = serializers.CharField(source="mission.title", read_only=True)
    issue_title = serializers.CharField(source="issue.title", read_only=True)

    class Meta:
        model = Evidence
        fields = (
            "id", "project", "project_name", "phase", "phase_name", "mission", "mission_title", "issue", "issue_title",
            "uploaded_by", "uploaded_by_name", "title", "caption", "location", "evidence_type", "image", "video",
            "image_url", "video_url", "thumbnail_url", "medium_url", "latitude", "longitude", "verification_status",
            "taken_at", "client_reference", "created_at",
        )
        read_only_fields = (
            "id", "uploaded_by", "uploaded_by_name", "image_url", "video_url", "thumbnail_url", "medium_url",
            "verification_status", "created_at",
        )
        extra_kwargs = {
            "image": {"required": False, "allow_null": True},
            "video": {"required": False, "allow_null": True},
            "client_reference": {"required": False},
        }

    def get_image_url(self, obj: Evidence) -> str | None:
        return obj.image.url if obj.image else None

    def get_video_url(self, obj: Evidence) -> str | None:
        return obj.video.url if obj.video else None

    def get_thumbnail_url(self, obj: Evidence) -> str | None:
        return obj.thumbnail.url if obj.thumbnail else None

    def get_medium_url(self, obj: Evidence) -> str | None:
        return obj.medium.url if obj.medium else None

    def get_uploaded_by_name(self, obj: Evidence) -> str:
        return f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}".strip() or obj.uploaded_by.phone

    def get_phase_name(self, obj: Evidence) -> str | None:
        return obj.phase.name if obj.phase_id else None

    def validate_image(self, value):
        if value and value.size > 8 * 1024 * 1024:
            raise serializers.ValidationError("Une photo terrain ne peut pas dépasser 8 Mo.")
        return value

    def validate_video(self, value):
        if value and value.size > 30 * 1024 * 1024:
            raise serializers.ValidationError("Une vidéo terrain ne peut pas dépasser 30 Mo.")
        if value:
            name = (getattr(value, "name", "") or "").lower()
            if not name.endswith((".mp4", ".mov", ".webm")):
                raise serializers.ValidationError("La vidéo doit être au format MP4, MOV ou WebM.")
        return value

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        project = attrs.get("project", getattr(instance, "project", None))
        phase = attrs.get("phase", getattr(instance, "phase", None))
        mission = attrs.get("mission", getattr(instance, "mission", None))
        issue = attrs.get("issue", getattr(instance, "issue", None))
        evidence_type = attrs.get("evidence_type", getattr(instance, "evidence_type", EvidenceType.PHOTO))
        image = attrs.get("image", getattr(instance, "image", None))
        video = attrs.get("video", getattr(instance, "video", None))
        if phase and project and phase.project_id != project.id:
            raise serializers.ValidationError({"phase": "Cette étape n’appartient pas au projet indiqué."})
        if mission and project and mission.project_id != project.id:
            raise serializers.ValidationError({"mission": "Cette mission n’appartient pas au projet indiqué."})
        if issue and project and issue.project_id != project.id:
            raise serializers.ValidationError({"issue": "Ce problème n’appartient pas au projet indiqué."})
        if evidence_type == EvidenceType.PHOTO and not image:
            raise serializers.ValidationError({"image": "Une photo est requise pour ce type de preuve."})
        if evidence_type == EvidenceType.VIDEO and not video:
            raise serializers.ValidationError({"video": "Une vidéo est requise pour ce type de preuve."})
        return attrs


class ProjectReportSerializer(serializers.ModelSerializer):
    document_url = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = ProjectReport
        fields = ("id", "project", "author", "author_name", "title", "summary", "period_start", "period_end", "document", "document_url", "created_at")
        read_only_fields = ("id", "author", "author_name", "document_url", "created_at")

    def get_document_url(self, obj: ProjectReport) -> str | None:
        return obj.document.url if obj.document else None

    def get_author_name(self, obj: ProjectReport) -> str:
        return f"{obj.author.first_name} {obj.author.last_name}".strip()


def _display_name(user) -> str:
    return f"{user.first_name} {user.last_name}".strip() or user.phone


def _validate_checklist(value):
    if not isinstance(value, list):
        raise serializers.ValidationError("La checklist doit être une liste.")
    if len(value) > 60:
        raise serializers.ValidationError("Une mission ne peut pas contenir plus de 60 points de checklist.")
    for item in value:
        if not isinstance(item, dict) or not str(item.get("id", "")).strip() or not str(item.get("label", "")).strip():
            raise serializers.ValidationError("Chaque point de checklist doit contenir un identifiant et un libellé.")
    return value


class ProjectAssignmentSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    assigned_by_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ProjectAssignment
        fields = (
            "id", "project", "project_name", "user", "user_name", "role", "status", "assigned_by", "assigned_by_name",
            "start_date", "end_date", "created_at", "updated_at",
        )
        read_only_fields = ("id", "assigned_by", "assigned_by_name", "project_name", "created_at", "updated_at")

    def get_user_name(self, obj):
        return _display_name(obj.user)

    def get_assigned_by_name(self, obj):
        return _display_name(obj.assigned_by) if obj.assigned_by_id else None

    def validate_user(self, value):
        if value.role != UserRole.FIELD_AGENT:
            raise serializers.ValidationError("Seul un compte Agent terrain peut être affecté à une mission.")
        return value

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "La date de fin ne peut pas précéder la date de début."})
        return attrs


class FieldMissionSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    phase_name = serializers.CharField(source="phase.name", read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    mission_type_label = serializers.CharField(source="get_mission_type_display", read_only=True)
    report_status = serializers.CharField(source="field_report.status", read_only=True, default=None)

    class Meta:
        model = FieldMission
        fields = (
            "id", "project", "project_name", "phase", "phase_name", "task", "assigned_to", "assigned_to_name",
            "created_by", "created_by_name", "title", "description", "mission_type", "mission_type_label", "status", "status_label",
            "scheduled_start", "scheduled_end", "location", "instructions", "checklist", "requires_geo_confirmation",
            "start_latitude", "start_longitude", "location_confirmed_at", "started_at", "completed_at", "revision_reason",
            "last_sync_at", "report_status", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "created_by", "created_by_name", "project_name", "phase_name", "assigned_to_name", "status", "status_label",
            "mission_type_label", "start_latitude", "start_longitude", "location_confirmed_at", "started_at", "completed_at",
            "revision_reason", "last_sync_at", "report_status", "created_at", "updated_at",
        )

    def get_assigned_to_name(self, obj):
        return _display_name(obj.assigned_to)

    def get_created_by_name(self, obj):
        return _display_name(obj.created_by)

    def validate_checklist(self, value):
        return _validate_checklist(value)

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        project = attrs.get("project", getattr(instance, "project", None))
        phase = attrs.get("phase", getattr(instance, "phase", None))
        task = attrs.get("task", getattr(instance, "task", None))
        assigned_to = attrs.get("assigned_to", getattr(instance, "assigned_to", None))
        scheduled_start = attrs.get("scheduled_start", getattr(instance, "scheduled_start", None))
        scheduled_end = attrs.get("scheduled_end", getattr(instance, "scheduled_end", None))
        if phase and project and phase.project_id != project.id:
            raise serializers.ValidationError({"phase": "Cette étape n’appartient pas au projet indiqué."})
        if task and project and task.project_id != project.id:
            raise serializers.ValidationError({"task": "Cette tâche n’appartient pas au projet indiqué."})
        if assigned_to and assigned_to.role != UserRole.FIELD_AGENT:
            raise serializers.ValidationError({"assigned_to": "Une mission doit être confiée à un Agent terrain."})
        if scheduled_start and scheduled_end and scheduled_end < scheduled_start:
            raise serializers.ValidationError({"scheduled_end": "La fin prévue ne peut pas précéder le début."})
        return attrs


class FieldReportSerializer(serializers.ModelSerializer):
    mission_title = serializers.CharField(source="mission.title", read_only=True)
    project = serializers.IntegerField(source="mission.project_id", read_only=True)
    project_name = serializers.CharField(source="mission.project.name", read_only=True)
    submitted_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = FieldReport
        fields = (
            "id", "mission", "mission_title", "project", "project_name", "submitted_by", "submitted_by_name", "summary",
            "observations", "progress_percentage", "checklist_results", "status", "status_label", "review_comment",
            "reviewed_by", "reviewed_by_name", "submitted_at", "reviewed_at", "client_reference", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "project", "project_name", "submitted_by", "submitted_by_name", "status", "status_label", "review_comment",
            "reviewed_by", "reviewed_by_name", "submitted_at", "reviewed_at", "created_at", "updated_at",
        )
        extra_kwargs = {"client_reference": {"required": False}}

    def get_submitted_by_name(self, obj):
        return _display_name(obj.submitted_by)

    def get_reviewed_by_name(self, obj):
        return _display_name(obj.reviewed_by) if obj.reviewed_by_id else None

    def validate_checklist_results(self, value):
        return _validate_checklist(value)

    def validate_mission(self, mission):
        if mission.status not in {MissionStatus.IN_PROGRESS, MissionStatus.REVISION_REQUIRED}:
            raise serializers.ValidationError("Un rapport ne peut être préparé que pour une mission en cours ou à corriger.")
        return mission


class ProjectIssueSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    mission_title = serializers.CharField(source="mission.title", read_only=True)
    reported_by_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ProjectIssue
        fields = (
            "id", "project", "project_name", "mission", "mission_title", "reported_by", "reported_by_name", "assigned_to",
            "assigned_to_name", "title", "description", "priority", "priority_label", "status", "status_label", "resolution_note",
            "resolved_at", "client_reference", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "project_name", "mission_title", "reported_by", "reported_by_name", "assigned_to_name", "resolved_at",
            "created_at", "updated_at",
        )
        extra_kwargs = {"client_reference": {"required": False}}

    def get_reported_by_name(self, obj):
        return _display_name(obj.reported_by)

    def get_assigned_to_name(self, obj):
        return _display_name(obj.assigned_to) if obj.assigned_to_id else None

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        project = attrs.get("project", getattr(instance, "project", None))
        mission = attrs.get("mission", getattr(instance, "mission", None))
        assigned_to = attrs.get("assigned_to", getattr(instance, "assigned_to", None))
        if mission and project and mission.project_id != project.id:
            raise serializers.ValidationError({"mission": "Cette mission n’appartient pas au projet indiqué."})
        if assigned_to and assigned_to.role != UserRole.FIELD_AGENT:
            raise serializers.ValidationError({"assigned_to": "Le responsable d’un problème doit être un Agent terrain."})
        return attrs


class RevisionRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000, trim_whitespace=True)


class MissionStartSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
