"""
URL configuration for SaaS admin dashboard API.
"""

from django.urls import path
from .views import (
    DashboardOverview,
    RevenueChart,
    SchoolList,
    ToggleSchool,
    RevenuePerSchool,
    AlertList,
    ResolveAlert,
    AuditTrailView,
    ExportAuditCSV,
    VerifyAuditChain,
    SystemHealth
)

urlpatterns = [
    # Dashboard
    path('overview/', DashboardOverview.as_view(), name='admin-overview'),
    path('revenue-chart/', RevenueChart.as_view(), name='revenue-chart'),
    path('health/', SystemHealth.as_view(), name='system-health'),
    
    # Schools
    path('schools/', SchoolList.as_view(), name='school-list'),
    path('schools/<int:school_id>/toggle/', ToggleSchool.as_view(), name='toggle-school'),
    
    # Revenue
    path('revenue-per-school/', RevenuePerSchool.as_view(), name='revenue-per-school'),
    
    # Alerts
    path('alerts/', AlertList.as_view(), name='alert-list'),
    path('alerts/<int:alert_id>/resolve/', ResolveAlert.as_view(), name='resolve-alert'),
    
    # Audit
    path('audit/', AuditTrailView.as_view(), name='audit-trail'),
    path('audit/export/', ExportAuditCSV.as_view(), name='export-audit'),
    path('audit/verify/', VerifyAuditChain.as_view(), name='verify-audit'),
]
