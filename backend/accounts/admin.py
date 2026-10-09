from django.contrib import admin

from accounts.models import RoleGrant, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone", "first_name", "last_name", "role", "phone_verified", "is_active", "created_at")
    list_filter = ("role", "phone_verified", "is_active", "is_staff")
    search_fields = ("phone", "first_name", "last_name", "email")
    readonly_fields = ("last_login", "created_at", "updated_at")
    ordering = ("-created_at",)
    fieldsets = (
        ("Identité", {"fields": ("phone", "phone_verified", "first_name", "last_name", "email", "role")}),
        ("Accès", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )


@admin.register(RoleGrant)
class RoleGrantAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "enabled", "updated_at")
    list_filter = ("role", "enabled")
    search_fields = ("role", "permission")
