from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import UserRole
from common.services import write_audit_event
from companies.models import CompanyProfile
from opportunities.models import Application, ApplicationStatus, Opportunity, OpportunityStatus
from opportunities.permissions import ApplicationAccessPermission, OpportunityAccessPermission
from opportunities.serializers import ApplicationSerializer, ApplicationStatusSerializer, OpportunitySerializer


class OpportunityViewSet(viewsets.ModelViewSet):
    serializer_class = OpportunitySerializer
    permission_classes = (OpportunityAccessPermission,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "opportunity_public"
    http_method_names = ("get", "post", "patch", "put", "head", "options")

    def get_queryset(self):
        user = self.request.user
        queryset = Opportunity.objects.select_related("created_by").order_by("deadline", "-created_at")
        if user.is_authenticated and (user.is_staff or user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}):
            status_filter = self.request.query_params.get("status")
            if status_filter:
                queryset = queryset.filter(status=status_filter.upper())
            return queryset
        queryset = queryset.filter(status=OpportunityStatus.OPEN, deadline__gte=timezone.localdate())
        city = self.request.query_params.get("city")
        if city:
            queryset = queryset.filter(city__iexact=city.strip())
        project_type = self.request.query_params.get("project_type")
        if project_type:
            queryset = queryset.filter(project_type__iexact=project_type.strip())
        return queryset

    def perform_create(self, serializer):
        opportunity = serializer.save(created_by=self.request.user)
        write_audit_event(event="opportunity.created", actor=self.request.user, object_type="opportunity", object_id=opportunity.pk)

    def perform_update(self, serializer):
        opportunity = serializer.save()
        write_audit_event(event="opportunity.updated", actor=self.request.user, object_type="opportunity", object_id=opportunity.pk)


class ApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = ApplicationSerializer
    permission_classes = (ApplicationAccessPermission,)
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        user = self.request.user
        queryset = Application.objects.select_related("company", "company__user", "opportunity", "opportunity__created_by")
        if user.is_staff or user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            opportunity_id = self.request.query_params.get("opportunity")
            return queryset.filter(opportunity_id=opportunity_id) if opportunity_id else queryset
        return queryset.filter(company__user=user)

    def get_serializer_class(self):
        if self.action in {"partial_update", "update"}:
            return ApplicationStatusSerializer
        return ApplicationSerializer

    def perform_create(self, serializer):
        company = CompanyProfile.objects.filter(user=self.request.user).first()
        if company is None:
            raise ValidationError({"company": "Créez d’abord le profil de votre entreprise."})
        if not company.verified or not company.is_published:
            raise PermissionDenied("Votre entreprise doit être vérifiée par KEMTA avant de candidater.")
        try:
            with transaction.atomic():
                application = serializer.save(company=company)
                write_audit_event(
                    event="application.submitted",
                    actor=self.request.user,
                    object_type="application",
                    object_id=application.pk,
                    metadata={"opportunity_id": application.opportunity_id},
                    request_id=getattr(self.request, "request_id", ""),
                )
        except IntegrityError as exc:
            raise ValidationError({"opportunity": "Votre entreprise a déjà candidaté à cette opportunité."}) from exc

    def perform_update(self, serializer):
        if not (self.request.user.is_staff or self.request.user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}):
            raise PermissionDenied("Seule l’équipe KEMTA peut modifier le statut de la candidature.")
        application = serializer.save()
        write_audit_event(
            event="application.status_changed",
            actor=self.request.user,
            object_type="application",
            object_id=application.pk,
            metadata={"status": application.status},
            request_id=getattr(self.request, "request_id", ""),
        )

    @action(detail=True, methods=("post",), permission_classes=(ApplicationAccessPermission,))
    def withdraw(self, request, pk=None):
        application = self.get_object()
        if application.company.user_id != request.user.id:
            raise PermissionDenied("Vous ne pouvez pas retirer la candidature d’une autre entreprise.")
        if application.status not in {ApplicationStatus.SUBMITTED, ApplicationStatus.IN_REVIEW}:
            raise ValidationError("Cette candidature ne peut plus être retirée.")
        application.status = ApplicationStatus.WITHDRAWN
        application.save(update_fields=("status", "updated_at"))
        write_audit_event(event="application.withdrawn", actor=request.user, object_type="application", object_id=application.pk)
        return Response(ApplicationSerializer(application).data, status=status.HTTP_200_OK)
