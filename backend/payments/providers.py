from dataclasses import dataclass
from typing import Protocol

from payments.models import Payment


class PaymentProviderNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class PaymentIntent:
    provider_reference: str
    status: str
    checkout_url: str | None = None


class PaymentProvider(Protocol):
    """Provider adapter contract; a gateway-specific implementation is configured per deployment."""

    code: str

    def create_intent(self, payment: Payment, phone: str) -> PaymentIntent: ...

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool: ...


def get_payment_provider(provider_code: str) -> PaymentProvider:
    """Fail closed until a gateway-specific adapter is installed and configured."""
    raise PaymentProviderNotConfigured(
        f"Aucun adaptateur de paiement n’est configuré pour « {provider_code} ». "
        "Les clés et la signature de webhook doivent être validées avant l’activation."
    )
