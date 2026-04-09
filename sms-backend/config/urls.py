from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, HttpResponseNotFound, JsonResponse

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
    path("api/", include("school.urls")),

    # 4. Catch-all: serve the React SPA for any non-API route
    re_path(r"^(?!api/|admin/|static/|media/|health).*$", _serve_react_app),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
