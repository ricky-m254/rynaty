from django.urls import path

from .teacher_portal_views import (
    TeacherPortalAttendanceView,
    TeacherPortalClassesView,
    TeacherPortalDashboardView,
    TeacherPortalGradebookView,
    TeacherPortalResourceDetailView,
    TeacherPortalResourcesView,
    TeacherPortalTimetableView,
)


urlpatterns = [
    path("dashboard/", TeacherPortalDashboardView.as_view()),
    path("classes/", TeacherPortalClassesView.as_view()),
    path("attendance/", TeacherPortalAttendanceView.as_view()),
    path("gradebook/", TeacherPortalGradebookView.as_view()),
    path("resources/", TeacherPortalResourcesView.as_view()),
    path("resources/<int:material_id>/", TeacherPortalResourceDetailView.as_view()),
    path("timetable/", TeacherPortalTimetableView.as_view()),
]
