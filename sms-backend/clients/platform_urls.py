import os

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
    PlatformSubscriptionPaymentViewSet,
    PlatformSubscriptionPaymentMpesaCallbackView,
    PlatformSubscriptionPlanViewSet,
    PlatformSupportTicketViewSet,
    PlatformTenantSubscriptionViewSet,
    PlatformTenantViewSet,
    PlatformRevenueOverviewView,
    PlatformFraudAlertsOverviewView,
    PlatformAuditExportView,
    PlatformTenantWalletSummaryView,
)

router = SimpleRouter()
router.register(r"tenants", PlatformTenantViewSet, basename="platform-tenant")
router.register(r"plans", PlatformSubscriptionPlanViewSet, basename="platform-plan")
router.register(r"subscriptions", PlatformTenantSubscriptionViewSet, basename="platform-subscription")
router.register(r"subscription-invoices", PlatformSubscriptionInvoiceViewSet, basename="platform-subscription-invoice")
router.register(r"subscription-payments", PlatformSubscriptionPaymentViewSet, basename="platform-subscription-payment")
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
router.register(r"revenue/overview", PlatformRevenueOverviewView, basename="platform-revenue-overview")
router.register(r"fraud/overview", PlatformFraudAlertsOverviewView, basename="platform-fraud-overview")
router.register(r"audit/export", PlatformAuditExportView, basename="platform-audit-export")
router.register(r"wallets/summary", PlatformTenantWalletSummaryView, basename="platform-wallet-summary")


_DEFAULT_PLATFORM_PASSWORD = "PlatformAdmin#2025"


def _platform_login_username_candidates(username: str) -> list[str]:
    """
    Return candidate usernames for platform login in priority order.

    We keep the exact username first so public platform users can log in with
    the account they were given, then fall back to the historical Riqs# alias
    pair for compatibility with older seed data.
    """
    normalized = (username or "").strip()
    lowered = normalized.casefold()

    if lowered == "platform_admin":
        return ["platform_admin"]

    if lowered in {"riqs#", "riqs#."}:
        candidates = [normalized]
        for alias in ("Riqs#", "Riqs#."):
            if alias.casefold() == lowered:
                continue
            if alias not in candidates:
                candidates.append(alias)
        return candidates

    return [normalized]


def _ensure_platform_admin_user():
    """
    Make sure the public-schema platform admin account exists before login.

    Some deploys have the platform user missing even though the rest of the
    platform data is present. The login endpoint self-heals that state so the
    platform admin can still sign in with the configured password.
    """
    from django.contrib.auth import get_user_model
    from django_tenants.utils import get_public_schema_name, schema_context

    from clients.models import GlobalSuperAdmin

    env_password = os.environ.get("PLATFORM_ADMIN_PASSWORD", "").strip()
    if env_password:
        password = env_password
    else:
        password = _DEFAULT_PLATFORM_PASSWORD

    with schema_context(get_public_schema_name()):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="platform_admin",
            defaults={
                "email": "platform@rynatyschool.com",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        needs_save = created
        if created:
            user.set_password(password)
        else:
            if not user.is_active:
                user.is_active = True
                needs_save = True
            if not user.is_staff:
                user.is_staff = True
                needs_save = True
            if not user.is_superuser:
                user.is_superuser = True
                needs_save = True
            if not user.check_password(password):
                user.set_password(password)
                needs_save = True

        if needs_save:
            user.save()

        gsa, gsa_created = GlobalSuperAdmin.objects.get_or_create(
            user=user,
            defaults={"role": "OWNER", "is_active": True},
        )
        if not gsa_created and (gsa.role != "OWNER" or not gsa.is_active):
            gsa.role = "OWNER"
            gsa.is_active = True
            gsa.save()

        return user, gsa


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
            candidate_usernames = _platform_login_username_candidates(username)

            if candidate_usernames and candidate_usernames[0].casefold() == "platform_admin":
                _ensure_platform_admin_user()

            from django.contrib.auth.models import User
            from clients.models import GlobalSuperAdmin
            from rest_framework_simplejwt.tokens import RefreshToken

            user = None
            gsa = None
            password_match_without_gsa = None
            for candidate_username in candidate_usernames:
                candidate_user = User.objects.filter(username__iexact=candidate_username, is_active=True).first()
                if not candidate_user or not candidate_user.check_password(password):
                    continue

                candidate_gsa = GlobalSuperAdmin.objects.filter(user=candidate_user, is_active=True).first()
                if candidate_gsa:
                    user = candidate_user
                    gsa = candidate_gsa
                    break

                password_match_without_gsa = candidate_user

            if not user:
                if password_match_without_gsa:
                    return JsonResponse(
                        {"detail": "This account does not have platform admin access."},
                        status=403,
                    )
                return JsonResponse(
                    {"detail": "No active platform admin account found with those credentials."},
                    status=401,
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
    path("subscription-payments/mpesa/callback/", PlatformSubscriptionPaymentMpesaCallbackView.as_view(), name="platform-subscription-payment-mpesa-callback"),
    path("", include(router.urls)),
]
