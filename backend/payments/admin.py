from django.contrib import admin

from payments.models import Payment, PaymentTransaction, Subscription, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "tier", "price", "currency", "billing_period_days", "is_active")
    list_filter = ("tier", "is_active", "currency")
    search_fields = ("name", "code")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("company", "plan", "status", "starts_at", "ends_at")
    list_filter = ("status", "plan")
    search_fields = ("company__name", "company__user__phone")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "provider", "amount", "currency", "status", "created_at")
    list_filter = ("provider", "status", "currency")
    search_fields = ("provider_reference", "idempotency_key", "owner__phone")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("event_type", "payment", "provider_reference", "verified", "created_at")
    list_filter = ("event_type", "verified")
    search_fields = ("provider_reference", "idempotency_key", "payment__idempotency_key")
    readonly_fields = ("payment", "event_type", "provider_reference", "idempotency_key", "payload_hash", "verified", "created_at")
