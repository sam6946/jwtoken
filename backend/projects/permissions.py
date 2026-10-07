from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import KemtaPermission, UserRole
from accounts.permissions import has_kemta_permission

_ADMIN_ROLES = {UserRole.ADMIN, UserRole.SUPER_ADMIN}


def can_manage_all(user) -> bool:
    return bool(user.is_authenticated and (user.is_staff or user.role in _ADMIN_ROLES))


def can_access_project(user, project) -> bool:
    if can_manage_all(user):
        return True
    if not user.is_authenticated:
        return False
    if project.owner_id == user.id or project.manager_id == user.id:
        return True
    return bool(project.field_agents.filter(pk=user.id).exists())


class ProjectAccessPermission(BasePermission):
    message = "Vous n’avez pas les droits nécessaires sur ce projet."

    def has_permission(self, request, view) -> bool:
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return has_kemta_permission(request.user, KemtaPermission.VIEW_PROJECT)
        return has_kemta_permission(request.user, KemtaPermission.MANAGE_PROJECT)

    def has_object_permission(self, request, view, obj) -> bool:
        if can_manage_all(request.user):
            return True
        if request.method in SAFE_METHODS:
            return can_access_project(request.user, obj)
        return has_kemta_permission(request.user, KemtaPermission.MANAGE_PROJECT) and can_access_project(request.user, obj)


def _is_own_task_status_update(request, view, obj) -> bool:
    """Un agent terrain peut faire évoluer le statut d’une tâche qui lui est assignée."""
    if getattr(view, "basename", "") != "project-task" or request.method != "PATCH":
        return False
    return getattr(obj, "assigned_to_id", None) == request.user.id


class ProjectChildAccessPermission(BasePermission):
    message = "Vous n’avez pas accès à cette information de chantier."

    def has_permission(self, request, view) -> bool:
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return has_kemta_permission(request.user, KemtaPermission.VIEW_PROJECT)
        if getattr(view, "basename", "") == "project-task" and request.method == "PATCH":
            # Le contrôle fin (tâche assignée) est fait dans has_object_permission.
            return has_kemta_permission(request.user, KemtaPermission.VIEW_PROJECT)
        return has_kemta_permission(request.user, KemtaPermission.MANAGE_PROJECT)

    def has_object_permission(self, request, view, obj) -> bool:
        if can_manage_all(request.user):
            return True
        project = getattr(obj, "project", None)
        if project is None or not can_access_project(request.user, project):
            return False
        if request.method in SAFE_METHODS or _is_own_task_status_update(request, view, obj):
            return True
        return has_kemta_permission(request.user, KemtaPermission.MANAGE_PROJECT)


class EvidenceAccessPermission(BasePermission):
    message = "Vous n’avez pas accès à cette preuve terrain."

    def has_permission(self, request, view) -> bool:
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return has_kemta_permission(request.user, KemtaPermission.VIEW_PROJECT)
        if getattr(view, "action", "") == "create":
            return has_kemta_permission(request.user, KemtaPermission.UPLOAD_EVIDENCE)
        return has_kemta_permission(request.user, KemtaPermission.VALIDATE_EVIDENCE)

    def has_object_permission(self, request, view, obj) -> bool:
        if can_manage_all(request.user):
            return True
        if request.method in SAFE_METHODS:
            return can_access_project(request.user, obj.project)
        return has_kemta_permission(request.user, KemtaPermission.VALIDATE_EVIDENCE) and can_access_project(request.user, obj.project)


class ProjectExpenseAccessPermission(BasePermission):
    """Le propriétaire consulte les dépenses de son chantier ; l’équipe KEMTA les enregistre."""

    message = "Vous n’avez pas accès aux dépenses de ce chantier."

    def has_permission(self, request, view) -> bool:
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return has_kemta_permission(request.user, KemtaPermission.VIEW_PROJECT)
        return has_kemta_permission(request.user, KemtaPermission.MANAGE_FINANCE)

    def has_object_permission(self, request, view, obj) -> bool:
        if can_manage_all(request.user):
            return True
        if not can_access_project(request.user, obj.project):
            return False
        if request.method in SAFE_METHODS:
            return has_kemta_permission(request.user, KemtaPermission.VIEW_FINANCE)
        return has_kemta_permission(request.user, KemtaPermission.MANAGE_FINANCE)
