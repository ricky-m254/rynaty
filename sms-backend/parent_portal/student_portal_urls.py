from django.urls import path

from .student_portal_views import (
    MyInvoicesView,
    MyPaymentsView,
    StudentAcademicsGradesView,
    StudentAssignmentsView,
    StudentAttendanceCalendarView,
    StudentAttendanceSummaryView,
    StudentDashboardView,
    StudentELearningView,
    StudentLibraryView,
    StudentReportCardsView,
    StudentTimetableView,
)

urlpatterns = [
    path("dashboard/", StudentDashboardView.as_view()),
    path("academics/grades/", StudentAcademicsGradesView.as_view()),
    path("academics/report-cards/", StudentReportCardsView.as_view()),
    path("attendance/summary/", StudentAttendanceSummaryView.as_view()),
    path("attendance/calendar/", StudentAttendanceCalendarView.as_view()),
    path("assignments/", StudentAssignmentsView.as_view()),
    path("my-invoices/", MyInvoicesView.as_view()),
    path("my-payments/", MyPaymentsView.as_view()),
    path("library/", StudentLibraryView.as_view()),
    path("elearning/", StudentELearningView.as_view()),
    path("timetable/", StudentTimetableView.as_view()),
]

portal_urlpatterns = [
    path("my-invoices/", MyInvoicesView.as_view()),
    path("my-payments/", MyPaymentsView.as_view()),
]
