from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.models import KemtaPermission, UserRole
from accounts.permissions import has_kemta_permission
from common.services import write_audit_event
from projects.models import (
    Evidence,
    FieldMission,
    FieldReport,
    FieldReportStatus,
    PhaseStatus,
    Project,
    ProjectAssignment,
    ProjectExpense,
    ProjectIssue,
    ProjectPhase,
    ProjectReport,
    ProjectTask,
)
from projects.permissions import (
    EvidenceAccessPermission,
    FieldMissionPermission,
    FieldReportPermission,
    ProjectAccessPermission,
    ProjectAssignmentPermission,
    ProjectChildAccessPermission,
    ProjectExpenseAccessPermission,
    ProjectIssuePermission,
    can_access_mission,
    can_access_project,
    can_manage_all,
    is_project_manager,
)
from projects.serializers import (
    EvidenceSerializer,
    FieldMissionSerializer,
    FieldReportSerializer,
    MissionStartSerializer,
    ProjectAssignmentSerializer,
    ProjectDetailSerializer,
    ProjectExpenseSerializer,
    ProjectIssueSerializer,
    ProjectReportSerializer,
    ProjectSerializer,
    ProjectTaskSerializer,
    RevisionRequestSerializer,
)
from projects.field_workflow import (
    accept_mission,
    approve_field_report,
    assign_agent,
    create_mission,
    request_report_revision,
    start_mission,
    start_report_review,
    submit_field_report,
)

_DEFAULT_PHASES = (
    "Étude & préparation",
    "Fondations",
    "Structure & murs",
    "Toiture",
    "Électricité",
    "Plomberie",
    "Finitions",
    "Livraison",
)


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = (ProjectAccessPermission,)
    http_method_names = ("get", "post", "patch", "put", "head", "options")

    def get_queryset(self):
        user = self.request.user
        queryset = Project.objects.select_related("owner", "manager").prefetch_related("phases", "field_agents").order_by("-updated_at")
        if can_manage_all(user):
            return queryset
        return queryset.filter(Q(owner=user) | Q(manager=user) | Q(field_agents=user)).distinct()

    def get_serializer_class(self):
        # La fiche projet complète (budget, dépenses, reçus, demandes liées) n'est servie
        # qu'au détail : la liste reste légère.
        if self.action == "retrieve":
            return ProjectDetailSerializer
        return ProjectSerializer

    def perform_create(self, serializer):
        if not has_kemta_permission(self.request.user, KemtaPermission.MANAGE_PROJECT):
            raise PermissionDenied("La création de projets est réservée aux responsables KEMTA.")
        with transaction.atomic():
            project = serializer.save(manager=self.request.user)
            for agent in serializer.validated_data.get("field_agents", []):
                assign_agent(project=project, agent=agent, actor=self.request.user, request_id=getattr(self.request, "request_id", ""))
            ProjectPhase.objects.bulk_create([
                ProjectPhase(
                    project=project,
                    name=name,
                    position=index,
                    status=PhaseStatus.CURRENT if index == 1 else PhaseStatus.UPCOMING,
                )
                for index, name in enumerate(_DEFAULT_PHASES, start=1)
            ])
            project.current_phase = _DEFAULT_PHASES[0]
            project.save(update_fields=("current_phase", "updated_at"))
            write_audit_event(
                event="project.created",
                actor=self.request.user,
                object_type="project",
                object_id=project.pk,
                request_id=getattr(self.request, "request_id", ""),
            )

    def perform_update(self, serializer):
        selected_agents = serializer.validated_data.get("field_agents")
        project = serializer.save()
        if selected_agents is not None:
            for agent in selected_agents:
                assign_agent(project=project, agent=agent, actor=self.request.user, request_id=getattr(self.request, "request_id", ""))
        write_audit_event(
            event="project.updated",
            actor=self.request.user,
            object_type="project",
            object_id=project.pk,
            request_id=getattr(self.request, "request_id", ""),
        )

    @action(detail=True, methods=("get",), url_path="evidences")
    def evidences(self, request, pk=None):
        project = self.get_object()
        evidences = Evidence.objects.filter(project=project).select_related("phase", "uploaded_by")[:30]
        return Response(EvidenceSerializer(evidences, many=True, context={"request": request}).data)


class EvidenceViewSet(viewsets.ModelViewSet):
    serializer_class = EvidenceSerializer
    permission_classes = (EvidenceAccessPermission,)
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    http_method_names = ("get", "post", "patch", "put", "head", "options")

    def get_queryset(self):
        user = self.request.user
        queryset = Evidence.objects.select_related("project", "phase", "mission", "issue", "uploaded_by").order_by("-created_at")
        project_id = self.request.query_params.get("project")
        mission_id = self.request.query_params.get("mission")
        if can_manage_all(user):
            pass
        elif user.role == UserRole.FIELD_AGENT:
            # Une preuve missionnelle ne doit jamais exposer la visite d'un autre agent.
            queryset = queryset.filter(Q(uploaded_by=user) | Q(mission__assigned_to=user)).distinct()
        else:
            visible_projects = Project.objects.filter(Q(owner=user) | Q(manager=user)).values("id")
            queryset = queryset.filter(project_id__in=visible_projects)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if mission_id:
            queryset = queryset.filter(mission_id=mission_id)
        return queryset

    def create(self, request, *args, **kwargs):
        reference = request.data.get("client_reference") or request.headers.get("Idempotency-Key", "")[:64]
        if reference:
            existing = Evidence.objects.filter(uploaded_by=request.user, client_reference=reference).first()
            if existing:
                return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)
        payload = request.data.copy()
        if reference:
            payload["client_reference"] = reference
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=self.get_success_headers(serializer.data))

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        mission = serializer.validated_data.get("mission")
        if self.request.user.role == UserRole.FIELD_AGENT:
            if mission is None or mission.assigned_to_id != self.request.user.id:
                raise PermissionDenied("Un agent doit joindre une preuve à l’une de ses propres missions.")
        elif not is_project_manager(self.request.user, project):
            raise PermissionDenied("Cette preuve ne peut pas être ajoutée à ce projet.")
        evidence = serializer.save(uploaded_by=self.request.user)
        write_audit_event(
            event="evidence.uploaded",
            actor=self.request.user,
            object_type="evidence",
            object_id=evidence.pk,
            metadata={"project_id": project.pk, "mission_id": evidence.mission_id, "evidence_type": evidence.evidence_type},
            request_id=getattr(self.request, "request_id", ""),
        )
        if evidence.image:
            transaction.on_commit(lambda: self._queue_image_processing(evidence.pk))

    def _queue_image_processing(self, evidence_id: int) -> None:
        from projects.tasks import process_evidence_images

        process_evidence_images.delay(evidence_id)

    def perform_update(self, serializer):
        previous_status = serializer.instance.verification_status
        evidence = serializer.save()
        write_audit_event(
            event="evidence.updated",
            actor=self.request.user,
            object_type="evidence",
            object_id=evidence.pk,
            metadata={"previous_status": previous_status, "status": evidence.verification_status},
            request_id=getattr(self.request, "request_id", ""),
        )


class ProjectTaskViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectTaskSerializer
    permission_classes = (ProjectChildAccessPermission,)

    def get_queryset(self):
        user = self.request.user
        queryset = ProjectTask.objects.select_related("project", "phase", "assigned_to")
        if can_manage_all(user):
            return queryset
        return queryset.filter(Q(project__owner=user) | Q(project__manager=user) | Q(assigned_to=user)).distinct()

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not can_access_project(self.request.user, project) or not has_kemta_permission(self.request.user, KemtaPermission.MANAGE_PROJECT):
            raise PermissionDenied("Vous ne pouvez pas créer une tâche sur ce projet.")
        task = serializer.save()
        write_audit_event(event="project_task.created", actor=self.request.user, object_type="project_task", object_id=task.pk)


class ProjectReportViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectReportSerializer
    permission_classes = (ProjectChildAccessPermission,)
    http_method_names = ("get", "post", "head", "options")
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_queryset(self):
        user = self.request.user
        queryset = ProjectReport.objects.select_related("project", "author")
        if can_manage_all(user):
            return queryset
        return queryset.filter(Q(project__owner=user) | Q(project__manager=user)).distinct()

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not can_access_project(self.request.user, project) or not has_kemta_permission(self.request.user, KemtaPermission.MANAGE_PROJECT):
            raise PermissionDenied("Vous ne pouvez pas créer un rapport sur ce projet.")
        report = serializer.save(author=self.request.user)
        project.last_report_at = report.created_at
        project.save(update_fields=("last_report_at", "updated_at"))
        write_audit_event(event="project_report.created", actor=self.request.user, object_type="project_report", object_id=report.pk)


class ProjectExpenseViewSet(viewsets.ModelViewSet):
    """Dépenses d'un chantier, filtrables par projet.

    Le justificatif n'est jamais exposé par une URL publique : il se télécharge
    depuis l'action `receipt`, qui revérifie les droits sur le projet.
    """

    serializer_class = ProjectExpenseSerializer
    permission_classes = (ProjectExpenseAccessPermission,)
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    http_method_names = ("get", "post", "patch", "put", "head", "options")

    def get_queryset(self):
        user = self.request.user
        queryset = ProjectExpense.objects.select_related("project", "recorded_by").order_by("-spent_at", "-id")
        if not can_manage_all(user):
            visible_projects = Project.objects.filter(
                Q(owner=user) | Q(manager=user) | Q(field_agents=user)
            ).values("id")
            queryset = queryset.filter(project_id__in=visible_projects)
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        status_filter = self.request.query_params.get("status")
        if status_filter in dict(ProjectExpense._meta.get_field("status").choices):
            queryset = queryset.filter(status=status_filter)
        return queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not can_access_project(self.request.user, project):
            raise PermissionDenied("Cette dépense ne peut pas être ajoutée à ce projet.")
        receipt = serializer.validated_data.get("receipt")
        expense = serializer.save(
            recorded_by=self.request.user,
            receipt_original_name=getattr(receipt, "name", "")[:255],
        )
        write_audit_event(
            event="project_expense.created",
            actor=self.request.user,
            object_type="project_expense",
            object_id=expense.pk,
            metadata={"project_id": project.pk, "amount": str(expense.amount)},
            request_id=getattr(self.request, "request_id", ""),
        )

    def perform_update(self, serializer):
        receipt = serializer.validated_data.get("receipt")
        expense = serializer.save(
            receipt_original_name=getattr(receipt, "name", expense.receipt_original_name)[:255]
            if receipt
            else expense.receipt_original_name
        )
        write_audit_event(
            event="project_expense.updated",
            actor=self.request.user,
            object_type="project_expense",
            object_id=expense.pk,
            metadata={"project_id": expense.project_id, "status": expense.status},
            request_id=getattr(self.request, "request_id", ""),
        )

    @action(detail=True, methods=("get",), url_path="receipt")
    def receipt(self, request, pk=None):
        """Télécharge le justificatif après vérification des droits sur le projet."""
        expense = self.get_object()
        if not expense.receipt:
            raise NotFound("Aucun justificatif n’est joint à cette dépense.")
        filename = expense.receipt_original_name or expense.receipt.name.rsplit("/", 1)[-1]
        return FileResponse(expense.receipt.open("rb"), as_attachment=True, filename=filename)


class ProjectAssignmentViewSet(viewsets.ModelViewSet):
    """Affectations explicites pilotées uniquement par le chef du projet."""

    serializer_class = ProjectAssignmentSerializer
    permission_classes = (ProjectAssignmentPermission,)
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        user = self.request.user
        queryset = ProjectAssignment.objects.select_related("project", "user", "assigned_by").order_by("-created_at")
        if can_manage_all(user):
            return queryset
        return queryset.filter(project__manager=user)

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not is_project_manager(self.request.user, project):
            raise PermissionDenied("Vous ne pilotez pas ce projet.")
        assignment = assign_agent(
            project=project,
            agent=serializer.validated_data["user"],
            actor=self.request.user,
            start_date=serializer.validated_data.get("start_date"),
            end_date=serializer.validated_data.get("end_date"),
            request_id=getattr(self.request, "request_id", ""),
        )
        serializer.instance = assignment

    def perform_update(self, serializer):
        assignment = serializer.save()
        if assignment.status == "ACTIVE":
            assignment.project.field_agents.add(assignment.user)
        write_audit_event(
            event="project.assignment_updated",
            actor=self.request.user,
            object_type="project_assignment",
            object_id=assignment.pk,
            metadata={"project_id": assignment.project_id, "agent_id": assignment.user_id, "status": assignment.status},
            request_id=getattr(self.request, "request_id", ""),
        )


class FieldMissionViewSet(viewsets.ModelViewSet):
    serializer_class = FieldMissionSerializer
    permission_classes = (FieldMissionPermission,)
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        user = self.request.user
        queryset = FieldMission.objects.select_related(
            "project", "phase", "task", "assigned_to", "created_by", "field_report"
        ).order_by("scheduled_start", "-created_at")
        if can_manage_all(user):
            pass
        elif user.role == UserRole.FIELD_AGENT:
            queryset = queryset.filter(assigned_to=user)
        else:
            queryset = queryset.filter(project__manager=user)
        for field in ("project", "status", "assigned_to"):
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{f"{field}_id" if field == "project" else field: value})
        return queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not is_project_manager(self.request.user, project):
            raise PermissionDenied("Vous ne pilotez pas ce projet.")
        mission = create_mission(
            actor=self.request.user,
            request_id=getattr(self.request, "request_id", ""),
            **serializer.validated_data,
        )
        serializer.instance = mission

    def perform_update(self, serializer):
        mission = self.get_object()
        if not is_project_manager(self.request.user, mission.project):
            raise PermissionDenied("Seul le chef de projet peut modifier la planification.")
        if mission.status not in {"PLANNED", "ACCEPTED"}:
            raise PermissionDenied("Une mission déjà exécutée ne peut plus être replanifiée.")
        serializer.save()
        write_audit_event(
            event="field_mission.updated",
            actor=self.request.user,
            object_type="field_mission",
            object_id=mission.pk,
            request_id=getattr(self.request, "request_id", ""),
        )

    @action(detail=True, methods=("post",), url_path="accept")
    def accept(self, request, pk=None):
        mission = self.get_object()
        if mission.assigned_to_id != request.user.id:
            raise PermissionDenied("Seul l’agent affecté peut accepter cette mission.")
        return Response(FieldMissionSerializer(accept_mission(mission, actor=request.user, request_id=getattr(request, "request_id", ""))).data)

    @action(detail=True, methods=("post",), url_path="start")
    def start(self, request, pk=None):
        mission = self.get_object()
        if mission.assigned_to_id != request.user.id:
            raise PermissionDenied("Seul l’agent affecté peut démarrer cette mission.")
        payload = MissionStartSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        started = start_mission(mission, actor=request.user, request_id=getattr(request, "request_id", ""), **payload.validated_data)
        return Response(FieldMissionSerializer(started).data)


class FieldReportViewSet(viewsets.ModelViewSet):
    serializer_class = FieldReportSerializer
    permission_classes = (FieldReportPermission,)
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        user = self.request.user
        queryset = FieldReport.objects.select_related(
            "mission", "mission__project", "submitted_by", "reviewed_by"
        ).order_by("-updated_at")
        if can_manage_all(user):
            pass
        elif user.role == UserRole.FIELD_AGENT:
            queryset = queryset.filter(submitted_by=user, mission__assigned_to=user)
        else:
            queryset = queryset.filter(mission__project__manager=user)
        mission_id = self.request.query_params.get("mission")
        status_filter = self.request.query_params.get("status")
        if mission_id:
            queryset = queryset.filter(mission_id=mission_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def create(self, request, *args, **kwargs):
        reference = request.data.get("client_reference") or request.headers.get("Idempotency-Key", "")[:64]
        mission_id = request.data.get("mission")
        if mission_id:
            existing = FieldReport.objects.filter(mission_id=mission_id).first()
            if existing and existing.submitted_by_id == request.user.id and (not reference or existing.client_reference == reference):
                return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)
        payload = request.data.copy()
        if reference:
            payload["client_reference"] = reference
            duplicate = FieldReport.objects.filter(submitted_by=request.user, client_reference=reference).first()
            if duplicate:
                return Response(self.get_serializer(duplicate).data, status=status.HTTP_200_OK)
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        mission = serializer.validated_data["mission"]
        if mission.assigned_to_id != request.user.id:
            raise PermissionDenied("Vous ne pouvez rédiger qu’un rapport pour votre propre mission.")
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=self.get_success_headers(serializer.data))

    def perform_create(self, serializer):
        report = serializer.save(submitted_by=self.request.user)
        write_audit_event(
            event="field_report.draft_created",
            actor=self.request.user,
            object_type="field_report",
            object_id=report.pk,
            metadata={"mission_id": report.mission_id},
            request_id=getattr(self.request, "request_id", ""),
        )

    def perform_update(self, serializer):
        report = self.get_object()
        if report.submitted_by_id != self.request.user.id or report.status not in {FieldReportStatus.DRAFT, FieldReportStatus.REVISION_REQUIRED}:
            raise PermissionDenied("Seul l’auteur peut modifier un brouillon ou un rapport à corriger.")
        serializer.save()
        write_audit_event(
            event="field_report.updated",
            actor=self.request.user,
            object_type="field_report",
            object_id=report.pk,
            request_id=getattr(self.request, "request_id", ""),
        )

    @action(detail=True, methods=("post",), url_path="submit")
    def submit(self, request, pk=None):
        report = self.get_object()
        if report.submitted_by_id != request.user.id:
            raise PermissionDenied("Seul l’auteur peut soumettre ce rapport.")
        return Response(FieldReportSerializer(submit_field_report(report, actor=request.user, request_id=getattr(request, "request_id", ""))).data)

    @action(detail=True, methods=("post",), url_path="start-review")
    def start_review(self, request, pk=None):
        report = self.get_object()
        if not is_project_manager(request.user, report.mission.project) or report.submitted_by_id == request.user.id:
            raise PermissionDenied("Un chef de projet distinct de l’auteur est requis pour la revue.")
        return Response(FieldReportSerializer(start_report_review(report, actor=request.user, request_id=getattr(request, "request_id", ""))).data)

    @action(detail=True, methods=("post",), url_path="approve")
    def approve(self, request, pk=None):
        report = self.get_object()
        if not is_project_manager(request.user, report.mission.project) or report.submitted_by_id == request.user.id:
            raise PermissionDenied("Un chef de projet distinct de l’auteur est requis pour la validation.")
        return Response(FieldReportSerializer(approve_field_report(report, actor=request.user, request_id=getattr(request, "request_id", ""))).data)

    @action(detail=True, methods=("post",), url_path="request-revision")
    def request_revision(self, request, pk=None):
        report = self.get_object()
        if not is_project_manager(request.user, report.mission.project) or report.submitted_by_id == request.user.id:
            raise PermissionDenied("Un chef de projet distinct de l’auteur est requis pour demander une correction.")
        payload = RevisionRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        revised = request_report_revision(
            report,
            actor=request.user,
            reason=payload.validated_data["reason"],
            request_id=getattr(request, "request_id", ""),
        )
        return Response(FieldReportSerializer(revised).data)


class ProjectIssueViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectIssueSerializer
    permission_classes = (ProjectIssuePermission,)
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        user = self.request.user
        queryset = ProjectIssue.objects.select_related(
            "project", "mission", "reported_by", "assigned_to"
        ).order_by("-created_at")
        if can_manage_all(user):
            pass
        elif user.role == UserRole.FIELD_AGENT:
            queryset = queryset.filter(Q(reported_by=user) | Q(assigned_to=user)).distinct()
        else:
            queryset = queryset.filter(project__manager=user)
        project_id = self.request.query_params.get("project")
        mission_id = self.request.query_params.get("mission")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if mission_id:
            queryset = queryset.filter(mission_id=mission_id)
        return queryset

    def create(self, request, *args, **kwargs):
        reference = request.data.get("client_reference") or request.headers.get("Idempotency-Key", "")[:64]
        if reference:
            existing = ProjectIssue.objects.filter(reported_by=request.user, client_reference=reference).first()
            if existing:
                return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)
        payload = request.data.copy()
        if reference:
            payload["client_reference"] = reference
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=self.get_success_headers(serializer.data))

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        mission = serializer.validated_data.get("mission")
        if self.request.user.role == UserRole.FIELD_AGENT:
            if mission is None or mission.assigned_to_id != self.request.user.id:
                raise PermissionDenied("Un agent ne peut signaler un problème que depuis sa propre mission.")
        elif not is_project_manager(self.request.user, project):
            raise PermissionDenied("Vous ne pilotez pas ce projet.")
        issue = serializer.save(reported_by=self.request.user)
        write_audit_event(
            event="project_issue.created",
            actor=self.request.user,
            object_type="project_issue",
            object_id=issue.pk,
            metadata={"project_id": issue.project_id, "mission_id": issue.mission_id, "priority": issue.priority},
            request_id=getattr(self.request, "request_id", ""),
        )
        if issue.project.manager_id and issue.project.manager_id != self.request.user.id:
            from notifications.services import create_in_app_notification
            from notifications.models import NotificationType

            create_in_app_notification(
                user=issue.project.manager,
                title="Nouveau problème terrain",
                body=f"{issue.title} · {issue.project.name}",
                notification_type=NotificationType.TASK,
                action_url="/dashboard#problèmes",
                dedupe_key=f"project-issue-created-{issue.pk}",
            )

    def perform_update(self, serializer):
        issue = self.get_object()
        if not is_project_manager(self.request.user, issue.project):
            raise PermissionDenied("Seul le chef de projet peut traiter un problème.")
        previous_status = issue.status
        issue = serializer.save()
        if issue.status in {"RESOLVED", "CLOSED"} and issue.resolved_at is None:
            issue.resolved_at = timezone.now()
            issue.save(update_fields=("resolved_at", "updated_at"))
        write_audit_event(
            event="project_issue.updated",
            actor=self.request.user,
            object_type="project_issue",
            object_id=issue.pk,
            metadata={"previous_status": previous_status, "status": issue.status},
            request_id=getattr(self.request, "request_id", ""),
        )
