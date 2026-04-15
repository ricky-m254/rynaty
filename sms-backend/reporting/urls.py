from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import AuditLogRefView, AuditLogViewSet

router = SimpleRouter()
router.register(r"audit-logs", AuditLogViewSet, basename="reporting_audit_logs")

urlpatterns = [
    path("ref/audit-logs/", AuditLogRefView.as_view(), name="reporting_ref_audit_logs"),
    path("", include(router.urls)),
]
