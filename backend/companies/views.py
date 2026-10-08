from django.core.cache import cache
from django.db.models import Prefetch, Q
from django.http import FileResponse
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import UserRole
from common.services import write_audit_event
from companies import verification as verification_rules
from companies.models import CompanyDocument, CompanyProfile, PortfolioItem
from companies.permissions import (
    CompanyOwnerPermission,
    CompanyVerificationAdminPermission,
    PortfolioAccessPermission,
)
from companies.serializers import (
    CompanyDocumentSerializer,
    CompanyDocumentUploadSerializer,
    CompanyProfileOwnerSerializer,
    CompanyProfileSerializer,
    CompanyProfileWriteSerializer,
    CompanyReviewQueueSerializer,
    CompanyVerificationDecisionSerializer,
    PortfolioItemOwnerSerializer,
    PortfolioItemSerializer,
)


def _verification_payload(company: CompanyProfile, request) -> dict:
    """Charge utile du dossier : état, étapes, pièces et niveaux."""
    payload = verification_rules.verification_snapshot(company, request.user)
    payload["levels"] = verification_rules.level_progress(company)
    payload["profile"] = CompanyProfileOwnerSerializer(company, context={"request": request}).data
    return payload


# Clé de version du catalogue : les listes publiques sont mises en cache avec elle,
# ce qui permet de les invalider sans parcourir les clés (portable LocMem/Redis).
CATALOG_VERSION_KEY = "catalog:version"


def _invalidate_company_catalog(company: CompanyProfile) -> None:
    """Retire une fiche des caches publics : la fiche détaillée et les listes."""
    cache.delete(f"catalog:company:{company.slug}")
    cache.add(CATALOG_VERSION_KEY, 1)
    try:
        cache.incr(CATALOG_VERSION_KEY)
    except ValueError:  # cache vidé entre-temps : on repart d'une version neuve
        cache.set(CATALOG_VERSION_KEY, 2)


def _company_for(user) -> CompanyProfile:
    """Profil entreprise du compte connecté (créé au fil du parcours d'inscription)."""
    company = CompanyProfile.objects.filter(user=user).first()
    if company is None:
        raise NotFound("Créez d’abord le profil de votre entreprise.")
    return company


class CompanyMeAPIView(APIView):
    permission_classes = (IsAuthenticated, CompanyOwnerPermission)

    def get(self, request):
        company = CompanyProfile.objects.filter(user=request.user).prefetch_related("portfolio").first()
        if company is None:
            raise NotFound("Aucun profil entreprise n’a encore été créé.")
        return Response(CompanyProfileOwnerSerializer(company, context={"request": request}).data)

    def put(self, request):
        return self._save(request, partial=False)

    def patch(self, request):
        """Mise à jour partielle : « Enregistrer et continuer plus tard »."""
        return self._save(request, partial=True)

    def _save(self, request, *, partial: bool):
        company = CompanyProfile.objects.filter(user=request.user).prefetch_related("portfolio").first()
        was_verified = bool(company and company.verified)
        serializer = CompanyProfileWriteSerializer(instance=company, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        company = serializer.save(user=request.user)
        write_audit_event(
            event="company.profile_saved",
            actor=request.user,
            object_type="company_profile",
            object_id=company.pk,
            request_id=getattr(request, "request_id", ""),
        )
        if was_verified:
            # Une entreprise vérifiée le reste tant qu'une décision n'a pas été prise.
            _invalidate_company_catalog(company)
        return Response(CompanyProfileOwnerSerializer(company, context={"request": request}).data, status=status.HTTP_200_OK)


class CompanyProfileViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = CompanyProfileSerializer
    permission_classes = (AllowAny,)
    lookup_field = "slug"
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "company_public"

    def get_queryset(self):
        queryset = CompanyProfile.objects.filter(is_published=True).select_related("user").prefetch_related(
            Prefetch("portfolio", queryset=PortfolioItem.objects.filter(is_published=True).order_by("position", "-created_at"))
        )
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(city__icontains=search) | Q(description__icontains=search)).distinct()
        return queryset

    def list(self, request, *args, **kwargs):
        cache_key = f"catalog:companies:{cache.get(CATALOG_VERSION_KEY, 1)}:{request.get_full_path()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=300)
        return response

    def retrieve(self, request, *args, **kwargs):
        cache_key = f"catalog:company:{kwargs.get('slug', '')}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        response = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=300)
        return response


class PortfolioItemViewSet(viewsets.ModelViewSet):
    serializer_class = PortfolioItemSerializer
    permission_classes = (PortfolioAccessPermission,)
    http_method_names = ("get", "post", "patch", "put", "delete", "head", "options")

    def get_queryset(self):
        user = self.request.user
        queryset = PortfolioItem.objects.select_related("company", "company__user")
        if user.is_authenticated and (user.is_staff or user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}):
            return queryset
        if user.is_authenticated:
            return queryset.filter(company__user=user)
        return queryset.none()

    def get_serializer_class(self):
        if self.request.method in {"POST", "PUT", "PATCH"}:
            return PortfolioItemOwnerSerializer
        return PortfolioItemSerializer

    def perform_create(self, serializer):
        company = CompanyProfile.objects.filter(user=self.request.user).first()
        if company is None:
            raise PermissionDenied("Créez d’abord le profil de votre entreprise.")
        portfolio_item = serializer.save(company=company)
        write_audit_event(event="company.portfolio_created", actor=self.request.user, object_type="portfolio_item", object_id=portfolio_item.pk)

    def perform_update(self, serializer):
        portfolio_item = serializer.save()
        write_audit_event(event="company.portfolio_updated", actor=self.request.user, object_type="portfolio_item", object_id=portfolio_item.pk)


class CompanyMeDocumentsAPIView(APIView):
    """Liste et dépôt des pièces justificatives (un document par type, remplaçable)."""

    permission_classes = (IsAuthenticated, CompanyOwnerPermission)

    def get(self, request):
        company = _company_for(request.user)
        documents = company.documents.all()
        return Response({
            "documents": CompanyDocumentSerializer(documents, many=True).data,
            "required": list(verification_rules.required_document_types()),
            "missing": verification_rules.missing_document_labels(company),
        })

    def post(self, request):
        company = _company_for(request.user)
        serializer = CompanyDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = verification_rules.store_document(
            company=company,
            document_type=serializer.validated_data["document_type"],
            file_obj=serializer.validated_data["file"],
            actor=request.user,
            expires_at=serializer.validated_data.get("expires_at"),
            request_id=getattr(request, "request_id", ""),
        )
        return Response(
            {
                **CompanyDocumentSerializer(document).data,
                "checklist": verification_rules.document_checklist(company),
                "missing_documents": verification_rules.missing_document_labels(company),
            },
            status=status.HTTP_201_CREATED,
        )


class CompanyDocumentFileAPIView(APIView):
    """Sert une pièce du dossier après contrôle des droits (propriétaire ou KEMTA)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, pk: int):
        document = CompanyDocument.objects.select_related("company", "company__user").filter(pk=pk).first()
        if document is None:
            raise NotFound("Ce document n’existe pas.")
        user = request.user
        is_reviewer = user.is_staff or user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}
        if not is_reviewer and document.company.user_id != user.id:
            raise PermissionDenied("Ce document appartient à une autre entreprise.")
        filename = document.original_name or document.file.name.rsplit("/", 1)[-1]
        return FileResponse(document.file.open("rb"), as_attachment=True, filename=filename)


class CompanyVerificationAPIView(APIView):
    """État du dossier de vérification vu par l'entreprise."""

    permission_classes = (IsAuthenticated, CompanyOwnerPermission)

    def get(self, request):
        company = _company_for(request.user)
        return Response(_verification_payload(company, request))


class CompanyVerificationSubmitAPIView(APIView):
    """Soumission du dossier à l'équipe KEMTA."""

    permission_classes = (IsAuthenticated, CompanyOwnerPermission)

    def post(self, request):
        company = _company_for(request.user)
        verification_rules.submit_verification(company, request.user, request_id=getattr(request, "request_id", ""))
        return Response(_verification_payload(company, request), status=status.HTTP_200_OK)


class CompanyVerificationQueueAPIView(APIView):
    """File d'attente d'examen : dossiers déposés par les entreprises."""

    permission_classes = (IsAuthenticated, CompanyVerificationAdminPermission)

    def get(self, request):
        limit = request.query_params.get("limit")
        try:
            limit_value = min(int(limit), 50) if limit else 20
        except ValueError:
            limit_value = 20
        queryset = verification_rules.review_queue(limit=limit_value)
        return Response({
            "count": verification_rules.review_queue().count(),
            "results": CompanyReviewQueueSerializer(queryset, many=True, context={"request": request}).data,
        })


class CompanyVerificationDecisionAPIView(APIView):
    """Décision d'administration sur un dossier : examen, validation, refus, suspension."""

    permission_classes = (IsAuthenticated, CompanyVerificationAdminPermission)

    def post(self, request, pk: int):
        company = CompanyProfile.objects.select_related("user").filter(pk=pk).first()
        if company is None:
            raise NotFound("Cette entreprise n’existe pas.")
        serializer = CompanyVerificationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification_rules.apply_decision(
            company,
            request.user,
            action=serializer.validated_data["action"],
            reason=serializer.validated_data.get("reason", ""),
            document_type=serializer.validated_data.get("document_type", ""),
            advanced=serializer.validated_data.get("advanced", False),
            request_id=getattr(request, "request_id", ""),
        )
        _invalidate_company_catalog(company)
        return Response(CompanyReviewQueueSerializer(company, context={"request": request}).data, status=status.HTTP_200_OK)
