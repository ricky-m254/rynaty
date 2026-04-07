from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, Student, UserModuleAssignment, UserProfile
from school.views import StudentsDirectoryCsvExportView


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="students_phase8_test",
                name="Students Phase8 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="students-phase8.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class StudentsPhase8DirectoryExportTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        students_module = Module.objects.create(key="STUDENTS", name="Students")
        role = Role.objects.create(name="ADMIN", description="Admin")
        self.user = User.objects.create_user(username="students_phase8_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=role)
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

        Student.objects.create(
            admission_number="S-SP8-001",
            first_name="Alice",
            last_name="Phase",
            date_of_birth=date(2012, 1, 1),
            gender="Female",
            is_active=True,
        )
        Student.objects.create(
            admission_number="S-SP8-002",
            first_name="Bob",
            last_name="Dormant",
            date_of_birth=date(2011, 5, 8),
            gender="Male",
            is_active=False,
        )

    def test_directory_csv_export_respects_filters(self):
        request = self.factory.get("/api/students/export/csv/?is_active=false&search=Bob")
        force_authenticate(request, user=self.user)
        response = StudentsDirectoryCsvExportView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode("utf-8")
        self.assertIn("students_directory.csv", response["Content-Disposition"])
        self.assertIn("S-SP8-002", content)
        self.assertNotIn("S-SP8-001", content)
