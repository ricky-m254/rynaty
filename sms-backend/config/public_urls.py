from django.urls import include, path, re_path
from django.http import JsonResponse, FileResponse, HttpResponse
from django.conf import settings
from django.views.static import serve as static_serve
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.views import TokenRefreshView


# Security note: @csrf_exempt is correct here.  This is a stateless JWT login
# endpoint — credentials travel in the JSON request body, not in a cookie.
# Django's CSRF middleware protects cookie-based sessions; it does not apply
# to token-based (JWT) authentication flows.  The JWT tokens returned by this
# view are validated on every subsequent request by JWTAuthentication.
@csrf_exempt
def _tenant_aware_login_view(request):
    """
    Login endpoint that works for BOTH public-schema requests and tenant requests.

    With X-Tenant-ID header: switches the DB connection to the named tenant
    schema before calling SmartCampusTokenObtainPairView.

    Without X-Tenant-ID header (platform admin / public-schema login): calls
    SmartCampusTokenObtainPairView with the connection in the public schema.
    Stage 0 of the serializer checks for a matching GlobalSuperAdmin record and
    returns the enriched response (role, redirect_to=/platform, etc.) so the
    frontend can route correctly.  The plain TokenObtainPairView is no longer
    used because it returns a bare JWT without role/redirect_to enrichment.
    """
    import logging as _logging
    from django.db import connection
    from django_tenants.utils import get_public_schema_name
    from clients.models import Tenant
    from school.views import SmartCampusTokenObtainPairView

    _log = _logging.getLogger(__name__)
    header_name = getattr(settings, "TENANT_HEADER_NAME", "X-Tenant-ID")
    tenant_id_header = (request.headers.get(header_name) or "").strip()

    if tenant_id_header:
        try:
            tenant = Tenant.objects.get(schema_name=tenant_id_header)
            connection.set_tenant(tenant)
        except Tenant.DoesNotExist:
            return JsonResponse(
                {"detail": f"Unknown School ID: '{tenant_id_header}'."},
                status=400,
            )
        except Exception as _exc:
            # Unexpected error switching to tenant schema; log it so it is
            # visible in monitoring and fall through with the connection in
            # whatever schema it is currently in.  Stage 0 / standard auth
            # will handle credentials from there.
            _log.warning(
                "Failed to set tenant schema for header '%s': %s",
                tenant_id_header, _exc, exc_info=True,
            )

    # Always use the enriched SmartCampus view.
    # Without a tenant header the connection remains in the public schema, and
    # Stage 0 of SmartCampusTokenObtainPairSerializer picks up GlobalSuperAdmin
    # users, returning role + redirect_to=/platform so the UI navigates correctly.
    return SmartCampusTokenObtainPairView.as_view()(request)


def ping_view(request):
    """Public health check. Accessible from any origin before tenant isolation."""
    return JsonResponse({"status": "ok", "service": "sms_backend", "schema": "public"})


def tenant_info_view(request):
    """
    Return basic info about the currently resolved tenant.
    Works via subdomain (Host header) or X-Tenant-ID header.
    Used by the frontend to auto-detect school context on login page.
    """
    from django_tenants.utils import get_public_schema_name
    tenant = getattr(request, "tenant", None)
    public_schema = get_public_schema_name()
    schema = getattr(tenant, "schema_name", None)

    if not tenant or schema in {None, public_schema}:
        return JsonResponse(
            {"error": "No tenant found for this hostname.", "code": "TENANT_NOT_FOUND"},
            status=404,
        )

    status = getattr(tenant, "status", "")
    if status in {"SUSPENDED"}:
        return JsonResponse(
            {
                "error": "This school account is suspended.",
                "code": "TENANT_SUSPENDED",
                "tenant_name": tenant.name,
                "schema_name": schema,
            },
            status=403,
        )
    if status in {"CANCELLED", "ARCHIVED"}:
        return JsonResponse(
            {
                "error": "This school account is no longer active.",
                "code": "TENANT_INACTIVE",
                "tenant_name": tenant.name,
                "schema_name": schema,
            },
            status=403,
        )

    return JsonResponse(
        {
            "schema_name": schema,
            "tenant_name": tenant.name,
            "status": status,
            "subdomain": getattr(tenant, "subdomain", None),
            "contact_email": getattr(tenant, "contact_email", ""),
        }
    )


def _serve_react_app(request, path=""):
    """Serve the React SPA for all non-API public routes."""
    index_path = settings.BASE_DIR / "frontend_build" / "index.html"
    if index_path.exists():
        response = FileResponse(open(index_path, "rb"), content_type="text/html")
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response
    return HttpResponse(
        b"<h1>SMS Platform</h1><p>App is starting up...</p>",
        content_type="text/html",
    )


def _db_health_view(request):
    """Public-schema DB health check — imported lazily to avoid startup ordering issues."""
    from school.views import db_health_check_view as _view
    return _view(request)


urlpatterns = [
    # 1. System Health
    path("api/ping/", ping_view),
    path("api/ping", ping_view),
    path("health/", ping_view),
    path("health", ping_view),

    # DB-aware health check (unauthenticated) — used by the login page banner
    path("api/health/", _db_health_view),
    path("api/health", _db_health_view),

    # 2. Authentication (Login + Refresh)
    path("api/auth/login/", _tenant_aware_login_view),
    path("api/auth/refresh/", TokenRefreshView.as_view()),

    # 3. Tenant Info (subdomain/header auto-detection for login page)
    path("api/tenant/info/", tenant_info_view),

    # 4. Platform (Super Tenant) APIs
    path("api/platform/", include("clients.platform_urls")),

    # 5. Catch-all: serve the React SPA for any remaining public-schema route
    re_path(r"^(?!api/|admin/|static/|media/).*$", _serve_react_app),
]

urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        static_serve,
        {"document_root": str(settings.MEDIA_ROOT)},
    )
]
