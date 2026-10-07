from django.core.cache import cache
from rest_framework.permissions import BasePermission

from accounts.models import RoleGrant, UserRole


def has_kemta_permission(user, permission: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.role == UserRole.SUPER_ADMIN:
        return True
    cache_key = f"rbac:{user.role}:{permission}"
    cached = cache.get(cache_key)
    if cached is not None:
        return bool(cached)
    allowed = RoleGrant.objects.filter(role=user.role, permission=permission, enabled=True).exists()
    cache.set(cache_key, allowed, timeout=300)
    return allowed


class HasKemtaPermission(BasePermission):
    message = "Votre compte n’a pas l’autorisation nécessaire pour effectuer cette action."

    def has_permission(self, request, view) -> bool:
        permission = getattr(view, "required_permission", None)
        return True if permission is None else has_kemta_permission(request.user, permission)


class HasAllowedKemtaRole(BasePermission):
    message = "Cette fonctionnalité est réservée à un autre type de compte."

    def has_permission(self, request, view) -> bool:
        allowed_roles = getattr(view, "allowed_roles", None)
        if allowed_roles is None:
            return True
        return bool(request.user.is_authenticated and (request.user.is_superuser or request.user.role in allowed_roles))
