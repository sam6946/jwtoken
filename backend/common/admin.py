from django.contrib import admin

from common.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("event", "actor", "object_type", "object_id", "request_id", "created_at")
    list_filter = ("event", "object_type", "created_at")
    search_fields = ("event", "object_type", "object_id", "request_id", "actor__phone")
    readonly_fields = ("actor", "event", "object_type", "object_id", "metadata", "request_id", "created_at")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
