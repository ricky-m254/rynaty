from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import (
    AcademicYear,
    AdmissionApplication,
    AttendanceRecord,
    BehaviorIncident,
    Module,
    Role,
    SchoolClass,
    Student,
    Term,
    UserModuleAssignment,
    UserProfile,
)
from school.views import StudentsDashboardView


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="students_phase7_test",
                name="Students Phase7 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="students-phase7.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class StudentsPhase7DashboardTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        students_module = Module.objects.create(key="STUDENTS", name="Students")
        role = Role.objects.create(name="ADMIN", description="Admin")
        self.user = User.objects.create_user(username="students_phase7_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=role)
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

        self.student = Student.objects.create(
            admission_number="S-SP7-001",
            first_name="Phase",
            last_name="Seven",
            date_of_birth=date(2012, 1, 1),
            gender="M",
            is_active=True,
        )
        AttendanceRecord.objects.create(
            student=self.student,
            date=date(2026, 2, 12),
            status="Present",
            recorded_by=self.user,
        )
        AttendanceRecord.objects.create(
            student=self.student,
            date=date(2026, 2, 13),
            status="Absent",
            recorded_by=self.user,
        )
        AttendanceRecord.objects.create(
            student=self.student,
            date=date(2026, 2, 14),
            status="Absent",
            recorded_by=self.user,
        )
        BehaviorIncident.objects.create(
            student=self.student,
            incident_type="Negative",
            category="Discipline",
            incident_date=date(2026, 2, 14),
            severity="Critical",
            description="Major incident",
            reported_by=self.user,
        )

        year = AcademicYear.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        Term.objects.create(academic_year=year, name="Term 1", start_date=date(2026, 1, 1), end_date=date(2026, 4, 30))
        school_class = SchoolClass.objects.create(name="Grade 7", stream="A", academic_year=year)
        AdmissionApplication.objects.create(
            student_first_name="New",
            student_last_name="Applicant",
            student_dob=date(2013, 1, 1),
            student_gender="Male",
            applying_for_grade=school_class,
            application_date=date(2026, 2, 14),
            status="Submitted",
            guardian_name="Guardian",
            guardian_phone="0712345678",
            guardian_email="guardian@example.com",
        )

    def test_students_dashboard_payload(self):
        request = self.factory.get("/api/students/dashboard/")
        force_authenticate(request, user=self.user)
        response = StudentsDashboardView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("kpis", response.data)
        self.assertIn("alerts", response.data)
        self.assertIn("recent_activity", response.data)
        self.assertEqual(response.data["kpis"]["students_active"], 1)
        self.assertEqual(response.data["kpis"]["pending_admissions"], 1)
        self.assertEqual(response.data["kpis"]["attendance_rate"], 33.33)
        self.assertEqual(response.data["alerts"]["low_attendance_students"], 1)
        self.assertGreaterEqual(response.data["alerts"]["critical_behavior_incidents"], 1)
        self.assertGreaterEqual(len(response.data["recent_activity"]), 1)
