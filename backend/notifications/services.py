from django.utils import timezone

from notifications.models import Notification, NotificationType


def create_in_app_notification(
    *,
    user,
    title: str,
    body: str = "",
    notification_type: str = NotificationType.GENERAL,
    action_url: str = "",
    data: dict | None = None,
    dedupe_key: str | None = None,
) -> Notification:
    defaults = {
        "notification_type": notification_type,
        "title": title[:180],
        "body": body[:500],
        "action_url": action_url[:300],
        "data": data or {},
    }
    if dedupe_key:
        notification, _ = Notification.objects.get_or_create(user=user, dedupe_key=dedupe_key, defaults=defaults)
        return notification
    return Notification.objects.create(user=user, **defaults)


def mark_notification_read(notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=("read_at",))
    return notification
