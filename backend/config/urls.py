from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from companies.views import (
    CompanyDocumentFileAPIView,
    CompanyMeAPIView,
    CompanyMeDocumentsAPIView,
    CompanyProfileViewSet,
    CompanyVerificationAPIView,
    CompanyVerificationDecisionAPIView,
    CompanyVerificationQueueAPIView,
    CompanyVerificationSubmitAPIView,
    PortfolioItemViewSet,
)
from dashboard.diagnostics import ClientDiagnosticAPIView
from dashboard.views import DashboardAPIView, FieldOperationsDashboardAPIView
from notifications.views import NotificationViewSet
from opportunities.views import ApplicationViewSet, OpportunityViewSet
from projects.views import (
    EvidenceViewSet,
    FieldMissionViewSet,
    FieldReportViewSet,
    ProjectAssignmentViewSet,
    ProjectExpenseViewSet,
    ProjectIssueViewSet,
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
router.register("project-assignments", ProjectAssignmentViewSet, basename="project-assignment")
router.register("field-missions", FieldMissionViewSet, basename="field-mission")
router.register("field-reports", FieldReportViewSet, basename="field-report")
router.register("project-issues", ProjectIssueViewSet, basename="project-issue")
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
    # Parcours de vérification d'entreprise : déclaré avant le routeur du catalogue.
    path("api/v1/companies/me/documents/", CompanyMeDocumentsAPIView.as_view(), name="company-me-documents"),
    path("api/v1/companies/me/documents/<int:pk>/file/", CompanyDocumentFileAPIView.as_view(), name="company-document-file"),
    path("api/v1/companies/me/verification/", CompanyVerificationAPIView.as_view(), name="company-verification"),
    path("api/v1/companies/me/verification/submit/", CompanyVerificationSubmitAPIView.as_view(), name="company-verification-submit"),
    path("api/v1/companies/verification/queue/", CompanyVerificationQueueAPIView.as_view(), name="company-verification-queue"),
    path("api/v1/companies/<int:pk>/verification/", CompanyVerificationDecisionAPIView.as_view(), name="company-verification-decision"),
    path("api/v1/dashboard/", DashboardAPIView.as_view(), name="dashboard"),
    path("api/v1/dashboard/field-operations/", FieldOperationsDashboardAPIView.as_view(), name="field-operations-dashboard"),
    path("api/v1/diagnostics/client/", ClientDiagnosticAPIView.as_view(), name="client-diagnostic"),
    path("api/v1/", include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
