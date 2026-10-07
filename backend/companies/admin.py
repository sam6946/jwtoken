from django.contrib import admin

from companies.models import CompanyProfile, PortfolioItem


class PortfolioInline(admin.TabularInline):
    model = PortfolioItem
    extra = 0
    fields = ("title", "project_type", "city", "is_published", "position")


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "user", "verified", "is_published", "created_at")
    list_filter = ("verified", "is_published", "city")
    search_fields = ("name", "city", "user__phone", "user__email")
    readonly_fields = ("slug", "views_count", "created_at", "updated_at")
    inlines = (PortfolioInline,)
    actions = ("verify_and_publish",)

    @admin.action(description="Vérifier et publier les profils sélectionnés")
    def verify_and_publish(self, request, queryset):
        queryset.update(verified=True, is_published=True)


@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "city", "is_published", "position")
    list_filter = ("is_published", "project_type", "city")
    search_fields = ("title", "company__name", "city")
