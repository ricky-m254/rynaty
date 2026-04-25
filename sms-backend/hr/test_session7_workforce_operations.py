from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, UserModuleAssignment, UserProfile

from .models import (
    AbsenceAlert,
    AttendanceRecord,
    Department,
    Employee,
    LeavePolicy,
    LeaveRequest,
    LeaveType,
    Position,
    ReturnToWorkReconciliation,
    ShiftTemplate,
    TeachingSubstituteAssignment,
    WorkSchedule,
)
from .views import (
    AbsenceAlertViewSet,
    AttendanceViewSet,
    LeaveRequestViewSet,
    PayrollBatchViewSet,
    ReturnToWorkReconciliationViewSet,
    TeachingSubstituteAssignmentViewSet,
)

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="hr_test",
                name="HR Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="hr.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class HrSession7ShiftAndAlertTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_session7", password="pass1234")
        self.manager_user = User.objects.create_user(username="line_manager", password="pass1234")
        self.hr_user = User.objects.create_user(username="hr_final", password="pass1234")
        self.other_teacher_user = User.objects.create_user(username="other_teacher", password="pass1234")
        admin_role, _ = Role.objects.get_or_create(
            name="ADMIN",
            defaults={"description": "School Administrator"},
        )
        hod_role, _ = Role.objects.get_or_create(
            name="HOD",
            defaults={"description": "Head of Department"},
        )
        hr_role, _ = Role.objects.get_or_create(
            name="HR_OFFICER",
            defaults={"description": "HR Officer"},
        )
        teacher_role, _ = Role.objects.get_or_create(
            name="TEACHER",
            defaults={"description": "Teaching Staff"},
        )
        UserProfile.objects.create(user=self.user, role=admin_role)
        UserProfile.objects.create(user=self.manager_user, role=hod_role)
        UserProfile.objects.create(user=self.hr_user, role=hr_role)
        UserProfile.objects.create(user=self.other_teacher_user, role=teacher_role)
        self.hr_module, _ = Module.objects.get_or_create(key="HR", defaults={"name": "Human Resources"})
        self.academics_module, _ = Module.objects.get_or_create(key="ACADEMICS", defaults={"name": "Academics"})
        UserModuleAssignment.objects.create(user=self.manager_user, module=self.academics_module, is_active=True)
        UserModuleAssignment.objects.create(user=self.hr_user, module=self.hr_module, is_active=True)
        UserModuleAssignment.objects.create(user=self.other_teacher_user, module=self.academics_module, is_active=True)

        self.department = Department.objects.create(name="Operations", code="OPS7", is_active=True)
        self.position = Position.objects.create(title="Operations Officer", department=self.department, headcount=3, is_active=True)
        self.manager = Employee.objects.create(
            user=self.manager_user,
            employee_id="EMP-S7-MGR",
            first_name="Mara",
            last_name="Lead",
            date_of_birth=date(1988, 1, 1),
            gender="Female",
            department=self.department,
            position=self.position,
            staff_category="OPERATIONS",
            employment_type="Full-time",
            join_date=date(2024, 1, 1),
            status="Active",
        )
        self.employee = Employee.objects.create(
            employee_id="EMP-S7-001",
            first_name="Alex",
            last_name="Stone",
            date_of_birth=date(1994, 2, 2),
            gender="Male",
            department=self.department,
            position=self.position,
            staff_category="OPERATIONS",
            employment_type="Full-time",
            join_date=date(2026, 1, 1),
            reporting_to=self.manager,
            status="Active",
        )
        self.hr_employee = Employee.objects.create(
            user=self.hr_user,
            employee_id="EMP-S7-HR",
            first_name="Helen",
            last_name="Rights",
            date_of_birth=date(1987, 3, 3),
            gender="Female",
            department=self.department,
            position=self.position,
            staff_category="ADMIN",
            employment_type="Full-time",
            join_date=date(2025, 1, 1),
            status="Active",
        )
        self.teaching_department = Department.objects.create(name="Academics", code="ACAS7", is_active=True)
        self.teacher_position = Position.objects.create(title="Teacher", department=self.teaching_department, headcount=4, is_active=True)
        self.other_teacher = Employee.objects.create(
            user=self.other_teacher_user,
            employee_id="EMP-S7-OTH",
            first_name="Toni",
            last_name="Other",
            date_of_birth=date(1992, 4, 4),
            gender="Female",
            department=self.teaching_department,
            position=self.teacher_position,
            staff_category="TEACHING",
            employment_type="Full-time",
            join_date=date(2025, 1, 1),
            status="Active",
        )

    def _create_leave_type_policy(self):
        leave_type = LeaveType.objects.create(
            name="Annual Leave",
            code="ANNUAL-S7",
            is_paid=True,
            requires_approval=True,
            requires_document=False,
            max_days_year=30,
            notice_days=7,
            color="#16A34A",
            is_active=True,
        )
        LeavePolicy.objects.create(
            leave_type=leave_type,
            employment_type="Full-time",
            entitlement_days="24.00",
            accrual_method="Annual",
            carry_forward_max=5,
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        return leave_type

    def _create_approved_long_leave(self):
        leave_type = self._create_leave_type_policy()
        create_request = self.factory.post(
            "/api/hr/leave-requests/",
            {
                "employee": self.employee.id,
                "leave_type": leave_type.id,
                "start_date": "2026-04-06",
                "end_date": "2026-04-12",
                "reason": "Family travel",
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = LeaveRequestViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)

        leave_request = LeaveRequest.objects.get(pk=create_response.data["id"])

        manager_request = self.factory.post(f"/api/hr/leave-requests/{leave_request.id}/manager-approve/", {}, format="json")
        force_authenticate(manager_request, user=self.manager_user)
        manager_response = LeaveRequestViewSet.as_view({"post": "manager_approve"})(manager_request, pk=leave_request.id)
        self.assertEqual(manager_response.status_code, 200)

        final_request = self.factory.post(f"/api/hr/leave-requests/{leave_request.id}/hr-final-approve/", {}, format="json")
        force_authenticate(final_request, user=self.hr_user)
        final_response = LeaveRequestViewSet.as_view({"post": "hr_final_approve"})(final_request, pk=leave_request.id)
        self.assertEqual(final_response.status_code, 200)

        leave_request.refresh_from_db()
        return leave_request

    def _create_shift_template(self, *, code, name, shift_start, shift_end, grace_minutes=15, working_days=None):
        return ShiftTemplate.objects.create(
            code=code,
            name=name,
            staff_category="OPERATIONS",
            shift_start=shift_start,
            shift_end=shift_end,
            working_days=working_days or ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            break_duration_minutes=60,
            grace_minutes=grace_minutes,
            requires_biometric_clock=False,
            overtime_eligible=True,
            is_active=True,
        )

    def _create_schedule(self, *, shift_template, employee=None, department=None, effective_from=date(2026, 4, 1), assignment_priority=100):
        return WorkSchedule.objects.create(
            employee=employee,
            department=department,
            shift_template=shift_template,
            assignment_priority=assignment_priority,
            staff_category_snapshot=(employee.staff_category if employee else shift_template.staff_category),
            shift_start=shift_template.shift_start,
            shift_end=shift_template.shift_end,
            working_days=shift_template.working_days,
            break_duration=shift_template.break_duration_minutes,
            effective_from=effective_from,
            is_active=True,
        )

    def test_employee_schedule_overrides_department_schedule_on_clock_in(self):
        department_shift = self._create_shift_template(
            code="OPS-DEPT-AM",
            name="Department Morning",
            shift_start=time(6, 0, 0),
            shift_end=time(14, 0, 0),
            grace_minutes=5,
        )
        employee_shift = self._create_shift_template(
            code="OPS-EMP-DAY",
            name="Employee Day",
            shift_start=time(8, 0, 0),
            shift_end=time(16, 0, 0),
            grace_minutes=10,
        )
        self._create_schedule(shift_template=department_shift, department=self.department, assignment_priority=50)
        self._create_schedule(shift_template=employee_shift, employee=self.employee, assignment_priority=10)

        request = self.factory.post(
            "/api/hr/attendance/clock-in/",
            {"employee": self.employee.id, "date": "2026-04-06", "clock_in": "08:05:00"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = AttendanceViewSet.as_view({"post": "clock_in"})(request)

        self.assertEqual(response.status_code, 200)
        record = AttendanceRecord.objects.get(employee=self.employee, date="2026-04-06")
        self.assertEqual(record.shift_template_id, employee_shift.id)
        self.assertEqual(record.scheduled_shift_start, time(8, 0, 0))
        self.assertEqual(record.status, "Present")
        self.assertEqual(record.attendance_source, "MANUAL")

    def test_unscheduled_day_does_not_create_absence_alert(self):
        monday_only = self._create_shift_template(
            code="OPS-MON",
            name="Monday Shift",
            shift_start=time(8, 0, 0),
            shift_end=time(16, 0, 0),
            working_days=["Monday"],
        )
        self._create_schedule(shift_template=monday_only, employee=self.employee)

        request = self.factory.post(
            "/api/hr/absence-alerts/evaluate/",
            {
                "employee": self.employee.id,
                "date": "2026-04-07",
                "triggered_at": "2026-04-07T10:00:00+03:00",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = AbsenceAlertViewSet.as_view({"post": "evaluate"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reason"], "unscheduled")
        self.assertIsNone(response.data["alert"])
        self.assertFalse(AbsenceAlert.objects.filter(employee=self.employee, alert_date="2026-04-07").exists())

    def test_missed_check_in_creates_manager_first_alert(self):
        shift_template = self._create_shift_template(
            code="OPS-MAIN",
            name="Operations Main",
            shift_start=time(8, 0, 0),
            shift_end=time(16, 0, 0),
            grace_minutes=15,
        )
        self._create_schedule(shift_template=shift_template, employee=self.employee)

        request = self.factory.post(
            "/api/hr/absence-alerts/evaluate/",
            {
                "employee": self.employee.id,
                "date": "2026-04-06",
                "triggered_at": "2026-04-06T08:30:00+03:00",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = AbsenceAlertViewSet.as_view({"post": "evaluate"})(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["reason"], "alert_open")
        alert = AbsenceAlert.objects.get(employee=self.employee, alert_date="2026-04-06")
        record = AttendanceRecord.objects.get(employee=self.employee, date="2026-04-06")

        self.assertEqual(alert.status, "OPEN")
        self.assertEqual(alert.notified_manager_id, self.manager.id)
        self.assertFalse(alert.hr_copied)
        self.assertEqual(record.status, "Absent")
        self.assertEqual(record.alert_status, "OPEN")
        self.assertEqual(record.payroll_feed_status, "BLOCKED_ALERT")

    def test_late_clock_in_auto_resolves_open_alert(self):
        shift_template = self._create_shift_template(
            code="OPS-LATE",
            name="Operations Late",
            shift_start=time(8, 0, 0),
            shift_end=time(16, 0, 0),
            grace_minutes=10,
        )
        self._create_schedule(shift_template=shift_template, employee=self.employee)

        evaluate_request = self.factory.post(
            "/api/hr/absence-alerts/evaluate/",
            {
                "employee": self.employee.id,
                "date": "2026-04-06",
                "triggered_at": "2026-04-06T08:20:00+03:00",
            },
            format="json",
        )
        force_authenticate(evaluate_request, user=self.user)
        evaluate_response = AbsenceAlertViewSet.as_view({"post": "evaluate"})(evaluate_request)
        self.assertEqual(evaluate_response.status_code, 201)

        clock_in_request = self.factory.post(
            "/api/hr/attendance/clock-in/",
            {"employee": self.employee.id, "date": "2026-04-06", "clock_in": "08:25:00"},
            format="json",
        )
        force_authenticate(clock_in_request, user=self.user)
        clock_in_response = AttendanceViewSet.as_view({"post": "clock_in"})(clock_in_request)

        self.assertEqual(clock_in_response.status_code, 200)
        alert = AbsenceAlert.objects.get(employee=self.employee, alert_date="2026-04-06")
        record = AttendanceRecord.objects.get(employee=self.employee, date="2026-04-06")

        self.assertEqual(alert.status, "AUTO_RESOLVED")
        self.assertEqual(record.status, "Late")
        self.assertEqual(record.alert_status, "AUTO_RESOLVED")
        self.assertEqual(record.payroll_feed_status, "READY")

    def test_teaching_substitute_assignment_requires_teaching_staff(self):
        non_teaching_record = AttendanceRecord.objects.create(
            employee=self.employee,
            date="2026-04-06",
            status="Absent",
            is_active=True,
        )
        teacher_substitute = Employee.objects.create(
            employee_id="EMP-S7-TSUB",
            first_name="Tina",
            last_name="Teach",
            date_of_birth=date(1990, 4, 4),
            gender="Female",
            department=self.teaching_department,
            position=self.teacher_position,
            staff_category="TEACHING",
            employment_type="Full-time",
            join_date=date(2025, 1, 1),
            status="Active",
        )

        request = self.factory.post(
            "/api/hr/substitute-assignments/",
            {
                "absent_employee": self.employee.id,
                "substitute_employee": teacher_substitute.id,
                "attendance_record": non_teaching_record.id,
                "assignment_date": "2026-04-06",
                "class_context": "Form 2 Mathematics",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = TeachingSubstituteAssignmentViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(TeachingSubstituteAssignment.objects.exists())

    def test_teaching_substitute_assignment_preserves_absent_teacher_attendance(self):
        absent_teacher = Employee.objects.create(
            employee_id="EMP-S7-TA",
            first_name="Abel",
            last_name="Teacher",
            date_of_birth=date(1991, 5, 5),
            gender="Male",
            department=self.teaching_department,
            position=self.teacher_position,
            staff_category="TEACHING",
            employment_type="Full-time",
            join_date=date(2025, 1, 1),
            status="Active",
        )
        substitute_teacher = Employee.objects.create(
            employee_id="EMP-S7-TB",
            first_name="Betty",
            last_name="Backup",
            date_of_birth=date(1992, 6, 6),
            gender="Female",
            department=self.teaching_department,
            position=self.teacher_position,
            staff_category="TEACHING",
            employment_type="Full-time",
            join_date=date(2025, 1, 1),
            status="Active",
        )
        attendance_record = AttendanceRecord.objects.create(
            employee=absent_teacher,
            date="2026-04-06",
            status="Absent",
            is_active=True,
        )

        request = self.factory.post(
            "/api/hr/substitute-assignments/",
            {
                "absent_employee": absent_teacher.id,
                "substitute_employee": substitute_teacher.id,
                "attendance_record": attendance_record.id,
                "assignment_date": "2026-04-06",
                "start_time": "08:00:00",
                "end_time": "15:00:00",
                "class_context": "Form 2 Mathematics",
                "reason": "Emergency sick leave",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = TeachingSubstituteAssignmentViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 201)
        attendance_record.refresh_from_db()
        self.assertEqual(attendance_record.status, "Absent")
        self.assertEqual(TeachingSubstituteAssignment.objects.count(), 1)

    def test_long_leave_requires_manager_then_hr_and_creates_reconciliation(self):
        leave_type = self._create_leave_type_policy()
        create_request = self.factory.post(
            "/api/hr/leave-requests/",
            {
                "employee": self.employee.id,
                "leave_type": leave_type.id,
                "start_date": "2026-04-06",
                "end_date": "2026-04-12",
                "reason": "Family travel",
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = LeaveRequestViewSet.as_view({"post": "create"})(create_request)

        self.assertEqual(create_response.status_code, 201)
        leave_request = LeaveRequest.objects.get(pk=create_response.data["id"])
        self.assertTrue(leave_request.requires_dual_approval)
        self.assertEqual(leave_request.approval_stage, "PENDING_MANAGER")
        self.assertEqual(leave_request.current_approver_id, self.manager.id)

        manager_request = self.factory.post(f"/api/hr/leave-requests/{leave_request.id}/manager-approve/", {}, format="json")
        force_authenticate(manager_request, user=self.manager_user)
        manager_response = LeaveRequestViewSet.as_view({"post": "manager_approve"})(manager_request, pk=leave_request.id)
        self.assertEqual(manager_response.status_code, 200)

        leave_request.refresh_from_db()
        self.assertEqual(leave_request.approval_stage, "PENDING_HR")
        self.assertEqual(leave_request.status, "Pending")
        self.assertEqual(leave_request.manager_approved_by_id, self.manager.id)

        final_request = self.factory.post(f"/api/hr/leave-requests/{leave_request.id}/hr-final-approve/", {}, format="json")
        force_authenticate(final_request, user=self.hr_user)
        final_response = LeaveRequestViewSet.as_view({"post": "hr_final_approve"})(final_request, pk=leave_request.id)
        self.assertEqual(final_response.status_code, 200)

        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, "Approved")
        self.assertEqual(leave_request.approval_stage, "APPROVED")
        self.assertEqual(leave_request.hr_approved_by_id, self.hr_employee.id)
        self.assertTrue(ReturnToWorkReconciliation.objects.filter(leave_request=leave_request, status="PENDING").exists())

        leave_records = AttendanceRecord.objects.filter(
            employee=self.employee,
            date__gte="2026-04-06",
            date__lte="2026-04-12",
            status="On Leave",
        )
        self.assertEqual(leave_records.count(), 7)
        self.assertTrue(all(record.payroll_feed_status == "BLOCKED_LEAVE" for record in leave_records))

    def test_hod_with_academics_module_can_approve_pending_manager_stage_without_hr_module(self):
        leave_type = self._create_leave_type_policy()
        create_request = self.factory.post(
            "/api/hr/leave-requests/",
            {
                "employee": self.employee.id,
                "leave_type": leave_type.id,
                "start_date": "2026-04-06",
                "end_date": "2026-04-12",
                "reason": "Department travel",
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = LeaveRequestViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)

        leave_request = LeaveRequest.objects.get(pk=create_response.data["id"])
        approve_request = self.factory.post(f"/api/hr/leave-requests/{leave_request.id}/approve/", {}, format="json")
        force_authenticate(approve_request, user=self.manager_user)
        approve_response = LeaveRequestViewSet.as_view({"post": "approve"})(approve_request, pk=leave_request.id)

        self.assertEqual(approve_response.status_code, 200)
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.approval_stage, "PENDING_HR")
        self.assertEqual(leave_request.manager_approved_by_id, self.manager.id)

    def test_non_manager_academic_staff_cannot_approve_pending_manager_stage(self):
        leave_type = self._create_leave_type_policy()
        create_request = self.factory.post(
            "/api/hr/leave-requests/",
            {
                "employee": self.employee.id,
                "leave_type": leave_type.id,
                "start_date": "2026-04-06",
                "end_date": "2026-04-12",
                "reason": "Department travel",
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = LeaveRequestViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)

        leave_request = LeaveRequest.objects.get(pk=create_response.data["id"])
        approve_request = self.factory.post(f"/api/hr/leave-requests/{leave_request.id}/approve/", {}, format="json")
        force_authenticate(approve_request, user=self.other_teacher_user)
        approve_response = LeaveRequestViewSet.as_view({"post": "approve"})(approve_request, pk=leave_request.id)

        self.assertEqual(approve_response.status_code, 400)
        self.assertEqual(
            approve_response.data["error"],
            "Only the assigned manager approver can approve this leave request.",
        )

    def test_leave_reject_accepts_legacy_reason_payload_from_approvals_hub(self):
        leave_type = self._create_leave_type_policy()
        create_request = self.factory.post(
            "/api/hr/leave-requests/",
            {
                "employee": self.employee.id,
                "leave_type": leave_type.id,
                "start_date": "2026-04-06",
                "end_date": "2026-04-12",
                "reason": "Department travel",
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = LeaveRequestViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)

        leave_request = LeaveRequest.objects.get(pk=create_response.data["id"])
        reject_request = self.factory.post(
            f"/api/hr/leave-requests/{leave_request.id}/reject/",
            {"reason": "Coverage unavailable"},
            format="json",
        )
        force_authenticate(reject_request, user=self.hr_user)
        reject_response = LeaveRequestViewSet.as_view({"post": "reject"})(reject_request, pk=leave_request.id)

        self.assertEqual(reject_response.status_code, 200)
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, "Rejected")
        self.assertEqual(leave_request.rejection_reason, "Coverage unavailable")

    def test_return_to_work_completion_unblocks_leave_period(self):
        leave_request = self._create_approved_long_leave()
        reconciliation = ReturnToWorkReconciliation.objects.get(leave_request=leave_request)
        return_record = AttendanceRecord.objects.create(
            employee=self.employee,
            date="2026-04-13",
            status="Present",
            is_active=True,
        )

        complete_request = self.factory.post(
            f"/api/hr/return-to-work/{reconciliation.id}/complete/",
            {
                "actual_return_date": "2026-04-13",
                "attendance_record": return_record.id,
                "substitute_closed": True,
                "notes": "Returned on schedule",
            },
            format="json",
        )
        force_authenticate(complete_request, user=self.hr_user)
        complete_response = ReturnToWorkReconciliationViewSet.as_view({"post": "complete"})(complete_request, pk=reconciliation.id)

        self.assertEqual(complete_response.status_code, 200)
        reconciliation.refresh_from_db()
        return_record.refresh_from_db()
        self.assertEqual(reconciliation.status, "COMPLETED")
        self.assertEqual(return_record.reconciliation_status, "COMPLETED")
        self.assertEqual(return_record.payroll_feed_status, "READY")
        self.assertFalse(
            AttendanceRecord.objects.filter(
                employee=self.employee,
                date__gte="2026-04-06",
                date__lte="2026-04-12",
                payroll_feed_status="BLOCKED_LEAVE",
            ).exists()
        )

    def test_workforce_feed_exposes_leave_and_blocker_state(self):
        self._create_approved_long_leave()

        request = self.factory.get(f"/api/hr/payrolls/workforce-feed/?month=4&year=2026&employee={self.employee.id}")
        force_authenticate(request, user=self.hr_user)
        response = PayrollBatchViewSet.as_view({"get": "workforce_feed"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["employee_count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["approved_leave_days_total"], "7.00")
        self.assertEqual(row["blocked_leave_days"], 7)
        self.assertEqual(row["open_return_reconciliation_count"], 1)
        self.assertFalse(row["is_payroll_ready"])
