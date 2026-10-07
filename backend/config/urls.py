from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from companies.views import CompanyMeAPIView, CompanyProfileViewSet, PortfolioItemViewSet
from dashboard.diagnostics import ClientDiagnosticAPIView
from dashboard.views import DashboardAPIView
from notifications.views import NotificationViewSet
from opportunities.views import ApplicationViewSet, OpportunityViewSet
from projects.views import (
    EvidenceViewSet,
    ProjectExpenseViewSet,
    ProjectReportViewSet,
    ProjectTaskViewSet,
    ProjectViewSet,
)
from service_requests.views import ServiceRequestViewSet
from common.health import health, readiness

router = DefaultRouter()
router.register("service-requests", ServiceRequestViewSet, basename="service-request")
router.register("projects", ProjectViewSet, basename="project")
router.register("evidences", EvidenceViewSet, basename="evidence")
router.register("project-expenses", ProjectExpenseViewSet, basename="project-expense")
router.register("project-tasks", ProjectTaskViewSet, basename="project-task")
router.register("reports", ProjectReportViewSet, basename="project-report")
router.register("companies", CompanyProfileViewSet, basename="company")
router.register("portfolio", PortfolioItemViewSet, basename="portfolio")
router.register("opportunities", OpportunityViewSet, basename="opportunity")
router.register("applications", ApplicationViewSet, basename="application")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("health/ready/", readiness, name="health-ready"),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/companies/me/", CompanyMeAPIView.as_view(), name="company-me"),
    path("api/v1/dashboard/", DashboardAPIView.as_view(), name="dashboard"),
    path("api/v1/diagnostics/client/", ClientDiagnosticAPIView.as_view(), name="client-diagnostic"),
    path("api/v1/", include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
