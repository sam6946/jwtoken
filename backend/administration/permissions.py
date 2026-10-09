from rest_framework.permissions import BasePermission

from accounts.models import UserRole


def is_kemta_admin(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (user.is_superuser or user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN})
    )


def is_super_admin(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (user.is_superuser or user.role == UserRole.SUPER_ADMIN)
    )


class IsKemtaAdmin(BasePermission):
    message = "Cet espace est réservé à l’administration KEMTA."

    def has_permission(self, request, view):
        return is_kemta_admin(request.user)


class IsSuperAdmin(BasePermission):
    message = "Cette action est réservée au Super Admin KEMTA."

    def has_permission(self, request, view):
        return is_super_admin(request.user)
