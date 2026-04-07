from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, UserProfile

from .models import Department, Employee, JobPosting, Position, WorkSchedule
from .views import DepartmentViewSet, EmployeeViewSet, JobPostingViewSet, WorkScheduleViewSet

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="hr_department_fk_cleanup",
                name="HR Department FK Cleanup School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="hr-cleanup.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class HrDepartmentForeignKeyCleanupTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_cleanup_admin", password="pass1234")
        role = Role.objects.create(name="ADMIN", description="School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.create(key="HR", name="Human Resources")

        self.department = Department.objects.create(name="Academics", code="HR-ACA", is_active=True)
        self.position = Position.objects.create(title="Teacher", department=self.department, headcount=3, is_active=True)

    def test_employee_create_and_filter_use_hr_department_ids(self):
        create_request = self.factory.post(
            "/api/hr/employees/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "date_of_birth": "1990-01-01",
                "gender": "Female",
                "nationality": "Kenyan",
                "department": self.department.id,
                "position": self.position.id,
                "employment_type": "Full-time",
                "status": "Active",
                "join_date": "2026-01-10",
                "notice_period_days": 30,
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = EmployeeViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["department"], self.department.id)
        self.assertEqual(create_response.data["department_name"], "Academics")

        list_request = self.factory.get(f"/api/hr/employees/?department={self.department.id}")
        force_authenticate(list_request, user=self.user)
        list_response = EmployeeViewSet.as_view({"get": "list"})(list_request)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]["department"], self.department.id)

    def test_department_employees_endpoint_reads_direct_hr_relationship(self):
        employee = Employee.objects.create(
            employee_id="EMP-HR-001",
            first_name="Sam",
            last_name="Hill",
            date_of_birth="1989-01-01",
            gender="Male",
            department=self.department,
            position=self.position,
            join_date="2026-01-01",
            status="Active",
            employment_type="Full-time",
            is_active=True,
        )

        employees_request = self.factory.get(f"/api/hr/departments/{self.department.id}/employees/")
        force_authenticate(employees_request, user=self.user)
        employees_response = DepartmentViewSet.as_view({"get": "employees"})(employees_request, pk=self.department.id)
        self.assertEqual(employees_response.status_code, 200)
        self.assertEqual(len(employees_response.data), 1)
        self.assertEqual(employees_response.data[0]["id"], employee.id)

        org_request = self.factory.get("/api/hr/departments/org-chart/")
        force_authenticate(org_request, user=self.user)
        org_response = DepartmentViewSet.as_view({"get": "org_chart"})(org_request)
        self.assertEqual(org_response.status_code, 200)
        self.assertEqual(org_response.data[0]["employee_count"], 1)

    def test_work_schedule_and_job_posting_filters_use_hr_department_ids(self):
        employee = Employee.objects.create(
            employee_id="EMP-HR-002",
            first_name="Ava",
            last_name="Ray",
            date_of_birth="1992-02-01",
            gender="Female",
            department=self.department,
            position=self.position,
            join_date="2026-01-01",
            status="Active",
            employment_type="Full-time",
            is_active=True,
        )
        schedule = WorkSchedule.objects.create(
            employee=employee,
            department=self.department,
            shift_start="08:00:00",
            shift_end="17:00:00",
            working_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
            effective_from="2026-01-01",
            is_active=True,
        )
        posting = JobPosting.objects.create(
            position=self.position,
            department=self.department,
            title="Biology Teacher",
            employment_type="Full-time",
            status="Draft",
            posted_by=self.user,
            is_active=True,
        )

        schedule_request = self.factory.get(f"/api/hr/work-schedules/?department={self.department.id}")
        force_authenticate(schedule_request, user=self.user)
        schedule_response = WorkScheduleViewSet.as_view({"get": "list"})(schedule_request)
        self.assertEqual(schedule_response.status_code, 200)
        self.assertEqual(len(schedule_response.data), 1)
        self.assertEqual(schedule_response.data[0]["id"], schedule.id)
        self.assertEqual(schedule_response.data[0]["department"], self.department.id)

        posting_request = self.factory.get(f"/api/hr/job-postings/?department={self.department.id}")
        force_authenticate(posting_request, user=self.user)
        posting_response = JobPostingViewSet.as_view({"get": "list"})(posting_request)
        self.assertEqual(posting_response.status_code, 200)
        self.assertEqual(len(posting_response.data), 1)
        self.assertEqual(posting_response.data[0]["id"], posting.id)
        self.assertEqual(posting_response.data[0]["department"], self.department.id)
