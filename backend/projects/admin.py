from django.contrib import admin

from projects.models import Evidence, Project, ProjectPhase, ProjectReport, ProjectTask


class PhaseInline(admin.TabularInline):
    model = ProjectPhase
    extra = 0
    ordering = ("position",)


class TaskInline(admin.TabularInline):
    model = ProjectTask
    extra = 0
    fields = ("title", "phase", "assigned_to", "status", "due_date")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "manager", "city", "progress", "status", "updated_at")
    list_filter = ("status", "city", "project_type")
    search_fields = ("name", "owner__phone", "owner__last_name", "city")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("field_agents",)
    inlines = (PhaseInline, TaskInline)


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "phase", "uploaded_by", "verification_status", "created_at")
    list_filter = ("verification_status", "created_at")
    search_fields = ("title", "project__name", "uploaded_by__phone")
    readonly_fields = ("uploaded_by", "created_at")


@admin.register(ProjectReport)
class ProjectReportAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "author", "created_at")
    search_fields = ("title", "project__name", "author__phone")
    readonly_fields = ("author", "created_at")
