from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import ClinicVisit, Module, Role, Student, UserModuleAssignment, UserProfile
from school.views import ClinicVisitViewSet


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="students_phase11_test",
                name="Students Phase11 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="students-phase11.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class StudentsPhase11MedicalListFilterTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        students_module = Module.objects.create(key="STUDENTS", name="Students")
        role = Role.objects.create(name="ADMIN", description="Admin")
        self.user = User.objects.create_user(username="students_phase11_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=role)
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

        self.student = Student.objects.create(
            admission_number="S-SP11-001",
            first_name="Filter",
            last_name="Case",
            date_of_birth=date(2013, 6, 1),
            gender="M",
            is_active=True,
        )
        ClinicVisit.objects.create(
            student=self.student,
            visit_date=date(2026, 2, 10),
            complaint="Headache",
            treatment="Rest",
            severity="Minor",
            parent_notified=True,
            attended_by=self.user,
        )
        ClinicVisit.objects.create(
            student=self.student,
            visit_date=date(2026, 1, 5),
            complaint="High fever",
            treatment="Medication",
            severity="Serious",
            parent_notified=False,
            attended_by=self.user,
        )

    def test_clinic_visit_list_supports_date_and_severity_filters(self):
        request = self.factory.get("/api/medical/visits/?date_from=2026-02-01&severity=Minor")
        force_authenticate(request, user=self.user)
        response = ClinicVisitViewSet.as_view({"get": "list"})(request)

        self.assertEqual(response.status_code, 200)
        payload = response.data
        rows = payload.get("results", payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["complaint"], "Headache")
