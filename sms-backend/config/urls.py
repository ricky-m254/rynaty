from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.http import FileResponse, HttpResponseNotFound, JsonResponse, HttpResponseRedirect
from django.views.static import serve as static_serve

# This file handles TENANT ROUTES (School Data)
# Public Routes are now handled by config/public_urls.py


def _health_check(request):
    return JsonResponse({"status": "ok"})


def _serve_react_app(request, path=""):
    frontend_dir = settings.BASE_DIR / "frontend_build"
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        response = FileResponse(open(index_path, "rb"), content_type="text/html")
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response
    return JsonResponse({"status": "ok", "detail": "API running — frontend not built yet"})


def _guard_platform_route(request, path=""):
    """
    Intercept /platform and /platform/* on school (non-public) schemas.
    The platform admin UI must only be accessible from the platform domain.
    School admins navigating to /platform on a school subdomain are redirected
    to /dashboard instead of seeing the platform admin panel.
    """
    from django.db import connection as _conn
    from django_tenants.utils import get_public_schema_name as _public
    if getattr(_conn, 'schema_name', None) != _public():
        return HttpResponseRedirect('/dashboard')
    return _serve_react_app(request, path)


def _tenant_info_view(request):
    from config.public_urls import tenant_info_view
    return tenant_info_view(request)


urlpatterns = [
    # 0. Health check (must return 200 for deployment probes)
    path("health", _health_check),
    path("health/", _health_check),

    # 1. Admin Panel (For School Admins)
    path("admin/", admin.site.urls),

    # 2. Tenant info (subdomain auto-detection — available in tenant schema context too)
    path("api/tenant/info/", _tenant_info_view),

    # 3. School API Modules (Students, Finance, etc.)
    #    Finance routes are mounted here via school.urls; the staged finance.urls
    #    module remains unmounted to avoid duplicating the live /api/finance/* surface.
    path("api/", include("school.urls")),

    # 4. Platform (Super Admin) APIs — protected by IsGlobalSuperAdmin (schema-aware).
    #    Even though these URL patterns are registered on tenant schemas, the permission
    #    class enforces public-schema-only access, so school-schema requests get 403.
    path("api/platform/", include("clients.platform_urls")),

    # 5. Platform UI route guard: redirect school-subdomain users away from /platform.
    #    Must appear BEFORE the catch-all so it fires first.
    re_path(r"^platform(/.*)?$", _guard_platform_route),

    # 6. Catch-all: serve the React SPA for any remaining non-API route
    re_path(r"^(?!api/|admin/|static/|media/|health).*$", _serve_react_app),
]

urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        static_serve,
        {"document_root": str(settings.MEDIA_ROOT)},
    )
]
