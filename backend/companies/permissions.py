from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import KemtaPermission, UserRole
from accounts.permissions import has_kemta_permission


class CompanyOwnerPermission(BasePermission):
    message = "Cet espace est réservé aux entreprises BTP."

    def has_permission(self, request, view) -> bool:
        return bool(request.user.is_authenticated and (
            request.user.is_staff
            or request.user.role in {UserRole.BTP_COMPANY, UserRole.ADMIN, UserRole.SUPER_ADMIN}
        ))


class PortfolioAccessPermission(BasePermission):
    message = "Vous n’avez pas les droits nécessaires pour gérer ce catalogue."

    def has_permission(self, request, view) -> bool:
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return has_kemta_permission(request.user, KemtaPermission.MANAGE_CATALOG)

    def has_object_permission(self, request, view, obj) -> bool:
        return bool(
            request.user.is_staff
            or request.user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}
            or obj.company.user_id == request.user.id
        )


class CompanyVerificationAdminPermission(BasePermission):
    """Réservé à l'équipe KEMTA : examen des dossiers de vérification."""

    message = "Seule l’équipe KEMTA peut examiner les dossiers de vérification."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user.is_authenticated and (user.is_staff or user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}))
