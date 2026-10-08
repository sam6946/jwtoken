from django.contrib import admin
from django.utils.html import format_html

from companies.models import CompanyDocument, CompanyProfile, PortfolioItem


class PortfolioInline(admin.TabularInline):
    model = PortfolioItem
    extra = 0
    fields = ("title", "project_type", "city", "is_published", "position")


class CompanyDocumentInline(admin.TabularInline):
    model = CompanyDocument
    extra = 0
    can_delete = False
    fields = ("document_type", "status", "rejection_reason", "uploaded_at", "reviewed_at", "download_link")
    readonly_fields = ("document_type", "status", "rejection_reason", "uploaded_at", "reviewed_at", "download_link")

    @admin.display(description="Document")
    def download_link(self, obj):
        if not obj.pk or not obj.file:
            return "—"
        # Lien vers l'endpoint authentifié : les pièces ne sont jamais servies
        # directement depuis le stockage.
        url = f"/api/v1/companies/me/documents/{obj.pk}/file/"
        return format_html('<a href="{}" target="_blank" rel="noreferrer">{}</a>', url, obj.original_name or "ouvrir")


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "user", "verified", "verification_status", "verification_level", "is_published", "created_at")
    list_filter = ("verification_status", "verification_level", "verified", "is_published", "company_type", "city")
    search_fields = ("name", "legal_name", "city", "user__phone", "user__email", "registration_number", "tax_number")
    readonly_fields = ("slug", "views_count", "created_at", "updated_at", "verification_submitted_at", "verification_reviewed_at", "verification_reviewed_by")
    inlines = (PortfolioInline, CompanyDocumentInline)
    actions = ("verify_and_publish",)

    @admin.action(description="Vérifier et publier les profils sélectionnés")
    def verify_and_publish(self, request, queryset):
        # Passage par save() : le dossier de vérification est aligné (statut et niveau).
        for company in queryset:
            company.verified = True
            company.is_published = True
            company.save()


@admin.register(CompanyDocument)
class CompanyDocumentAdmin(admin.ModelAdmin):
    list_display = ("company", "document_type", "status", "reviewed_at", "uploaded_at", "download_link")
    list_filter = ("document_type", "status")
    search_fields = ("company__name", "company__legal_name", "original_name")
    readonly_fields = ("company", "document_type", "file", "original_name", "content_type", "file_size", "uploaded_at", "created_at", "updated_at")

    @admin.display(description="Document")
    def download_link(self, obj):
        if not obj.file:
            return "—"
        url = f"/api/v1/companies/me/documents/{obj.pk}/file/"
        return format_html('<a href="{}" target="_blank" rel="noreferrer">ouvrir</a>', url)


@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "city", "is_published", "position")
    list_filter = ("is_published", "project_type", "city")
    search_fields = ("title", "company__name", "city")
