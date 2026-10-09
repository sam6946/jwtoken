import logging
import smtplib

import requests
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

logger = logging.getLogger("kemta")


@shared_task(bind=True, autoretry_for=(requests.RequestException, TimeoutError), retry_backoff=True, max_retries=5)
def send_sms_task(self, phone: str, message: str) -> None:
    provider = settings.SMS_PROVIDER
    if provider == "console" and settings.DEBUG:
        logger.info("Development SMS accepted for recipient ending %s", phone[-4:])
        return
    if provider != "http_json" or not settings.SMS_API_URL or not settings.SMS_API_KEY:
        raise RuntimeError("Aucun fournisseur SMS de production n’est configuré.")
    response = requests.post(
        settings.SMS_API_URL,
        headers={"Authorization": f"Bearer {settings.SMS_API_KEY}"},
        json={"to": phone, "message": message},
        timeout=(3.05, 8),
    )
    response.raise_for_status()
    logger.info("SMS provider accepted message for recipient ending %s", phone[-4:])


@shared_task(bind=True, autoretry_for=(smtplib.SMTPException, OSError, TimeoutError), retry_backoff=True, max_retries=3)
def send_email_task(self, subject: str, message: str, recipient: str) -> None:
    if not recipient:
        return
    sent_count = send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
    if sent_count != 1:
        raise RuntimeError("Le fournisseur email n’a pas accepté le message.")


@shared_task
def cleanup_expired_otp_cache() -> int:
    """Remove accidental persistent OTP/cache records; normal Redis TTLs expire them automatically."""
    if not settings.REDIS_URL or "django_redis" not in settings.CACHES["default"]["BACKEND"]:
        return 0
    from django_redis import get_redis_connection

    client = get_redis_connection("default")
    namespaces = ("auth:otp:", "auth:challenge:", "auth:otp-rate:")
    removed = 0
    for namespace in namespaces:
        pattern = f"{cache.make_key(namespace)}*"
        for key in client.scan_iter(match=pattern, count=200):
            if client.ttl(key) == -1:
                removed += client.delete(key)
    if removed:
        logger.warning("Removed %s auth cache key(s) without an expiry", removed)
    return removed
