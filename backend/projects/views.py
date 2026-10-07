from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from accounts.models import KemtaPermission
from accounts.permissions import has_kemta_permission
from common.services import write_audit_event
from projects.models import (
    Evidence,
    PhaseStatus,
    Project,
    ProjectExpense,
    ProjectPhase,
    ProjectReport,
    ProjectTask,
)
from projects.permissions import (
    EvidenceAccessPermission,
    ProjectAccessPermission,
    ProjectChildAccessPermission,
    ProjectExpenseAccessPermission,
    can_access_project,
    can_manage_all,
)
from projects.serializers import (
    EvidenceSerializer,
    ProjectDetailSerializer,
    ProjectExpenseSerializer,
    ProjectReportSerializer,
    ProjectSerializer,
    ProjectTaskSerializer,
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
        project = serializer.save()
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
        queryset = Evidence.objects.select_related("project", "phase", "uploaded_by").order_by("-created_at")
        project_id = self.request.query_params.get("project")
        if can_manage_all(user):
            return queryset.filter(project_id=project_id) if project_id else queryset
        visible_projects = Project.objects.filter(Q(owner=user) | Q(manager=user) | Q(field_agents=user)).values("id")
        queryset = queryset.filter(project_id__in=visible_projects)
        return queryset.filter(project_id=project_id) if project_id else queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not can_access_project(self.request.user, project):
            raise PermissionDenied("Cette preuve ne peut pas être ajoutée à ce projet.")
        evidence = serializer.save(uploaded_by=self.request.user)
        write_audit_event(
            event="evidence.uploaded",
            actor=self.request.user,
            object_type="evidence",
            object_id=evidence.pk,
            metadata={"project_id": project.pk},
            request_id=getattr(self.request, "request_id", ""),
        )
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
