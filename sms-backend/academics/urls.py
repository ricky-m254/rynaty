from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AcademicYearViewSet,
    TermViewSet,
    GradeLevelViewSet,
    SchoolClassViewSet,
    DepartmentViewSet,
    SubjectViewSet,
    SubjectMappingViewSet,
    SyllabusTopicViewSet,
    SyllabusProgressView,
    AcademicEnrollmentViewSet,
    TeacherAssignmentViewSet,
    GradingSchemeViewSet,
    GradeBandViewSet,
    AssessmentViewSet,
    AssessmentGradeViewSet,
    TermResultViewSet,
    ReportCardViewSet,
    AssignmentViewSet,
    AssignmentSubmissionViewSet,
    CalendarEventViewSet,
    AnalyticsSummaryView,
    AnalyticsClassPerformanceView,
    AnalyticsSubjectPerformanceView,
    AnalyticsAtRiskView,
    AnalyticsStudentProfileView,
    AnalyticsTeacherPerformanceView,
    AnalyticsTrendView,
    AcademicYearsRefView,
    TermsRefView,
    ClassesRefView,
)

router = DefaultRouter()
router.register("years", AcademicYearViewSet, basename="academics_years")
router.register("terms", TermViewSet, basename="academics_terms")
router.register("grade-levels", GradeLevelViewSet, basename="academics_grade_levels")
router.register("classes", SchoolClassViewSet, basename="academics_classes")
router.register("departments", DepartmentViewSet, basename="academics_departments")
router.register("subjects", SubjectViewSet, basename="academics_subjects")
router.register("subject-mappings", SubjectMappingViewSet, basename="academics_subject_mappings")
router.register("syllabus", SyllabusTopicViewSet, basename="academics_syllabus")
router.register("enrollments", AcademicEnrollmentViewSet, basename="academics_enrollments")
router.register("teacher-assignments", TeacherAssignmentViewSet, basename="academics_teacher_assignments")
router.register("grading-schemes", GradingSchemeViewSet, basename="academics_grading_schemes")
router.register("grade-bands", GradeBandViewSet, basename="academics_grade_bands")
router.register("assessments", AssessmentViewSet, basename="academics_assessments")
router.register("grades", AssessmentGradeViewSet, basename="academics_grades")
router.register("term-results", TermResultViewSet, basename="academics_term_results")
router.register("report-cards", ReportCardViewSet, basename="academics_report_cards")
router.register("assignments", AssignmentViewSet, basename="academics_assignments")
router.register("submissions", AssignmentSubmissionViewSet, basename="academics_submissions")
router.register("calendar", CalendarEventViewSet, basename="academics_calendar")

urlpatterns = [
    path("analytics/summary/", AnalyticsSummaryView.as_view(), name="academics_analytics_summary"),
    path("analytics/class-performance/", AnalyticsClassPerformanceView.as_view(), name="academics_analytics_class_performance"),
    path("analytics/subject-performance/", AnalyticsSubjectPerformanceView.as_view(), name="academics_analytics_subject_performance"),
    path("analytics/at-risk/", AnalyticsAtRiskView.as_view(), name="academics_analytics_at_risk"),
    path("analytics/student/<int:student_id>/", AnalyticsStudentProfileView.as_view(), name="academics_analytics_student"),
    path("analytics/teacher/<int:teacher_id>/", AnalyticsTeacherPerformanceView.as_view(), name="academics_analytics_teacher"),
    path("analytics/trend/", AnalyticsTrendView.as_view(), name="academics_analytics_trend"),
    path("ref/academic-years/", AcademicYearsRefView.as_view(), name="academics_ref_years"),
    path("ref/terms/", TermsRefView.as_view(), name="academics_ref_terms"),
    path("ref/classes/", ClassesRefView.as_view(), name="academics_ref_classes"),
    path("syllabus/progress/", SyllabusProgressView.as_view(), name="academics_syllabus_progress"),
    path("", include(router.urls)),
]
