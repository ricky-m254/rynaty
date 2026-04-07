from django.urls import include, path
from rest_framework.routers import DefaultRouter

from clients.platform_views import (
    PlatformBackupJobViewSet,
    PlatformComplianceReportViewSet,
    PlatformDeploymentReleaseViewSet,
    PlatformDomainRequestViewSet,
    PlatformFeatureFlagViewSet,
    PlatformApiKeyViewSet,
    PlatformIntegrationViewSet,
    PlatformMaintenanceWindowViewSet,
    PlatformActionLogViewSet,
    PlatformAdminUserViewSet,
    PlatformAnalyticsViewSet,
    PlatformImpersonationSessionViewSet,
    PlatformMonitoringAlertViewSet,
    PlatformMonitoringSnapshotViewSet,
    PlatformRestoreJobViewSet,
    PlatformSecurityIncidentViewSet,
    PlatformSettingViewSet,
    PlatformSubscriptionInvoiceViewSet,
    PlatformSubscriptionPlanViewSet,
    PlatformSupportTicketViewSet,
    PlatformTenantSubscriptionViewSet,
    PlatformTenantViewSet,
)

router = DefaultRouter()
router.register(r"tenants", PlatformTenantViewSet, basename="platform-tenant")
router.register(r"plans", PlatformSubscriptionPlanViewSet, basename="platform-plan")
router.register(r"subscriptions", PlatformTenantSubscriptionViewSet, basename="platform-subscription")
router.register(r"subscription-invoices", PlatformSubscriptionInvoiceViewSet, basename="platform-subscription-invoice")
router.register(r"analytics", PlatformAnalyticsViewSet, basename="platform-analytics")
router.register(r"support-tickets", PlatformSupportTicketViewSet, basename="platform-support-ticket")
router.register(r"impersonation-sessions", PlatformImpersonationSessionViewSet, basename="platform-impersonation-session")
router.register(r"monitoring/snapshots", PlatformMonitoringSnapshotViewSet, basename="platform-monitoring-snapshot")
router.register(r"monitoring/alerts", PlatformMonitoringAlertViewSet, basename="platform-monitoring-alert")
router.register(r"action-logs", PlatformActionLogViewSet, basename="platform-action-log")
router.register(r"settings", PlatformSettingViewSet, basename="platform-setting")
router.register(r"api-keys", PlatformApiKeyViewSet, basename="platform-api-key")
router.register(r"integrations", PlatformIntegrationViewSet, basename="platform-integration")
router.register(r"admin-users", PlatformAdminUserViewSet, basename="platform-admin-user")
router.register(r"maintenance/windows", PlatformMaintenanceWindowViewSet, basename="platform-maintenance-window")
router.register(r"deployment/releases", PlatformDeploymentReleaseViewSet, basename="platform-deployment-release")
router.register(r"deployment/feature-flags", PlatformFeatureFlagViewSet, basename="platform-feature-flag")
router.register(r"backup/jobs", PlatformBackupJobViewSet, basename="platform-backup-job")
router.register(r"backup/restores", PlatformRestoreJobViewSet, basename="platform-restore-job")
router.register(r"security/incidents", PlatformSecurityIncidentViewSet, basename="platform-security-incident")
router.register(r"security/compliance-reports", PlatformComplianceReportViewSet, basename="platform-compliance-report")
router.register(r"domain-requests", PlatformDomainRequestViewSet, basename="platform-domain-request")

urlpatterns = [
    path("", include(router.urls)),
]
