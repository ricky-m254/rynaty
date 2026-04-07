from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from hr.models import AttendanceRecord as HrAttendanceRecord
from hr.models import Department as HrDepartment
from hr.models import Employee
from hr.views import DepartmentViewSet as HrDepartmentViewSet
from school.models import Module, Role, UserProfile

from .models import StaffAttendance, StaffDepartment, StaffMember, StaffRole
from .views import (
    StaffAssignmentViewSet,
    StaffAttendanceViewSet,
    StaffDepartmentViewSet,
    StaffMemberViewSet,
    StaffReconciliationView,
    StaffRoleViewSet,
)

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="staff_bridge_test",
                name="Staff Bridge Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="staff-bridge.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class StaffBridgeConsolidationTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="phase4_staff_admin", password="pass1234")
        role = Role.objects.create(name="ADMIN", description="School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.create(key="STAFF", name="Staff Management")
        Module.objects.create(key="HR", name="Human Resources")

    def _create_staff(self):
        request = self.factory.post(
            "/api/staff/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "staff_type": "Teaching",
                "employment_type": "Full-time",
                "status": "Active",
                "join_date": "2026-01-10",
                "email_work": "jane.doe@school.local",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = StaffMemberViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 201)
        return StaffMember.objects.get(pk=response.data["id"]), response

    def _create_department(self):
        request = self.factory.post(
            "/api/staff/departments/",
            {"name": "Sciences", "code": "SCI", "department_type": "Academic", "description": "Science Wing"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = StaffDepartmentViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 201)
        return StaffDepartment.objects.get(pk=response.data["id"]), response

    def _create_role(self):
        request = self.factory.post(
            "/api/staff/roles/",
            {"name": "Teacher", "code": "TEACHER", "level": 3},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = StaffRoleViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 201)
        return StaffRole.objects.get(pk=response.data["id"])

    def test_staff_member_create_creates_canonical_hr_employee(self):
        staff_member, response = self._create_staff()

        staff_member.refresh_from_db()
        self.assertIsNotNone(staff_member.hr_employee_id)
        employee = staff_member.hr_employee
        self.assertTrue(employee.employee_id.startswith("EMP-"))
        self.assertEqual(employee.first_name, "Jane")
        self.assertEqual(employee.last_name, "Doe")
        self.assertEqual(employee.join_date.isoformat(), "2026-01-10")
        self.assertEqual(response.data["hr_employee"], employee.id)
        self.assertEqual(response.data["hr_employee_id"], employee.employee_id)

    def test_staff_department_create_creates_hr_department_and_school_shadow(self):
        department, response = self._create_department()

        department.refresh_from_db()
        self.assertIsNotNone(department.hr_department_id)
        hr_department = department.hr_department
        self.assertEqual(hr_department.name, "Sciences")
        self.assertEqual(hr_department.code, "SCI")
        self.assertIsNotNone(hr_department.school_department_id)
        self.assertEqual(response.data["hr_department"], hr_department.id)
        self.assertEqual(response.data["school_department"], hr_department.school_department_id)

    def test_primary_assignment_refreshes_employee_department(self):
        staff_member, _ = self._create_staff()
        department, _ = self._create_department()
        role = self._create_role()

        request = self.factory.post(
            "/api/staff/assignments/",
            {
                "staff": staff_member.id,
                "department": department.id,
                "role": role.id,
                "is_primary": True,
                "effective_from": "2026-01-10",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = StaffAssignmentViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 201)

        staff_member.refresh_from_db()
        department.refresh_from_db()
        self.assertEqual(
            staff_member.hr_employee.department_id,
            department.hr_department_id,
        )

    def test_attendance_mark_writes_canonical_hr_attendance(self):
        staff_member, _ = self._create_staff()

        request = self.factory.post(
            "/api/staff/attendance/mark/",
            {
                "records": [
                    {
                        "staff": staff_member.id,
                        "date": "2026-03-30",
                        "status": "Late",
                        "clock_in": "08:10:00",
                        "clock_out": "16:05:00",
                        "notes": "Traffic delay",
                    }
                ]
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = StaffAttendanceViewSet.as_view({"post": "mark"})(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["created"], 1)

        attendance = StaffAttendance.objects.get(staff=staff_member, date="2026-03-30")
        self.assertIsNotNone(attendance.hr_attendance_id)
        hr_attendance = HrAttendanceRecord.objects.get(pk=attendance.hr_attendance_id)
        self.assertEqual(hr_attendance.employee_id, staff_member.hr_employee_id)
        self.assertEqual(hr_attendance.status, "Late")
        self.assertEqual(str(hr_attendance.clock_in), "08:10:00")
        self.assertEqual(str(hr_attendance.clock_out), "16:05:00")
        self.assertEqual(hr_attendance.notes, "Traffic delay")

    def test_reconciliation_endpoint_reports_unmapped_legacy_rows(self):
        StaffMember.objects.create(
            first_name="Legacy",
            last_name="User",
            staff_id="LEG-001",
            staff_type="Administrative",
            employment_type="Full-time",
            status="Active",
        )

        request = self.factory.get("/api/staff/analytics/reconciliation/")
        force_authenticate(request, user=self.user)
        response = StaffReconciliationView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unmapped_staff_members"]["count"], 1)
        self.assertEqual(response.data["unmapped_staff_members"]["rows"][0]["staff_id"], "LEG-001")

    def test_hr_department_api_uses_canonical_hr_department_model(self):
        request = self.factory.post(
            "/api/hr/departments/",
            {"name": "Human Resources", "code": "HR", "description": "People operations"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = HrDepartmentViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 201)

        department = HrDepartment.objects.get(pk=response.data["id"])
        self.assertEqual(department.code, "HR")
        self.assertIsNotNone(department.school_department_id)
        self.assertEqual(response.data["school_department"], department.school_department_id)
        self.assertFalse(Employee.objects.filter(department_id=response.data["id"]).exists())
