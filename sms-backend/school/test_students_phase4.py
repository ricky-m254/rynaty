from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import BehaviorIncident, Module, Role, Student, UserModuleAssignment, UserProfile
from school.views import BehaviorIncidentsCsvExportView


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="students_phase4_test",
                name="Students Phase4 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="students-phase4.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class StudentsPhase4BehaviorExportTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        students_module = Module.objects.create(key="STUDENTS", name="Students")
        role = Role.objects.create(name="ADMIN", description="Admin")
        self.user = User.objects.create_user(username="students_phase4_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=role)
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

        student = Student.objects.create(
            admission_number="S-SP4-001",
            first_name="Phase",
            last_name="Four",
            date_of_birth="2012-01-01",
            gender="M",
            is_active=True,
        )
        BehaviorIncident.objects.create(
            student=student,
            incident_type="Negative",
            category="Discipline",
            incident_date="2026-02-14",
            severity="Low",
            description="Late to class",
        )
        BehaviorIncident.objects.create(
            student=student,
            incident_type="Negative",
            category="Discipline",
            incident_date="2026-02-15",
            severity="High",
            description="Class disruption",
        )

    def test_behavior_csv_export_respects_filters(self):
        request = self.factory.get("/api/behavior/incidents/export/csv/?severity=High")
        force_authenticate(request, user=self.user)
        response = BehaviorIncidentsCsvExportView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode("utf-8")
        self.assertIn("behavior_incidents_report.csv", response["Content-Disposition"])
        self.assertIn("Class disruption", content)
        self.assertNotIn("Late to class", content)
