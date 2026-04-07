from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import (
    AttendanceRecord,
    BehaviorIncident,
    ClinicVisit,
    MedicalRecord,
    Module,
    Role,
    Student,
    UserModuleAssignment,
    UserProfile,
)
from school.views import StudentOperationalSummaryView


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="students_phase6_test",
                name="Students Phase6 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="students-phase6.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class StudentsPhase6OperationalSummaryTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        students_module = Module.objects.create(key="STUDENTS", name="Students")
        role = Role.objects.create(name="ADMIN", description="Admin")
        self.user = User.objects.create_user(username="students_phase6_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=role)
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

        self.student = Student.objects.create(
            admission_number="S-SP6-001",
            first_name="Phase",
            last_name="Six",
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
            notes="Unwell",
            recorded_by=self.user,
        )
        BehaviorIncident.objects.create(
            student=self.student,
            incident_type="Negative",
            category="Discipline",
            incident_date="2026-02-15",
            severity="Medium",
            description="Late submission",
            reported_by=self.user,
        )
        MedicalRecord.objects.create(
            student=self.student,
            blood_type="O+",
            allergies="Dust",
        )
        ClinicVisit.objects.create(
            student=self.student,
            visit_date="2026-02-15",
            complaint="Headache",
            treatment="Rest",
            severity="Minor",
            attended_by=self.user,
            parent_notified=True,
        )

    def test_operational_summary_returns_expected_payload(self):
        request = self.factory.get(f"/api/students/{self.student.id}/operational-summary/")
        force_authenticate(request, user=self.user)
        response = StudentOperationalSummaryView.as_view()(request, student_id=self.student.id)

        self.assertEqual(response.status_code, 200)
        self.assertIn("attendance", response.data)
        self.assertIn("behavior", response.data)
        self.assertIn("academics", response.data)
        self.assertIn("medical", response.data)

        summary = response.data["attendance"]["summary"]
        self.assertEqual(summary["present"], 1)
        self.assertEqual(summary["absent"], 1)
        self.assertEqual(summary["late"], 0)
        self.assertEqual(summary["period_label"], "All time")
        self.assertEqual(summary["attendance_rate"], 50.0)

        self.assertEqual(len(response.data["attendance"]["records"]), 2)
        self.assertEqual(len(response.data["behavior"]), 1)
        self.assertEqual(response.data["medical"]["record"]["blood_type"], "O+")
        self.assertEqual(len(response.data["medical"]["visits"]), 1)
