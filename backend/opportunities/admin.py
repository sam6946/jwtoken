from django.contrib import admin

from opportunities.models import Application, Opportunity


class ApplicationInline(admin.TabularInline):
    model = Application
    extra = 0
    readonly_fields = ("company", "message", "estimated_budget", "duration_days", "created_at")
    fields = ("company", "status", "estimated_budget", "duration_days", "created_at")


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ("title", "project_type", "city", "status", "deadline", "published_at")
    list_filter = ("status", "project_type", "city", "deadline")
    search_fields = ("title", "city", "description")
    readonly_fields = ("created_by", "published_at", "created_at", "updated_at")
    inlines = (ApplicationInline,)
    ordering = ("deadline",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("opportunity", "company", "status", "estimated_budget", "duration_days", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("opportunity__title", "company__name", "company__user__phone")
    readonly_fields = ("created_at", "updated_at")
