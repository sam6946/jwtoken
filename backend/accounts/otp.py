from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import logging
import secrets
from typing import Literal, cast

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.core.cache import cache
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError

from accounts.models import User
from accounts.phones import normalize_phone

logger = logging.getLogger("kemta")
OtpPurpose = Literal["REGISTER", "LOGIN", "PASSWORD_RESET"]
_OTP_KEY_PREFIX = "auth:otp:"
_CHALLENGE_KEY_PREFIX = "auth:challenge:"
_REQUEST_LIMIT = 5
_REQUEST_WINDOW_SECONDS = 60 * 60
_CHALLENGE_SALT = "kemta.auth.phone-challenge.v1"


@dataclass
class OTPVerification:
    """Short-lived OTP record stored only in Redis/Django cache, never in PostgreSQL."""

    phone: str
    code_hash: str
    purpose: OtpPurpose
    expires_at: str
    attempts: int = 0
    used_at: str | None = None


@dataclass(frozen=True)
class OTPDispatch:
    detail: str
    expires_in: int
    debug_code: str | None = None


def _phone_fingerprint(phone: str) -> str:
    digest = hashlib.sha256(f"{settings.SECRET_KEY}:{phone}".encode("utf-8")).hexdigest()
    return digest


def _otp_cache_key(phone: str, purpose: OtpPurpose) -> str:
    return f"{_OTP_KEY_PREFIX}{purpose.lower()}:{_phone_fingerprint(phone)}"


def _throttle_key(phone: str, purpose: OtpPurpose) -> str:
    return f"auth:otp-rate:{purpose.lower()}:{_phone_fingerprint(phone)}"


def _consume_rate_limit(phone: str, purpose: OtpPurpose) -> None:
    key = _throttle_key(phone, purpose)
    cache.add(key, 0, timeout=_REQUEST_WINDOW_SECONDS)
    try:
        current_count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=_REQUEST_WINDOW_SECONDS)
        current_count = 1
    if current_count > _REQUEST_LIMIT:
        raise Throttled(wait=_REQUEST_WINDOW_SECONDS, detail="Trop de demandes de code. Réessayez plus tard.")


def _sms_configured() -> bool:
    if settings.DEBUG:
        return True
    if settings.SMS_PROVIDER == "http_json":
        return bool(settings.SMS_API_URL and settings.SMS_API_KEY)
    return False


def _dispatch_sms(phone: str, code: str, purpose: OtpPurpose) -> None:
    message_by_purpose = {
        "REGISTER": f"Votre code de vérification KEMTA est {code}. Il expire dans {settings.OTP_TTL_SECONDS // 60} minutes.",
        "LOGIN": f"Votre code de connexion KEMTA est {code}. Ne le partagez avec personne.",
        "PASSWORD_RESET": f"Votre code de réinitialisation KEMTA est {code}. Ne le partagez avec personne.",
    }
    message = message_by_purpose[purpose]
    if settings.DEBUG:
        logger.info("Development OTP generated for %s (purpose=%s): %s", phone, purpose, code)
        return
    if not _sms_configured():
        raise ValidationError("L’envoi de SMS n’est pas configuré pour cet environnement.")
    from notifications.tasks import send_sms_task

    send_sms_task.delay(phone, message)


def request_otp(phone_value: str, purpose_value: str) -> OTPDispatch:
    allowed = {"REGISTER", "LOGIN", "PASSWORD_RESET"}
    purpose_string = purpose_value.upper()
    if purpose_string not in allowed:
        raise ValidationError({"purpose": "Objet de vérification invalide."})
    purpose = cast(OtpPurpose, purpose_string)
    phone = normalize_phone(phone_value)
    _consume_rate_limit(phone, purpose)

    existing_user = User.objects.filter(phone=phone).only("id", "is_active").first()
    if purpose == "REGISTER" and existing_user:
        raise ValidationError({"phone": "Un compte est déjà associé à ce numéro. Essayez de vous connecter."})

    # For login/reset, return the same response for known and unknown numbers to avoid account enumeration.
    generic_detail = "Si le numéro peut recevoir un code, celui-ci vient d’être envoyé."
    if purpose in {"LOGIN", "PASSWORD_RESET"} and (existing_user is None or not existing_user.is_active):
        logger.info("OTP request ignored for unknown/inactive account (purpose=%s)", purpose)
        return OTPDispatch(detail=generic_detail, expires_in=settings.OTP_TTL_SECONDS)

    code = f"{secrets.randbelow(1_000_000):06d}"
    now = timezone.now()
    verification = OTPVerification(
        phone=phone,
        code_hash=make_password(code),
        purpose=purpose,
        expires_at=(now + timedelta(seconds=settings.OTP_TTL_SECONDS)).isoformat(),
    )
    cache.set(_otp_cache_key(phone, purpose), asdict(verification), timeout=settings.OTP_TTL_SECONDS)
    _dispatch_sms(phone, code, purpose)
    return OTPDispatch(
        detail=generic_detail,
        expires_in=settings.OTP_TTL_SECONDS,
        debug_code=code if settings.DEBUG else None,
    )


def verify_otp(phone_value: str, code_value: str, purpose_value: str) -> str:
    purpose_string = purpose_value.upper()
    if purpose_string not in {"REGISTER", "LOGIN", "PASSWORD_RESET"}:
        raise ValidationError({"purpose": "Objet de vérification invalide."})
    purpose = cast(OtpPurpose, purpose_string)
    phone = normalize_phone(phone_value)
    code = "".join(character for character in code_value if character.isdigit())
    if len(code) != 6:
        raise ValidationError({"code": "Saisissez le code à 6 chiffres."})

    key = _otp_cache_key(phone, purpose)
    record = cache.get(key)
    if not isinstance(record, dict):
        raise ValidationError({"code": "Ce code est invalide ou a expiré. Demandez-en un nouveau."})

    if record.get("used_at"):
        cache.delete(key)
        raise ValidationError({"code": "Ce code a déjà été utilisé. Demandez-en un nouveau."})

    expires_at = datetime.fromisoformat(record["expires_at"])
    if timezone.is_naive(expires_at):
        expires_at = timezone.make_aware(expires_at, timezone=timezone.get_current_timezone())
    if expires_at <= timezone.now():
        cache.delete(key)
        raise ValidationError({"code": "Ce code a expiré. Demandez-en un nouveau."})

    attempts = int(record.get("attempts", 0))
    if attempts >= settings.OTP_MAX_ATTEMPTS:
        cache.delete(key)
        raise Throttled(wait=0, detail="Nombre maximal d’essais atteint. Demandez un nouveau code.")
    if not check_password(code, record.get("code_hash", "")):
        record["attempts"] = attempts + 1
        remaining = max(1, int((expires_at - timezone.now()).total_seconds()))
        cache.set(key, record, timeout=remaining)
        remaining_attempts = max(0, settings.OTP_MAX_ATTEMPTS - attempts - 1)
        raise ValidationError({"code": f"Code incorrect. Il vous reste {remaining_attempts} essai(s)."})

    if purpose == "REGISTER" and User.objects.filter(phone=phone).exists():
        cache.delete(key)
        raise ValidationError({"phone": "Un compte est déjà associé à ce numéro."})
    if purpose in {"LOGIN", "PASSWORD_RESET"} and not User.objects.filter(phone=phone, is_active=True).exists():
        cache.delete(key)
        raise ValidationError({"code": "Ce code est invalide ou a expiré."})

    cache.delete(key)
    challenge_id = secrets.token_urlsafe(24)
    challenge = {"id": challenge_id, "phone": phone, "purpose": purpose}
    cache.set(f"{_CHALLENGE_KEY_PREFIX}{challenge_id}", challenge, timeout=settings.OTP_TTL_SECONDS)
    return signing.dumps(challenge, salt=_CHALLENGE_SALT, compress=True)


def consume_verification_token(token: str, expected_purpose: OtpPurpose) -> str:
    try:
        challenge = signing.loads(token, salt=_CHALLENGE_SALT, max_age=settings.OTP_TTL_SECONDS)
    except signing.BadSignature as exc:
        raise ValidationError({"verification_token": "La vérification a expiré. Recommencez."}) from exc
    if not isinstance(challenge, dict) or challenge.get("purpose") != expected_purpose:
        raise ValidationError({"verification_token": "Le jeton de vérification n’est pas valide pour cette opération."})
    challenge_id = challenge.get("id")
    if not isinstance(challenge_id, str):
        raise ValidationError({"verification_token": "Jeton de vérification invalide."})
    key = f"{_CHALLENGE_KEY_PREFIX}{challenge_id}"
    stored = cache.get(key)
    if stored != challenge:
        raise ValidationError({"verification_token": "Ce jeton a déjà été utilisé ou a expiré."})
    cache.delete(key)
    phone = challenge.get("phone")
    if not isinstance(phone, str):
        raise ValidationError({"verification_token": "Jeton de vérification invalide."})
    return phone


def clean_expired_otp_cache() -> int:
    """Redis expires OTP entries automatically; this hook is kept for scheduled audit/housekeeping."""
    return 0
