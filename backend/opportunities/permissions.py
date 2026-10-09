from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import KemtaPermission, UserRole
from accounts.permissions import has_kemta_permission


class OpportunityAccessPermission(BasePermission):
    message = "Cette action est réservée à l’équipe KEMTA."

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user.is_authenticated and has_kemta_permission(request.user, KemtaPermission.CREATE_OPPORTUNITY))

    def has_object_permission(self, request, view, obj) -> bool:
        return request.method in SAFE_METHODS or bool(request.user.is_staff or request.user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN})


class ApplicationAccessPermission(BasePermission):
    message = "Cette action est réservée aux comptes entreprise ou à l’équipe KEMTA."

    def has_permission(self, request, view) -> bool:
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            return True
        if request.method in SAFE_METHODS:
            return request.user.role == UserRole.BTP_COMPANY
        return request.user.role == UserRole.BTP_COMPANY and has_kemta_permission(request.user, KemtaPermission.APPLY_OPPORTUNITY)

    def has_object_permission(self, request, view, obj) -> bool:
        return bool(
            request.user.is_staff
            or request.user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}
            or obj.company.user_id == request.user.id
        )
