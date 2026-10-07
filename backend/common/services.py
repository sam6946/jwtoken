from collections.abc import Mapping
from typing import Any

from common.models import AuditLog


def write_audit_event(
    *,
    event: str,
    actor=None,
    object_type: str = "",
    object_id: str | int = "",
    metadata: Mapping[str, Any] | None = None,
    request_id: str = "",
) -> AuditLog:
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        event=event,
        object_type=object_type,
        object_id=str(object_id),
        metadata=dict(metadata or {}),
        request_id=request_id[:64],
    )
