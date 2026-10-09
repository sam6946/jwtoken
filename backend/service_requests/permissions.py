from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.models import UserRole


class ServiceRequestAccessPermission(BasePermission):
    message = "Cette demande n’est pas accessible avec votre compte."

    def has_permission(self, request, view) -> bool:
        if view.action == "create":
            return True
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            return True
        return view.action in {"list", "retrieve"}

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff or request.user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            return True
        if request.method in SAFE_METHODS:
            return obj.owner_id == request.user.id
        return False
