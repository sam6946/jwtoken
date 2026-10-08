from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import KemtaPermission, RoleGrant, User, UserRole
from accounts.serializers import UserSerializer
from companies.models import CompanyProfile
from companies.serializers import CompanyProfileSerializer
from common.models import AuditLog
from notifications.models import Notification
from notifications.serializers import NotificationSerializer
from opportunities.models import Application, Opportunity, OpportunityStatus
from opportunities.serializers import ApplicationSerializer, OpportunitySerializer
from payments.models import Payment, PaymentStatus, Subscription, SubscriptionStatus
from projects.models import (
    Evidence,
    FieldMission,
    FieldReport,
    FieldReportStatus,
    IssueStatus,
    MissionStatus,
    Project,
    ProjectAssignment,
    ProjectExpense,
    ProjectIssue,
    ProjectStatus,
    ProjectTask,
)
from projects.serializers import (
    EvidenceSerializer,
    FieldMissionSerializer,
    FieldReportSerializer,
    ProjectAssignmentSerializer,
    ProjectIssueSerializer,
    ProjectSerializer,
    ProjectTaskSerializer,
)
from service_requests.models import ServiceRequest, ServiceRequestStatus
from dashboard.serializers import DashboardServiceRequestSerializer


class DashboardAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user
        role = user.role
        today = timezone.localdate()
        permissions = list(
            RoleGrant.objects.filter(role=role, enabled=True).values_list("permission", flat=True)
        )
        projects = Project.objects.none()
        tasks = ProjectTask.objects.none()
        evidences = Evidence.objects.none()
        service_requests = ServiceRequest.objects.none()
        notifications = Notification.objects.filter(user=user).only(
            "id", "notification_type", "title", "body", "action_url", "data", "read_at", "created_at"
        ).order_by("-created_at")[:6]
        company = None
        companies = CompanyProfile.objects.none()
        opportunities = Opportunity.objects.none()
        applications = Application.objects.none()
        recent_activity = AuditLog.objects.none()
        statistics: dict[str, object] = {}

        is_admin = user.is_staff or role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}
        if is_admin:
            user_counts = User.objects.aggregate(
                clients=Count("id", filter=Q(role=UserRole.CUSTOMER, is_active=True)),
                companies=Count("id", filter=Q(role=UserRole.BTP_COMPANY, is_active=True)),
            )
            request_counts = ServiceRequest.objects.aggregate(
                pending=Count("id", filter=Q(status__in=(ServiceRequestStatus.NEW, ServiceRequestStatus.IN_REVIEW, ServiceRequestStatus.CONTACTED))),
                total=Count("id"),
            )
            project_counts = Project.objects.aggregate(
                projects=Count("id"),
                active=Count("id", filter=Q(status=ProjectStatus.ACTIVE)),
            )
            opportunity_counts = Opportunity.objects.aggregate(
                open=Count("id", filter=Q(status=OpportunityStatus.OPEN, deadline__gte=today)),
                total=Count("id"),
            )
            paid_total = Payment.objects.filter(status=PaymentStatus.SUCCEEDED).aggregate(total=Sum("amount"))["total"]
            statistics = {
                **user_counts,
                "service_requests": request_counts["pending"],
                "all_service_requests": request_counts["total"],
                "projects": project_counts["projects"],
                "active_projects": project_counts["active"],
                "revenue": str(paid_total or 0),
                "subscriptions": Subscription.objects.count(),
                "active_subscriptions": Subscription.objects.filter(status=SubscriptionStatus.ACTIVE).count(),
                "opportunities": opportunity_counts["open"],
                "all_opportunities": opportunity_counts["total"],
                "applications": Application.objects.count(),
                "tasks": ProjectTask.objects.count(),
                "pending_tasks": ProjectTask.objects.filter(status__in=(ProjectTask.Status.TODO, ProjectTask.Status.IN_PROGRESS, ProjectTask.Status.BLOCKED)).count(),
            }
            service_requests = ServiceRequest.objects.select_related("owner").order_by("-created_at")[:8]
            projects = Project.objects.select_related("owner", "manager").prefetch_related("phases").order_by("-updated_at")[:5]
            tasks = ProjectTask.objects.select_related("project", "phase", "assigned_to").order_by("due_date", "-created_at")[:8]
            companies = CompanyProfile.objects.select_related("user").prefetch_related("portfolio").order_by("-created_at")[:5]
            opportunities = Opportunity.objects.select_related("created_by").order_by("-updated_at")[:5]
            recent_activity = AuditLog.objects.select_related("actor").order_by("-created_at")[:8]
        elif role == UserRole.BTP_COMPANY:
            company = CompanyProfile.objects.filter(user=user).prefetch_related("portfolio").first()
            application_queryset = Application.objects.filter(company__user=user)
            applications = application_queryset.select_related("opportunity", "company").order_by("-created_at")[:5]
            opportunities = Opportunity.objects.filter(
                status=OpportunityStatus.OPEN,
                deadline__gte=today,
            ).select_related("created_by").order_by("deadline")[:5]
            statistics = {
                "applications": application_queryset.count(),
                "open_opportunities": Opportunity.objects.filter(status=OpportunityStatus.OPEN, deadline__gte=today).count(),
                "profile_completion": company.profile_completion if company else 0,
                "portfolio_count": company.portfolio.filter(is_published=True).count() if company else 0,
                "views_count": company.views_count if company else 0,
            }
            recent_activity = AuditLog.objects.filter(actor=user).order_by("-created_at")[:8]
        elif role == UserRole.PROJECT_MANAGER:
            project_scope = Project.objects.filter(manager=user)
            task_scope = ProjectTask.objects.filter(project__manager=user)
            projects = project_scope.select_related("owner").prefetch_related("phases").order_by("-updated_at")[:5]
            tasks = task_scope.select_related("project", "phase", "assigned_to").order_by("due_date", "-created_at")[:10]
            evidences = Evidence.objects.filter(project__manager=user).select_related("project", "phase", "uploaded_by").order_by("-created_at")[:6]
            statistics = {
                "projects": project_scope.count(),
                "active_projects": project_scope.filter(status=ProjectStatus.ACTIVE).count(),
                "tasks": task_scope.count(),
                "pending_tasks": task_scope.filter(status__in=(ProjectTask.Status.TODO, ProjectTask.Status.IN_PROGRESS, ProjectTask.Status.BLOCKED)).count(),
                "evidences_pending": Evidence.objects.filter(project__manager=user, verification_status=Evidence.VerificationStatus.PENDING).count(),
            }
            recent_activity = AuditLog.objects.filter(actor=user).order_by("-created_at")[:8]
        elif role == UserRole.FIELD_AGENT:
            project_scope = Project.objects.filter(field_agents=user)
            task_scope = ProjectTask.objects.filter(assigned_to=user)
            projects = project_scope.select_related("owner", "manager").prefetch_related("phases").order_by("-updated_at")[:5]
            tasks = task_scope.select_related("project", "phase", "assigned_to").order_by("due_date", "-created_at")[:10]
            statistics = {
                "projects": project_scope.count(),
                "active_projects": project_scope.filter(status=ProjectStatus.ACTIVE).count(),
                "tasks": task_scope.count(),
                "pending_tasks": task_scope.filter(status__in=(ProjectTask.Status.TODO, ProjectTask.Status.IN_PROGRESS, ProjectTask.Status.BLOCKED)).count(),
                "overdue_tasks": task_scope.filter(due_date__lt=today).exclude(status=ProjectTask.Status.DONE).count(),
                "evidences": Evidence.objects.filter(uploaded_by=user).count(),
            }
            evidences = Evidence.objects.filter(uploaded_by=user).select_related("project", "phase", "uploaded_by").order_by("-created_at")[:6]
            recent_activity = AuditLog.objects.filter(actor=user).order_by("-created_at")[:8]
        else:
            project_scope = Project.objects.filter(owner=user)
            # Le propriétaire doit retrouver la totalité de ses chantiers : chaque carte mène au détail.
            projects = project_scope.select_related("manager").prefetch_related("phases").order_by("-updated_at")
            service_requests = ServiceRequest.objects.filter(owner=user).order_by("-created_at")[:8]
            expense_scope = ProjectExpense.objects.filter(project__owner=user)
            project_counts = project_scope.aggregate(
                projects=Count("id"),
                active=Count("id", filter=Q(status=ProjectStatus.ACTIVE)),
            )
            statistics = {
                **project_counts,
                "service_requests": ServiceRequest.objects.filter(owner=user).count(),
                "expenses": expense_scope.count(),
                "receipts": expense_scope.exclude(receipt="").count(),
                "unread_notifications": Notification.objects.filter(user=user, read_at__isnull=True).count(),
                "budget_total": str(
                    project_scope.aggregate(total=Sum("budget_total"))["total"] or 0
                ),
                "budget_spent": str(
                    project_scope.aggregate(total=Sum("budget_spent"))["total"] or 0
                ),
            }
            recent_activity = AuditLog.objects.filter(actor=user).order_by("-created_at")[:8]

        activity_data = [
            {
                "id": item.pk,
                "event": item.event,
                "description": _activity_description(item),
                "created_at": item.created_at,
            }
            for item in recent_activity
        ]
        return Response({
            "user": UserSerializer(user).data,
            "role": role,
            "statistics": statistics,
            "permissions": permissions,
            "is_demo": bool(user.email and user.email.endswith("@kemta.invalid")),
            "projects": ProjectSerializer(projects, many=True, context={"request": request}).data,
            "tasks": ProjectTaskSerializer(tasks, many=True).data,
            "evidences": EvidenceSerializer(evidences, many=True, context={"request": request}).data,
            "service_requests": DashboardServiceRequestSerializer(service_requests, many=True).data,
            "company": CompanyProfileSerializer(company, context={"request": request}).data if company else None,
            "companies": CompanyProfileSerializer(companies, many=True, context={"request": request}).data,
            "opportunities": OpportunitySerializer(opportunities, many=True).data,
            "applications": ApplicationSerializer(applications, many=True).data,
            "notifications": NotificationSerializer(notifications, many=True).data,
            "recent_activity": activity_data,
            "generated_at": timezone.now(),
        })


def _activity_description(event: AuditLog) -> str:
    messages = {
        "service_request.created": "Une nouvelle demande a été enregistrée.",
        "service_request.updated": "Une demande a été mise à jour.",
        "project.created": "Un projet a été créé.",
        "project.updated": "Un projet a été mis à jour.",
        "evidence.uploaded": "Une nouvelle preuve terrain a été ajoutée.",
        "evidence.updated": "Une preuve terrain a été vérifiée.",
        "application.submitted": "Une candidature a été envoyée.",
        "application.status_changed": "Le statut d’une candidature a évolué.",
        "company.profile_saved": "Le profil entreprise a été enregistré.",
        "company.document_uploaded": "Une pièce du dossier entreprise a été ajoutée.",
        "company.verification_submitted": "Le dossier de vérification a été envoyé à KEMTA.",
        "company.review_started": "L’équipe KEMTA a pris en charge un dossier de vérification.",
        "company.verified": "L’entreprise a été vérifiée par KEMTA.",
        "company.verification_rejected": "Un dossier de vérification a été refusé.",
        "company.correction_requested": "Une correction a été demandée sur un dossier entreprise.",
        "company.document_approved": "Une pièce du dossier entreprise a été validée.",
        "company.document_rejected": "Une pièce du dossier entreprise a été refusée.",
        "company.suspended": "La vérification d’une entreprise a été suspendue.",
        "account.password_reset": "Le mot de passe du compte a été modifié.",
    }
    return messages.get(event.event, "Une activité a été enregistrée dans KEMTA.")


class FieldOperationsDashboardAPIView(APIView):
    """Vue agrégée, limitée et préchargée pour les consoles Chef/Agent.

    Les écrans opérationnels évitent ainsi d'ouvrir une requête par carte de
    mission tout en laissant les list endpoints paginés pour l'historique.
    """

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user
        today = timezone.localdate()
        mission_base = FieldMission.objects.select_related(
            "project", "phase", "task", "assigned_to", "created_by", "field_report"
        )
        report_base = FieldReport.objects.select_related(
            "mission", "mission__project", "submitted_by", "reviewed_by"
        )
        issue_base = ProjectIssue.objects.select_related("project", "mission", "reported_by", "assigned_to")
        notifications = Notification.objects.filter(user=user).only(
            "id", "notification_type", "title", "body", "action_url", "data", "read_at", "created_at"
        ).order_by("-created_at")[:8]

        if user.role == UserRole.PROJECT_MANAGER:
            projects = Project.objects.filter(manager=user)
            missions = mission_base.filter(project__manager=user)
            reports = report_base.filter(mission__project__manager=user)
            issues = issue_base.filter(project__manager=user)
            assignments = ProjectAssignment.objects.filter(project__manager=user).select_related("project", "user", "assigned_by")
            stats = {
                "active_projects": projects.filter(status=ProjectStatus.ACTIVE).count(),
                "missions_today": missions.filter(scheduled_start__date=today).exclude(status__in=(MissionStatus.APPROVED, MissionStatus.CANCELLED)).count(),
                "missions_in_progress": missions.filter(status=MissionStatus.IN_PROGRESS).count(),
                "reports_to_review": reports.filter(status__in=(FieldReportStatus.SUBMITTED, FieldReportStatus.UNDER_REVIEW)).count(),
                "open_issues": issues.exclude(status__in=(IssueStatus.RESOLVED, IssueStatus.CLOSED)).count(),
            }
            return Response({
                "role": user.role,
                "generated_at": timezone.now(),
                "statistics": stats,
                "today_missions": FieldMissionSerializer(
                    missions.filter(scheduled_start__date=today).order_by("scheduled_start")[:12], many=True
                ).data,
                "missions_in_progress": FieldMissionSerializer(
                    missions.filter(status__in=(MissionStatus.ACCEPTED, MissionStatus.IN_PROGRESS, MissionStatus.REVISION_REQUIRED)).order_by("scheduled_start")[:12], many=True
                ).data,
                "reports_to_review": FieldReportSerializer(
                    reports.filter(status__in=(FieldReportStatus.SUBMITTED, FieldReportStatus.UNDER_REVIEW)).order_by("submitted_at")[:12], many=True
                ).data,
                "open_issues": ProjectIssueSerializer(
                    issues.exclude(status__in=(IssueStatus.RESOLVED, IssueStatus.CLOSED)).order_by("-created_at")[:12], many=True
                ).data,
                "assignments": ProjectAssignmentSerializer(assignments.order_by("project__name", "user__last_name")[:24], many=True).data,
                "notifications": NotificationSerializer(notifications, many=True).data,
            })

        if user.role == UserRole.FIELD_AGENT:
            missions = mission_base.filter(assigned_to=user)
            reports = report_base.filter(submitted_by=user, mission__assigned_to=user)
            issues = issue_base.filter(Q(reported_by=user) | Q(assigned_to=user)).distinct()
            actionable = (MissionStatus.PLANNED, MissionStatus.ACCEPTED, MissionStatus.IN_PROGRESS, MissionStatus.REVISION_REQUIRED)
            stats = {
                "missions_today": missions.filter(scheduled_start__date=today, status__in=actionable).count(),
                "in_progress": missions.filter(status=MissionStatus.IN_PROGRESS).count(),
                "awaiting_correction": reports.filter(status=FieldReportStatus.REVISION_REQUIRED).count(),
                "open_issues": issues.exclude(status__in=(IssueStatus.RESOLVED, IssueStatus.CLOSED)).count(),
            }
            return Response({
                "role": user.role,
                "generated_at": timezone.now(),
                "statistics": stats,
                "today_missions": FieldMissionSerializer(
                    missions.filter(scheduled_start__date=today, status__in=actionable).order_by("scheduled_start")[:12], many=True
                ).data,
                "upcoming_missions": FieldMissionSerializer(
                    missions.filter(scheduled_start__date__gt=today, status__in=actionable).order_by("scheduled_start")[:12], many=True
                ).data,
                "reports_to_correct": FieldReportSerializer(
                    reports.filter(status=FieldReportStatus.REVISION_REQUIRED).order_by("-updated_at")[:8], many=True
                ).data,
                "my_open_issues": ProjectIssueSerializer(
                    issues.exclude(status__in=(IssueStatus.RESOLVED, IssueStatus.CLOSED)).order_by("-created_at")[:8], many=True
                ).data,
                "notifications": NotificationSerializer(notifications, many=True).data,
            })
        raise PermissionDenied("Ce dashboard est réservé aux Chefs de Projet et Agents Terrain.")
