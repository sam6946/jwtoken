import hashlib
import hmac

from django.db import transaction
from rest_framework.exceptions import ValidationError

from payments.models import Payment, PaymentStatus
from payments.providers import PaymentProviderNotConfigured, get_payment_provider


@transaction.atomic
def create_payment_intent(*, owner, provider_code: str, amount, currency: str, idempotency_key: str, phone: str, description: str = "") -> Payment:
    existing = Payment.objects.select_for_update().filter(idempotency_key=idempotency_key).first()
    if existing:
        same_request = (
            existing.owner_id == owner.id
            and existing.provider == provider_code
            and existing.amount == amount
            and existing.currency == currency
        )
        if not same_request:
            raise ValidationError("Cette clé d’idempotence a déjà été utilisée pour une autre opération.")
        return existing

    payment = Payment.objects.create(
        owner=owner,
        provider=provider_code,
        amount=amount,
        currency=currency,
        idempotency_key=idempotency_key,
        description=description,
        status=PaymentStatus.CREATED,
    )
    try:
        provider = get_payment_provider(provider_code)
        intent = provider.create_intent(payment, phone)
    except PaymentProviderNotConfigured:
        raise
    payment.provider_reference = intent.provider_reference
    payment.status = intent.status
    payment.metadata = {"checkout_url": intent.checkout_url} if intent.checkout_url else {}
    payment.save(update_fields=("provider_reference", "status", "metadata", "updated_at"))
    return payment


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
