from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import KemtaPermission, UserRole
from accounts.permissions import has_kemta_permission
from projects.models import ProjectAssignment, ProjectAssignmentStatus

_ADMIN_ROLES = {UserRole.ADMIN, UserRole.SUPER_ADMIN}


def can_manage_all(user) -> bool:
    return bool(user.is_authenticated and (user.is_staff or user.role in _ADMIN_ROLES))


def is_project_manager(user, project) -> bool:
    """Les opérations de pilotage sont réservées au chef du projet ou à KEMTA."""
    return bool(
        can_manage_all(user)
        or (
            user.is_authenticated
            and project.manager_id == user.id
            and has_kemta_permission(user, KemtaPermission.MANAGE_PROJECT)
        )
    )


def has_active_project_assignment(user, project) -> bool:
    return bool(
        user.is_authenticated
        and ProjectAssignment.objects.filter(
            project=project,
            user=user,
            status=ProjectAssignmentStatus.ACTIVE,
        ).exists()
    )


def can_access_project(user, project) -> bool:
    if can_manage_all(user):
        return True
    if not user.is_authenticated:
        return False
    if project.owner_id == user.id or project.manager_id == user.id:
        return True
    # field_agents est conservé pour ne pas exclure les données créées avant
    # ProjectAssignment. Les nouvelles vues métier s'appuient elles sur
    # has_active_project_assignment pour restreindre une mission précise.
    return bool(project.field_agents.filter(pk=user.id).exists())


def can_access_mission(user, mission) -> bool:
    return bool(can_manage_all(user) or mission.assigned_to_id == user.id or is_project_manager(user, mission.project))


def can_access_field_report(user, report) -> bool:
    return can_access_mission(user, report.mission)


def can_access_issue(user, issue) -> bool:
    if can_manage_all(user) or is_project_manager(user, issue.project):
        return True
    return issue.reported_by_id == user.id or issue.assigned_to_id == user.id


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
        return has_kemta_permission(request.user, KemtaPermission.VALIDATE_EVIDENCE) and is_project_manager(request.user, obj.project)


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


class ProjectAssignmentPermission(BasePermission):
    message = "Seul le chef de projet peut gérer les affectations terrain."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user.is_authenticated
            and (can_manage_all(request.user) or has_kemta_permission(request.user, KemtaPermission.ASSIGN_FIELD_AGENT))
        )

    def has_object_permission(self, request, view, obj) -> bool:
        return is_project_manager(request.user, obj.project)


class FieldMissionPermission(BasePermission):
    message = "Vous n’avez pas accès à cette mission terrain."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return bool(
                can_manage_all(user)
                or has_kemta_permission(user, KemtaPermission.CREATE_FIELD_MISSION)
                or has_kemta_permission(user, KemtaPermission.VIEW_ASSIGNED_MISSION)
            )
        if getattr(view, "action", "") in {"accept", "start"}:
            return has_kemta_permission(user, KemtaPermission.EXECUTE_ASSIGNED_MISSION)
        return bool(can_manage_all(user) or has_kemta_permission(user, KemtaPermission.CREATE_FIELD_MISSION))

    def has_object_permission(self, request, view, obj) -> bool:
        return can_access_mission(request.user, obj)


class FieldReportPermission(BasePermission):
    message = "Vous n’avez pas accès à ce rapport terrain."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return bool(
                can_manage_all(user)
                or has_kemta_permission(user, KemtaPermission.VIEW_FIELD_REPORT)
                or has_kemta_permission(user, KemtaPermission.VIEW_ASSIGNED_MISSION)
            )
        action = getattr(view, "action", "")
        if action in {"start_review", "approve", "request_revision"}:
            return has_kemta_permission(user, KemtaPermission.REVIEW_FIELD_REPORT)
        if action in {"submit"} or request.method == "POST":
            return has_kemta_permission(user, KemtaPermission.SUBMIT_FIELD_REPORT)
        return has_kemta_permission(user, KemtaPermission.SUBMIT_FIELD_REPORT)

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if getattr(view, "action", "") in {"start_review", "approve", "request_revision"}:
            return is_project_manager(user, obj.mission.project) and obj.submitted_by_id != user.id
        if request.method in SAFE_METHODS:
            return can_access_field_report(user, obj)
        return obj.submitted_by_id == user.id and obj.mission.assigned_to_id == user.id


class ProjectIssuePermission(BasePermission):
    message = "Vous n’avez pas accès à ce problème de chantier."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return bool(
                can_manage_all(user)
                or has_kemta_permission(user, KemtaPermission.MANAGE_PROJECT_ISSUE)
                or has_kemta_permission(user, KemtaPermission.REPORT_PROJECT_ISSUE)
            )
        if request.method == "POST":
            return bool(
                can_manage_all(user)
                or has_kemta_permission(user, KemtaPermission.MANAGE_PROJECT_ISSUE)
                or has_kemta_permission(user, KemtaPermission.REPORT_PROJECT_ISSUE)
            )
        return bool(can_manage_all(user) or has_kemta_permission(user, KemtaPermission.MANAGE_PROJECT_ISSUE))

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return can_access_issue(request.user, obj)
        return is_project_manager(request.user, obj.project)
