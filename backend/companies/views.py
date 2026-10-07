from django.core.cache import cache
from django.db.models import Prefetch, Q
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import UserRole
from common.services import write_audit_event
from companies.models import CompanyProfile, PortfolioItem
from companies.permissions import CompanyOwnerPermission, PortfolioAccessPermission
from companies.serializers import (
    CompanyProfileSerializer,
    CompanyProfileWriteSerializer,
    PortfolioItemOwnerSerializer,
    PortfolioItemSerializer,
)


class CompanyMeAPIView(APIView):
    permission_classes = (IsAuthenticated, CompanyOwnerPermission)

    def get(self, request):
        company = CompanyProfile.objects.filter(user=request.user).prefetch_related("portfolio").first()
        if company is None:
            raise NotFound("Aucun profil entreprise n’a encore été créé.")
        return Response(CompanyProfileSerializer(company, context={"request": request}).data)

    def put(self, request):
        company = CompanyProfile.objects.filter(user=request.user).first()
        serializer = CompanyProfileWriteSerializer(instance=company, data=request.data)
        serializer.is_valid(raise_exception=True)
        company = serializer.save(user=request.user)
        write_audit_event(
            event="company.profile_saved",
            actor=request.user,
            object_type="company_profile",
            object_id=company.pk,
            request_id=getattr(request, "request_id", ""),
        )
        return Response(CompanyProfileSerializer(company, context={"request": request}).data, status=status.HTTP_200_OK)


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
        cache_key = f"catalog:companies:{request.get_full_path()}"
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
