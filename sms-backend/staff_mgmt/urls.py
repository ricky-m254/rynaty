from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    StaffMemberViewSet,
    StaffQualificationViewSet,
    StaffEmergencyContactViewSet,
    StaffDepartmentViewSet,
    StaffRoleViewSet,
    StaffAssignmentViewSet,
    StaffAttendanceViewSet,
    StaffObservationViewSet,
    StaffAppraisalViewSet,
    StaffDocumentViewSet,
    StaffReviewHistoryView,
    StaffAnalyticsSummaryView,
    StaffReconciliationView,
    StaffAnalyticsByDepartmentView,
    StaffAnalyticsAttendanceView,
    StaffAnalyticsPerformanceView,
    StaffAnalyticsComplianceView,
    StaffDirectoryReportView,
    StaffAttendanceReportView,
)

router = DefaultRouter()
router.register(r"qualifications", StaffQualificationViewSet, basename="staff_qualification")
router.register(r"emergency-contacts", StaffEmergencyContactViewSet, basename="staff_emergency_contact")
router.register(r"departments", StaffDepartmentViewSet, basename="staff_department")
router.register(r"roles", StaffRoleViewSet, basename="staff_role")
router.register(r"assignments", StaffAssignmentViewSet, basename="staff_assignment")
router.register(r"attendance", StaffAttendanceViewSet, basename="staff_attendance")
router.register(r"observations", StaffObservationViewSet, basename="staff_observation")
router.register(r"appraisals", StaffAppraisalViewSet, basename="staff_appraisal")
router.register(r"documents", StaffDocumentViewSet, basename="staff_document")
router.register(r"", StaffMemberViewSet, basename="staff_member")

urlpatterns = [
    path("analytics/summary/", StaffAnalyticsSummaryView.as_view(), name="staff_analytics_summary"),
    path("analytics/reconciliation/", StaffReconciliationView.as_view(), name="staff_analytics_reconciliation"),
    path("analytics/by-department/", StaffAnalyticsByDepartmentView.as_view(), name="staff_analytics_by_department"),
    path("analytics/attendance/", StaffAnalyticsAttendanceView.as_view(), name="staff_analytics_attendance"),
    path("analytics/performance/", StaffAnalyticsPerformanceView.as_view(), name="staff_analytics_performance"),
    path("analytics/compliance/", StaffAnalyticsComplianceView.as_view(), name="staff_analytics_compliance"),
    path("reports/directory/", StaffDirectoryReportView.as_view(), name="staff_reports_directory"),
    path("reports/attendance/", StaffAttendanceReportView.as_view(), name="staff_reports_attendance"),
    path("<int:staff_id>/review-history/", StaffReviewHistoryView.as_view(), name="staff_review_history"),
    path("", include(router.urls)),
]
