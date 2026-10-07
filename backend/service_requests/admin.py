from django.contrib import admin

from service_requests.models import ServiceRequest, ServiceRequestAttachment


class AttachmentInline(admin.TabularInline):
    model = ServiceRequestAttachment
    extra = 0
    readonly_fields = ("file", "original_name", "content_type", "file_size", "created_at")
    can_delete = False


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ("request_code", "service_type", "first_name", "last_name", "phone", "city", "status", "created_at")
    list_filter = ("service_type", "status", "city", "created_at")
    search_fields = ("request_code", "first_name", "last_name", "phone", "email", "city")
    readonly_fields = ("request_code", "created_at", "updated_at")
    inlines = (AttachmentInline,)
    ordering = ("-created_at",)


admin.site.register(ServiceRequestAttachment)
