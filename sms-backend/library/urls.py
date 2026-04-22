from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AcquisitionRequestViewSet,
    CirculationBulkRemindView,
    CirculationMemberBorrowingsView,
    CirculationOverdueView,
    CirculationReminderView,
    CirculationRuleView,
    CirculationTransactionsView,
    FineViewSet,
    IssueResourceView,
    InventoryAuditViewSet,
    LibraryCategoryViewSet,
    LibraryDashboardView,
    LibraryMemberViewSet,
    LibraryReportsCirculationView,
    LibraryReportsFinesView,
    LibraryReportsMemberActivityView,
    LibraryReportsOverdueView,
    LibraryReportsPopularView,
    LibraryReportsTeacherCustodyView,
    LibraryResourceViewSet,
    RenewResourceView,
    ReservationViewSet,
    ResourceCopyViewSet,
    ReturnResourceView,
)

router = SimpleRouter()
router.register(r"resources", LibraryResourceViewSet, basename="library_resources")
router.register(r"copies", ResourceCopyViewSet, basename="library_copies")
router.register(r"categories", LibraryCategoryViewSet, basename="library_categories")
router.register(r"members", LibraryMemberViewSet, basename="library_members")
router.register(r"reservations", ReservationViewSet, basename="library_reservations")
router.register(r"fines", FineViewSet, basename="library_fines")
router.register(r"inventory/audits", InventoryAuditViewSet, basename="library_inventory_audits")
router.register(r"acquisition/requests", AcquisitionRequestViewSet, basename="library_acquisition_requests")

urlpatterns = [
    path("dashboard/", LibraryDashboardView.as_view(), name="library_dashboard"),
    path("circulation/issue/", IssueResourceView.as_view(), name="library_issue"),
    path("circulation/return/", ReturnResourceView.as_view(), name="library_return"),
    path("circulation/renew/", RenewResourceView.as_view(), name="library_renew"),
    path("circulation/transactions/", CirculationTransactionsView.as_view(), name="library_transactions"),
    path("circulation/overdue/", CirculationOverdueView.as_view(), name="library_overdue"),
    path("circulation/overdue/remind-all/", CirculationBulkRemindView.as_view(), name="library_bulk_remind"),
    path("circulation/<int:transaction_id>/send_reminder/", CirculationReminderView.as_view(), name="library_send_reminder"),
    path("circulation/member/<int:member_id>/", CirculationMemberBorrowingsView.as_view(), name="library_member_borrowings"),
    path("circulation/rules/", CirculationRuleView.as_view(), name="library_rules"),
    path("reports/circulation/", LibraryReportsCirculationView.as_view(), name="library_reports_circulation"),
    path("reports/popular/", LibraryReportsPopularView.as_view(), name="library_reports_popular"),
    path("reports/overdue/", LibraryReportsOverdueView.as_view(), name="library_reports_overdue"),
    path("reports/teacher-custody/", LibraryReportsTeacherCustodyView.as_view(), name="library_reports_teacher_custody"),
    path("reports/fines/", LibraryReportsFinesView.as_view(), name="library_reports_fines"),
    path("reports/member-activity/", LibraryReportsMemberActivityView.as_view(), name="library_reports_member_activity"),
    path("", include(router.urls)),
]
