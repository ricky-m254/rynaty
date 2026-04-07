from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuditLogRefView, AuditLogViewSet

router = DefaultRouter()
router.register(r"audit-logs", AuditLogViewSet, basename="reporting_audit_logs")

urlpatterns = [
    path("ref/audit-logs/", AuditLogRefView.as_view(), name="reporting_ref_audit_logs"),
    path("", include(router.urls)),
]
