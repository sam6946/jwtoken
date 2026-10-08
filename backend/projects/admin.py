from django.contrib import admin

from projects.models import (
    Evidence,
    FieldMission,
    FieldReport,
    Project,
    ProjectAssignment,
    ProjectIssue,
    ProjectPhase,
    ProjectReport,
    ProjectTask,
)


class PhaseInline(admin.TabularInline):
    model = ProjectPhase
    extra = 0
    ordering = ("position",)


class TaskInline(admin.TabularInline):
    model = ProjectTask
    extra = 0
    fields = ("title", "phase", "assigned_to", "status", "due_date")


class AssignmentInline(admin.TabularInline):
    model = ProjectAssignment
    extra = 0
    fields = ("user", "status", "assigned_by", "start_date", "end_date")
    readonly_fields = ("assigned_by",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "manager", "city", "progress", "status", "updated_at")
    list_filter = ("status", "city", "project_type")
    search_fields = ("name", "owner__phone", "owner__last_name", "city")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("field_agents",)
    inlines = (PhaseInline, TaskInline, AssignmentInline)


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "mission", "evidence_type", "uploaded_by", "verification_status", "created_at")
    list_filter = ("evidence_type", "verification_status", "created_at")
    search_fields = ("title", "project__name", "uploaded_by__phone")
    readonly_fields = ("uploaded_by", "created_at")


@admin.register(ProjectReport)
class ProjectReportAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "author", "created_at")
    search_fields = ("title", "project__name", "author__phone")
    readonly_fields = ("author", "created_at")


@admin.register(FieldMission)
class FieldMissionAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "assigned_to", "status", "scheduled_start", "updated_at")
    list_filter = ("status", "mission_type", "requires_geo_confirmation")
    search_fields = ("title", "project__name", "assigned_to__phone")
    readonly_fields = ("created_by", "started_at", "completed_at", "location_confirmed_at", "created_at", "updated_at")


@admin.register(FieldReport)
class FieldReportAdmin(admin.ModelAdmin):
    list_display = ("mission", "submitted_by", "status", "submitted_at", "reviewed_by", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("mission__title", "submitted_by__phone", "mission__project__name")
    readonly_fields = ("submitted_by", "submitted_at", "reviewed_by", "reviewed_at", "created_at", "updated_at")


@admin.register(ProjectIssue)
class ProjectIssueAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "mission", "priority", "status", "reported_by", "created_at")
    list_filter = ("priority", "status")
    search_fields = ("title", "project__name", "reported_by__phone")
    readonly_fields = ("reported_by", "created_at", "updated_at")
