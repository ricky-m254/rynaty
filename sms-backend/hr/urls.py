from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AbsenceAlertViewSet,
    AttendanceViewSet,
    DepartmentViewSet,
    EmployeeDocumentViewSet,
    EmployeeEmploymentProfileViewSet,
    EmployeeQualificationViewSet,
    EmployeeViewSet,
    EmergencyContactViewSet,
    HrAnalyticsSummaryView,
    HrAnalyticsHeadcountView,
    HrAnalyticsTurnoverView,
    HrAnalyticsAttendanceView,
    HrAnalyticsLeaveView,
    HrAnalyticsDiversityView,
    HrAnalyticsPayrollCostsView,
    HrAuditLogView,
    HrComplianceView,
    LeaveBalanceView,
    LeaveCalendarView,
    LeavePolicyViewSet,
    LeaveRequestViewSet,
    LeaveTypeViewSet,
    JobApplicationViewSet,
    JobPostingViewSet,
    InterviewViewSet,
    OnboardingChecklistView,
    OnboardingTaskViewSet,
    PerformanceGoalViewSet,
    PerformanceReviewViewSet,
    PayrollBatchViewSet,
    PayrollItemViewSet,
    PositionViewSet,
    ReturnToWorkReconciliationViewSet,
    ShiftTemplateViewSet,
    SalaryComponentViewSet,
    SalaryStructureViewSet,
    StatutoryDeductionBandViewSet,
    StatutoryDeductionRuleViewSet,
    StaffRefView,
    StaffCareerActionViewSet,
    DisciplinaryCaseViewSet,
    ExitCaseViewSet,
    ExitClearanceItemViewSet,
    StaffLifecycleEventViewSet,
    StaffViewSet,
    TeachingSubstituteAssignmentViewSet,
    TrainingEnrollmentViewSet,
    TrainingProgramViewSet,
    WorkScheduleViewSet,
    StaffTransferViewSet,
)

router = DefaultRouter()
router.register(r"staff", StaffViewSet, basename="hr_staff")
router.register(r"employees", EmployeeViewSet, basename="hr_employee")
router.register(r"employment-profiles", EmployeeEmploymentProfileViewSet, basename="hr_employment_profile")
router.register(r"qualifications", EmployeeQualificationViewSet, basename="hr_qualification")
router.register(r"emergency-contacts", EmergencyContactViewSet, basename="hr_emergency_contact")
router.register(r"documents", EmployeeDocumentViewSet, basename="hr_document")
router.register(r"departments", DepartmentViewSet, basename="hr_department")
router.register(r"positions", PositionViewSet, basename="hr_position")
router.register(r"shift-templates", ShiftTemplateViewSet, basename="hr_shift_template")
router.register(r"attendance", AttendanceViewSet, basename="hr_attendance")
router.register(r"absence-alerts", AbsenceAlertViewSet, basename="hr_absence_alert")
router.register(r"substitute-assignments", TeachingSubstituteAssignmentViewSet, basename="hr_substitute_assignment")
router.register(r"schedules", WorkScheduleViewSet, basename="hr_schedule")
router.register(r"leave-types", LeaveTypeViewSet, basename="hr_leave_type")
router.register(r"leave-policies", LeavePolicyViewSet, basename="hr_leave_policy")
router.register(r"leave-requests", LeaveRequestViewSet, basename="hr_leave_request")
router.register(r"return-to-work", ReturnToWorkReconciliationViewSet, basename="hr_return_to_work")
router.register(r"salary-structures", SalaryStructureViewSet, basename="hr_salary_structure")
router.register(r"salary-components", SalaryComponentViewSet, basename="hr_salary_component")
router.register(r"statutory-rules", StatutoryDeductionRuleViewSet, basename="hr_statutory_rule")
router.register(r"statutory-bands", StatutoryDeductionBandViewSet, basename="hr_statutory_band")
router.register(r"payrolls", PayrollBatchViewSet, basename="hr_payroll")
router.register(r"payslips", PayrollItemViewSet, basename="hr_payslip")
router.register(r"job-postings", JobPostingViewSet, basename="hr_job_posting")
router.register(r"applications", JobApplicationViewSet, basename="hr_application")
router.register(r"interviews", InterviewViewSet, basename="hr_interview")
router.register(r"onboarding", OnboardingTaskViewSet, basename="hr_onboarding")
router.register(r"performance-goals", PerformanceGoalViewSet, basename="hr_performance_goal")
router.register(r"performance-reviews", PerformanceReviewViewSet, basename="hr_performance_review")
router.register(r"training-programs", TrainingProgramViewSet, basename="hr_training_program")
router.register(r"training-enrollments", TrainingEnrollmentViewSet, basename="hr_training_enrollment")
router.register(r"lifecycle-events", StaffLifecycleEventViewSet, basename="hr_lifecycle_event")
router.register(r"career-actions", StaffCareerActionViewSet, basename="hr_career_action")
router.register(r"disciplinary-cases", DisciplinaryCaseViewSet, basename="hr_disciplinary_case")
router.register(r"exits", ExitCaseViewSet, basename="hr_exit_case")
router.register(r"exit-clearance-items", ExitClearanceItemViewSet, basename="hr_exit_clearance_item")
router.register(r"transfers", StaffTransferViewSet, basename="hr_transfer")

urlpatterns = [
    path("ref/staff/", StaffRefView.as_view(), name="hr_ref_staff"),
    path("analytics/summary/", HrAnalyticsSummaryView.as_view(), name="hr_analytics_summary"),
    path("analytics/headcount/", HrAnalyticsHeadcountView.as_view(), name="hr_analytics_headcount"),
    path("analytics/turnover/", HrAnalyticsTurnoverView.as_view(), name="hr_analytics_turnover"),
    path("analytics/attendance/", HrAnalyticsAttendanceView.as_view(), name="hr_analytics_attendance"),
    path("analytics/leave/", HrAnalyticsLeaveView.as_view(), name="hr_analytics_leave"),
    path("analytics/diversity/", HrAnalyticsDiversityView.as_view(), name="hr_analytics_diversity"),
    path("analytics/payroll-costs/", HrAnalyticsPayrollCostsView.as_view(), name="hr_analytics_payroll_costs"),
    path("leave-balance/<int:employee_id>/", LeaveBalanceView.as_view(), name="hr_leave_balance"),
    path("leave-calendar/", LeaveCalendarView.as_view(), name="hr_leave_calendar"),
    path("audit-logs/", HrAuditLogView.as_view(), name="hr_audit_logs"),
    path("compliance/", HrComplianceView.as_view(), name="hr_compliance"),
    path("onboarding/<int:employee_id>/", OnboardingChecklistView.as_view(), name="hr_onboarding_checklist"),
    path(
        "documents/upload/",
        EmployeeDocumentViewSet.as_view({"post": "create"}),
        name="hr_document_upload",
    ),
    path("", include(router.urls)),
]
