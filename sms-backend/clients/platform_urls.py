from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from rest_framework.routers import SimpleRouter

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

router = SimpleRouter()
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

@csrf_exempt
def platform_login_view(request):
    """
    Dedicated POST endpoint for GlobalSuperAdmin (platform super-admin) login.
    Accepts {username, password} and returns JWT tokens + platform role.
    This endpoint explicitly bypasses tenant context and only accepts GSA users.
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed."}, status=405)
    try:
        import json as _json
        body = _json.loads(request.body)
        username = (body.get("username") or "").strip()
        password = (body.get("password") or "").strip()
    except Exception:
        return JsonResponse({"detail": "Invalid JSON body."}, status=400)

    if not username or not password:
        return JsonResponse({"detail": "username and password are required."}, status=400)

    try:
        from django_tenants.utils import schema_context, get_public_schema_name
        with schema_context(get_public_schema_name()):
            from django.contrib.auth.models import User
            from clients.models import GlobalSuperAdmin
            from rest_framework_simplejwt.tokens import RefreshToken

            user = User.objects.filter(username__iexact=username, is_active=True).first()
            if not user or not user.check_password(password):
                return JsonResponse(
                    {"detail": "No active platform admin account found with those credentials."},
                    status=401,
                )
            gsa = GlobalSuperAdmin.objects.filter(user=user, is_active=True).first()
            if not gsa:
                return JsonResponse(
                    {"detail": "This account does not have platform admin access."},
                    status=403,
                )

            refresh = RefreshToken.for_user(user)
            refresh["role"] = gsa.role
            refresh["tenant_id"] = "public"
            access = refresh.access_token

            return JsonResponse({
                "access": str(access),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                "role": gsa.role,
                "available_roles": [gsa.role],
                "redirect_to": "/platform",
                "tenant_id": "public",
                "force_password_change": False,
            })
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).error("Platform login failed: %s", exc, exc_info=True)
        return JsonResponse({"detail": "Platform login error. Please try again."}, status=500)


urlpatterns = [
    path("auth/login/", platform_login_view, name="platform-auth-login"),
    path("", include(router.urls)),
]
