from django.contrib import admin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "notification_type", "read_at", "created_at")
    list_filter = ("notification_type", "read_at", "created_at")
    search_fields = ("title", "body", "user__phone")
    readonly_fields = ("created_at",)
