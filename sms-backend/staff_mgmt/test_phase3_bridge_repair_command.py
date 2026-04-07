from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from clients.models import Domain, Tenant
from hr.models import Department as HrDepartment
from hr.models import Employee
from school.models import Module, Role, UserProfile

from .models import StaffAssignment, StaffAttendance, StaffDepartment, StaffMember, StaffRole

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="people_org_bridge_cmd",
                name="People Org Bridge Command School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="people-org-bridge.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class RepairPeopleOrgBridgesCommandTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="bridge_cmd_admin", password="pass1234")
        role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "School Administrator"})
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.get_or_create(key="STAFF", defaults={"name": "Staff Management"})
        Module.objects.get_or_create(key="HR", defaults={"name": "Human Resources"})

    def test_command_repairs_staff_hr_and_school_department_bridges(self):
        head_staff = StaffMember.objects.create(
            first_name="Mary",
            last_name="Head",
            staff_id="LEG-HEAD-001",
            staff_type="Teaching",
            employment_type="Full-time",
            status="Active",
            join_date="2026-01-10",
        )
        staff_member = StaffMember.objects.create(
            first_name="John",
            last_name="Worker",
            staff_id="LEG-001",
            staff_type="Teaching",
            employment_type="Full-time",
            status="Active",
            join_date="2026-01-10",
        )
        department = StaffDepartment.objects.create(
            name="Sciences",
            code="SCI",
            department_type="Academic",
            head=head_staff,
            description="Science Wing",
            is_active=True,
        )
        role = StaffRole.objects.create(name="Teacher", code="TEACHER", level=3, is_active=True)
        StaffAssignment.objects.create(
            staff=staff_member,
            department=department,
            role=role,
            is_primary=True,
            effective_from="2026-01-10",
            is_active=True,
        )
        attendance = StaffAttendance.objects.create(
            staff=staff_member,
            date="2026-03-30",
            status="Late",
            clock_in="08:10:00",
            clock_out="16:05:00",
            notes="Traffic delay",
            is_active=True,
        )

        stdout = StringIO()
        call_command("repair_people_org_bridges", stdout=stdout)

        department.refresh_from_db()
        staff_member.refresh_from_db()
        attendance.refresh_from_db()

        self.assertIsNotNone(department.hr_department_id)
        hr_department = HrDepartment.objects.get(pk=department.hr_department_id)
        self.assertIsNotNone(hr_department.school_department_id)

        self.assertIsNotNone(staff_member.hr_employee_id)
        employee = Employee.objects.get(pk=staff_member.hr_employee_id)
        self.assertEqual(employee.department_id, department.hr_department_id)

        self.assertIsNotNone(attendance.hr_attendance_id)
        self.assertEqual(attendance.hr_attendance.employee_id, employee.id)
        self.assertIn("[people_org_bridge_cmd] APPLIED:", stdout.getvalue())
        self.assertIn("staff_without_hr_employee=0", stdout.getvalue())
