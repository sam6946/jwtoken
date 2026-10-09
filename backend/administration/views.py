from datetime import timedelta

from django.db.models import Count, Max, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User, UserRole
from administration.models import (
    PlatformSetting,
    SupportMessage,
    SupportTicket,
    SupportTicketStatus,
)
from administration.permissions import IsKemtaAdmin, IsSuperAdmin, is_super_admin
from administration.serializers import (
    AdminAuditSerializer,
    AdminIssueSerializer,
    AdminMissionSerializer,
    AdminPaymentSerializer,
    AdminPlanSerializer,
    AdminProjectSerializer,
    AdminReportSerializer,
    AdminSubscriptionSerializer,
    AdminUserSerializer,
    PlatformSettingSerializer,
    SupportMessageSerializer,
    SupportTicketSerializer,
)
from common.models import AuditLog
from common.pagination import StandardPagination
from common.services import write_audit_event
from companies.models import CompanyProfile, CompanyVerificationStatus
from companies.serializers import CompanyReviewQueueSerializer
from notifications.models import Notification, NotificationType
from notifications.services import create_in_app_notification
from payments.models import (
    Payment,
    PaymentStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
)
from projects.models import (
    FieldMission,
    FieldReport,
    FieldReportStatus,
    MissionStatus,
    Project,
    ProjectIssue,
    ProjectStatus,
)
from service_requests.models import ServiceRequest, ServiceRequestStatus
from service_requests.serializers import ServiceRequestAdminSerializer


def _period(request):
    days = request.query_params.get("period", "30")
    try:
        days = int(days)
    except ValueError:
        days = 30
    return max(1, min(days, 365)), timezone.now() - timedelta(
        days=max(1, min(days, 365))
    )


def _paginate(request, queryset, serializer):
    pager = StandardPagination()
    page = pager.paginate_queryset(queryset, request)
    if page is None:
        return Response(
            serializer(queryset, many=True, context={"request": request}).data
        )
    return pager.get_paginated_response(
        serializer(page, many=True, context={"request": request}).data
    )


class AdminDashboardAPIView(APIView):
    permission_classes = (IsKemtaAdmin,)

    def get(self, request):
        days, since = _period(request)
        today = timezone.localdate()
        users = User.objects.all()
        projects = Project.objects.all()
        missions = FieldMission.objects.all()
        reports = FieldReport.objects.all()
        issues = ProjectIssue.objects.all()
        payments = Payment.objects.all()
        stats = {
            "users_total": users.count(),
            "users_active": users.filter(is_active=True).count(),
            "users_new": users.filter(created_at__gte=since).count(),
            "companies_total": CompanyProfile.objects.count(),
            "companies_pending": CompanyProfile.objects.filter(
                verification_status__in=(
                    CompanyVerificationStatus.PENDING,
                    CompanyVerificationStatus.UNDER_REVIEW,
                )
            ).count(),
            "companies_verified": CompanyProfile.objects.filter(
                verification_status=CompanyVerificationStatus.VERIFIED
            ).count(),
            "projects_active": projects.filter(status=ProjectStatus.ACTIVE).count(),
            "projects_overdue": projects.filter(
                status=ProjectStatus.ACTIVE, planned_end__lt=today
            ).count(),
            "requests_pending": ServiceRequest.objects.filter(
                status__in=(
                    ServiceRequestStatus.NEW,
                    ServiceRequestStatus.IN_REVIEW,
                    ServiceRequestStatus.CONTACTED,
                )
            ).count(),
            "missions_in_progress": missions.filter(
                status=MissionStatus.IN_PROGRESS
            ).count(),
            "reports_to_review": reports.filter(
                status__in=(FieldReportStatus.SUBMITTED, FieldReportStatus.UNDER_REVIEW)
            ).count(),
            "issues_critical": issues.filter(priority="CRITICAL")
            .exclude(status__in=("RESOLVED", "CLOSED"))
            .count(),
            "payments_pending": payments.filter(
                status__in=(PaymentStatus.CREATED, PaymentStatus.PENDING)
            ).count(),
            "payments_failed": payments.filter(status=PaymentStatus.FAILED).count(),
            "revenue_succeeded": str(
                payments.filter(status=PaymentStatus.SUCCEEDED).aggregate(
                    total=Sum("amount")
                )["total"]
                or 0
            ),
            "subscriptions_active": Subscription.objects.filter(
                status=SubscriptionStatus.ACTIVE
            ).count(),
            "subscriptions_expiring": Subscription.objects.filter(
                status=SubscriptionStatus.ACTIVE,
                ends_at__date__range=(today, today + timedelta(days=14)),
            ).count(),
        }
        series = []
        for offset in range(min(days, 90) - 1, -1, -1):
            date = today - timedelta(days=offset)
            series.append(
                {
                    "date": date.isoformat(),
                    "users": users.filter(created_at__date=date).count(),
                    "projects": projects.filter(created_at__date=date).count(),
                    "requests": ServiceRequest.objects.filter(
                        created_at__date=date
                    ).count(),
                }
            )
        alerts = []
        for company in CompanyProfile.objects.filter(
            verification_status__in=(
                CompanyVerificationStatus.PENDING,
                CompanyVerificationStatus.UNDER_REVIEW,
            )
        ).order_by("verification_submitted_at")[:5]:
            alerts.append(
                {
                    "type": "company",
                    "severity": "MEDIUM",
                    "title": "Entreprise à vérifier",
                    "detail": company.name,
                    "date": company.verification_submitted_at,
                    "href": "/administration/companies?verification=PENDING",
                }
            )
        for issue in (
            issues.filter(priority="CRITICAL")
            .exclude(status__in=("RESOLVED", "CLOSED"))
            .select_related("project")[:5]
        ):
            alerts.append(
                {
                    "type": "issue",
                    "severity": "CRITICAL",
                    "title": "Incident critique",
                    "detail": f"{issue.title} · {issue.project.name}",
                    "date": issue.created_at,
                    "href": "/administration/incidents?priority=CRITICAL",
                }
            )
        for project in projects.filter(
            status=ProjectStatus.ACTIVE, planned_end__lt=today
        ).select_related("owner")[:5]:
            alerts.append(
                {
                    "type": "project",
                    "severity": "HIGH",
                    "title": "Échéance dépassée",
                    "detail": project.name,
                    "date": project.planned_end,
                    "href": "/administration/projects?overdue=1",
                }
            )
        return Response(
            {
                "period_days": days,
                "statistics": stats,
                "series": series,
                "alerts": sorted(
                    alerts, key=lambda item: str(item["date"]), reverse=True
                )[:12],
            }
        )


class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AdminUserSerializer
    permission_classes = (IsKemtaAdmin,)

    def get_queryset(self):
        query = User.objects.annotate(
            last_audit_at=Max("audit_events__created_at")
        ).order_by("-created_at")
        search = self.request.query_params.get("search", "").strip()
        if search:
            query = query.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(email__icontains=search)
            )
        for field in ("role", "is_active", "phone_verified"):
            value = self.request.query_params.get(field)
            if value not in (None, ""):
                query = query.filter(**{field: value})
        return query

    @action(detail=True, methods=("post",), url_path="status")
    def update_status(self, request, pk=None):
        target = self.get_object()
        active = request.data.get("is_active")
        if not isinstance(active, bool):
            raise ValidationError({"is_active": "Une valeur booléenne est requise."})
        if target.pk == request.user.pk:
            raise PermissionDenied("Vous ne pouvez pas suspendre votre propre compte.")
        if not is_super_admin(request.user) and target.role in {
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        }:
            raise PermissionDenied(
                "Seul le Super Admin gère les comptes administrateurs."
            )
        target.is_active = active
        target.save(update_fields=("is_active", "updated_at"))
        write_audit_event(
            event="account.activated" if active else "account.suspended",
            actor=request.user,
            object_type="user",
            object_id=target.pk,
            metadata={"role": target.role},
            request_id=getattr(request, "request_id", ""),
        )
        return Response(self.get_serializer(target).data)


class AdminCollectionAPIView(APIView):
    permission_classes = (IsKemtaAdmin,)

    def get(self, request, resource):
        data = {
            "companies": (
                CompanyProfile.objects.select_related(
                    "user", "verification_reviewed_by"
                ).prefetch_related("documents"),
                CompanyReviewQueueSerializer,
            ),
            "projects": (
                Project.objects.select_related("owner", "manager")
                .annotate(
                    open_issues=Count(
                        "issues", filter=~Q(issues__status__in=("RESOLVED", "CLOSED"))
                    )
                )
                .order_by("-updated_at"),
                AdminProjectSerializer,
            ),
            "requests": (
                ServiceRequest.objects.select_related("owner")
                .prefetch_related("attachments")
                .order_by("-created_at"),
                ServiceRequestAdminSerializer,
            ),
            "missions": (
                FieldMission.objects.select_related("project", "assigned_to").order_by(
                    "-scheduled_start"
                ),
                AdminMissionSerializer,
            ),
            "reports": (
                FieldReport.objects.select_related(
                    "mission", "mission__project", "submitted_by"
                ).order_by("-updated_at"),
                AdminReportSerializer,
            ),
            "incidents": (
                ProjectIssue.objects.select_related("project", "reported_by").order_by(
                    "-created_at"
                ),
                AdminIssueSerializer,
            ),
            "payments": (
                Payment.objects.select_related(
                    "owner", "subscription", "subscription__plan"
                ).order_by("-created_at"),
                AdminPaymentSerializer,
            ),
            "subscriptions": (
                Subscription.objects.select_related("company", "plan").order_by(
                    "-created_at"
                ),
                AdminSubscriptionSerializer,
            ),
            "plans": (SubscriptionPlan.objects.all(), AdminPlanSerializer),
            "audit": (
                AuditLog.objects.select_related("actor").order_by("-created_at"),
                AdminAuditSerializer,
            ),
        }
        if resource not in data:
            raise ValidationError({"resource": "Ressource administrative inconnue."})
        queryset, serializer = data[resource]
        filter_fields = {
            "companies": ("verification_status",),
            "projects": ("status",),
            "requests": ("status",),
            "missions": ("status", "project", "assigned_to"),
            "reports": ("status", "mission"),
            "incidents": ("status", "priority", "project", "assigned_to"),
            "payments": ("status", "provider"),
            "subscriptions": ("status", "plan"),
            "plans": ("tier", "is_active"),
        }.get(resource, ())
        for key in filter_fields:
            value = request.query_params.get(key)
            if value not in (None, ""):
                queryset = queryset.filter(**{key: value})
        search = request.query_params.get("search", "").strip()
        search_filters = {
            "companies": Q(name__icontains=search)
            | Q(city__icontains=search)
            | Q(user__phone__icontains=search),
            "projects": Q(name__icontains=search) | Q(city__icontains=search),
            "requests": Q(request_code__icontains=search)
            | Q(phone__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search),
            "missions": Q(title__icontains=search)
            | Q(project__name__icontains=search)
            | Q(assigned_to__phone__icontains=search),
            "reports": Q(mission__title__icontains=search)
            | Q(mission__project__name__icontains=search)
            | Q(submitted_by__phone__icontains=search),
            "incidents": Q(title__icontains=search)
            | Q(project__name__icontains=search)
            | Q(reported_by__phone__icontains=search),
            "payments": Q(provider_reference__icontains=search)
            | Q(owner__phone__icontains=search)
            | Q(description__icontains=search),
            "subscriptions": Q(company__name__icontains=search)
            | Q(plan__name__icontains=search),
            "plans": Q(code__icontains=search) | Q(name__icontains=search),
            "audit": Q(event__icontains=search)
            | Q(object_id__icontains=search)
            | Q(actor__phone__icontains=search),
        }
        if search and resource in search_filters:
            queryset = queryset.filter(search_filters[resource])
        return _paginate(request, queryset, serializer)


class AdminSearchAPIView(APIView):
    permission_classes = (IsKemtaAdmin,)

    def get(self, request):
        term = request.query_params.get("q", "").strip()
        if len(term) < 2:
            return Response({"results": []})
        results = []
        for user in User.objects.filter(
            Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(phone__icontains=term)
        )[:5]:
            results.append(
                {
                    "type": "user",
                    "id": user.pk,
                    "label": f"{user.first_name} {user.last_name}",
                    "meta": user.phone,
                    "href": f"/administration/users?search={user.phone}",
                }
            )
        for project in Project.objects.filter(
            Q(name__icontains=term) | Q(city__icontains=term)
        )[:5]:
            results.append(
                {
                    "type": "project",
                    "id": project.pk,
                    "label": project.name,
                    "meta": project.city,
                    "href": f"/administration/projects?search={project.name}",
                }
            )
        for company in CompanyProfile.objects.filter(
            Q(name__icontains=term) | Q(city__icontains=term)
        )[:5]:
            results.append(
                {
                    "type": "company",
                    "id": company.pk,
                    "label": company.name,
                    "meta": company.city,
                    "href": f"/administration/companies?search={company.name}",
                }
            )
        for mission in FieldMission.objects.filter(
            title__icontains=term
        ).select_related("project")[:5]:
            results.append(
                {
                    "type": "mission",
                    "id": mission.pk,
                    "label": mission.title,
                    "meta": mission.project.name,
                    "href": f"/administration/missions?search={mission.title}",
                }
            )
        return Response({"results": results[:15]})


class AdminNotificationAPIView(APIView):
    permission_classes = (IsKemtaAdmin,)

    def post(self, request):
        recipients = request.data.get("recipients", [])
        title = str(request.data.get("title", "")).strip()
        body = str(request.data.get("body", "")).strip()
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key or len(idempotency_key) > 96:
            raise ValidationError(
                {"Idempotency-Key": "Une clé d’idempotence valide est requise."}
            )
        if not title or not isinstance(recipients, list) or len(recipients) > 100:
            raise ValidationError("Titre et jusqu’à 100 destinataires sont requis.")
        users = User.objects.filter(pk__in=recipients, is_active=True)
        sent = 0
        for recipient in users:
            dedupe_key = f"admin-message-{idempotency_key}-{recipient.pk}"
            if Notification.objects.filter(
                user=recipient, dedupe_key=dedupe_key
            ).exists():
                continue
            create_in_app_notification(
                user=recipient,
                title=title,
                body=body,
                notification_type=NotificationType.GENERAL,
                dedupe_key=dedupe_key,
            )
            sent += 1
        if sent:
            write_audit_event(
                event="admin.notification_sent",
                actor=request.user,
                object_type="notification",
                metadata={"recipient_count": sent},
                request_id=getattr(request, "request_id", ""),
            )
        return Response({"sent": sent, "targeted": users.count()})


class SupportTicketViewSet(viewsets.ModelViewSet):
    serializer_class = SupportTicketSerializer
    permission_classes = (IsKemtaAdmin,)
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        query = SupportTicket.objects.select_related(
            "requester", "assigned_to"
        ).prefetch_related("messages", "messages__author")
        for key in ("status", "priority", "assigned_to"):
            value = self.request.query_params.get(key)
            if value:
                query = query.filter(**{key: value})
        search = self.request.query_params.get("search", "").strip()
        if search:
            query = query.filter(
                Q(subject__icontains=search)
                | Q(description__icontains=search)
                | Q(requester__phone__icontains=search)
            )
        return query

    def perform_create(self, serializer):
        requester = serializer.validated_data.get("requester", self.request.user)
        ticket = serializer.save(requester=requester)
        write_audit_event(
            event="support.ticket_created",
            actor=self.request.user,
            object_type="support_ticket",
            object_id=ticket.pk,
        )

    def perform_update(self, serializer):
        ticket = serializer.save()
        if (
            ticket.status in {SupportTicketStatus.RESOLVED, SupportTicketStatus.CLOSED}
            and not ticket.resolved_at
        ):
            ticket.resolved_at = timezone.now()
            ticket.save(update_fields=("resolved_at", "updated_at"))
        write_audit_event(
            event="support.ticket_updated",
            actor=self.request.user,
            object_type="support_ticket",
            object_id=ticket.pk,
        )

    @action(detail=True, methods=("post",), url_path="messages")
    def add_message(self, request, pk=None):
        ticket = self.get_object()
        serializer = SupportMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = SupportMessage.objects.create(
            ticket=ticket,
            author=request.user,
            body=serializer.validated_data["body"],
            is_internal=bool(request.data.get("is_internal", False)),
        )
        write_audit_event(
            event="support.message_added",
            actor=request.user,
            object_type="support_ticket",
            object_id=ticket.pk,
            metadata={"internal": message.is_internal},
        )
        return Response(
            SupportMessageSerializer(message).data, status=status.HTTP_201_CREATED
        )


class PlatformSettingViewSet(viewsets.ModelViewSet):
    serializer_class = PlatformSettingSerializer
    permission_classes = (IsSuperAdmin,)
    http_method_names = ("get", "post", "patch", "head", "options")
    queryset = PlatformSetting.objects.all()

    def perform_create(self, serializer):
        setting = serializer.save(updated_by=self.request.user)
        write_audit_event(
            event="platform.setting_created",
            actor=self.request.user,
            object_type="platform_setting",
            object_id=setting.pk,
        )

    def perform_update(self, serializer):
        setting = serializer.save(updated_by=self.request.user)
        write_audit_event(
            event="platform.setting_updated",
            actor=self.request.user,
            object_type="platform_setting",
            object_id=setting.pk,
        )


class AdminCsvExportAPIView(APIView):
    permission_classes = (IsKemtaAdmin,)

    def get(self, request, resource):
        rows = {
            "users": (
                User.objects.order_by("id")[:5000],
                (
                    "id",
                    "phone",
                    "first_name",
                    "last_name",
                    "role",
                    "is_active",
                    "created_at",
                ),
            ),
            "projects": (
                Project.objects.order_by("id")[:5000],
                ("id", "name", "city", "status", "progress", "planned_end"),
            ),
            "missions": (
                FieldMission.objects.order_by("id")[:5000],
                (
                    "id",
                    "title",
                    "status",
                    "scheduled_start",
                    "assigned_to_id",
                    "project_id",
                ),
            ),
        }
        if resource not in rows:
            raise ValidationError("Cet export n’est pas autorisé.")
        import csv

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="kemta-{resource}.csv"'
        writer = csv.writer(response)
        fields = rows[resource][1]
        writer.writerow(fields)
        for obj in rows[resource][0]:
            writer.writerow([getattr(obj, field) for field in fields])
        write_audit_event(
            event="admin.data_exported",
            actor=request.user,
            object_type=resource,
            metadata={"format": "csv"},
        )
        return response
