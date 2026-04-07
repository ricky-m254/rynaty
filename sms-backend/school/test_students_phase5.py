from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import AttendanceRecord, Module, Role, Student, UserModuleAssignment, UserProfile
from school.views import AttendanceRecordsCsvExportView


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="students_phase5_test",
                name="Students Phase5 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="students-phase5.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class StudentsPhase5AttendanceExportTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        students_module, _ = Module.objects.get_or_create(key="STUDENTS", defaults={"name": "Students"})
        role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "Admin"})
        self.user = User.objects.create_user(username="students_phase5_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=role)
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

        self.student = Student.objects.create(
            admission_number="S-SP5-001",
            first_name="Phase",
            last_name="Five",
            date_of_birth="2012-01-01",
            gender="F",
            is_active=True,
        )
        AttendanceRecord.objects.create(
            student=self.student,
            date="2026-02-14",
            status="Present",
            notes="On time",
            recorded_by=self.user,
        )
        AttendanceRecord.objects.create(
            student=self.student,
            date="2026-02-15",
            status="Absent",
            notes="Sick leave",
            recorded_by=self.user,
        )

    def test_attendance_csv_export_respects_status_filter(self):
        request = self.factory.get("/api/attendance/records/export/csv/?status=Absent")
        force_authenticate(request, user=self.user)
        response = AttendanceRecordsCsvExportView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode("utf-8")
        self.assertIn("attendance_records_report.csv", response["Content-Disposition"])
        self.assertIn("Sick leave", content)
        self.assertNotIn("On time", content)
