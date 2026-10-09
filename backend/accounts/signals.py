from django.db.models.signals import post_migrate
from django.dispatch import receiver

from accounts.models import KemtaPermission, RoleGrant, UserRole

DEFAULT_ROLE_GRANTS = {
    UserRole.CUSTOMER: (
        KemtaPermission.VIEW_PROJECT,
        KemtaPermission.VIEW_FINANCE,
    ),
    UserRole.BTP_COMPANY: (
        KemtaPermission.APPLY_OPPORTUNITY,
        KemtaPermission.MANAGE_COMPANY,
        KemtaPermission.MANAGE_CATALOG,
    ),
    UserRole.FIELD_AGENT: (
        KemtaPermission.VIEW_PROJECT,
        KemtaPermission.UPLOAD_EVIDENCE,
        KemtaPermission.VIEW_ASSIGNED_MISSION,
        KemtaPermission.EXECUTE_ASSIGNED_MISSION,
        KemtaPermission.SUBMIT_FIELD_REPORT,
        KemtaPermission.REPORT_PROJECT_ISSUE,
    ),
    UserRole.PROJECT_MANAGER: (
        KemtaPermission.VIEW_PROJECT,
        KemtaPermission.CREATE_PROJECT,
        KemtaPermission.EDIT_PROJECT,
        KemtaPermission.MANAGE_PROJECT,
        KemtaPermission.UPLOAD_EVIDENCE,
        KemtaPermission.VALIDATE_EVIDENCE,
        KemtaPermission.VIEW_FINANCE,
        KemtaPermission.MANAGE_FINANCE,
        KemtaPermission.CREATE_OPPORTUNITY,
        KemtaPermission.MANAGE_SERVICE_REQUESTS,
        KemtaPermission.ASSIGN_FIELD_AGENT,
        KemtaPermission.CREATE_FIELD_MISSION,
        KemtaPermission.VIEW_FIELD_REPORT,
        KemtaPermission.REVIEW_FIELD_REPORT,
        KemtaPermission.MANAGE_PROJECT_ISSUE,
    ),
    UserRole.ADMIN: tuple(permission for permission in KemtaPermission if permission != KemtaPermission.VIEW_AUDIT_LOGS),
    UserRole.SUPER_ADMIN: tuple(KemtaPermission),
}


@receiver(post_migrate, dispatch_uid="kemta_seed_role_grants")
def seed_role_grants(sender, using, **kwargs):
    if sender.name != "accounts":
        return
    for role, permissions in DEFAULT_ROLE_GRANTS.items():
        for permission in permissions:
            RoleGrant.objects.using(using).get_or_create(role=role, permission=permission)
