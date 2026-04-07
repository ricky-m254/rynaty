from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, Student, StudentDocument, UserModuleAssignment, UserProfile
from school.views import StudentsDocumentsCsvExportView


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="students_phase10_test",
                name="Students Phase10 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="students-phase10.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class StudentsPhase10DocumentsExportTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        students_module = Module.objects.create(key="STUDENTS", name="Students")
        role = Role.objects.create(name="ADMIN", description="Admin")
        self.user = User.objects.create_user(username="students_phase10_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=role)
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

        self.student_a = Student.objects.create(
            admission_number="S-SP10-001",
            first_name="Doc",
            last_name="Alpha",
            date_of_birth=date(2013, 3, 1),
            gender="M",
            is_active=True,
        )
        self.student_b = Student.objects.create(
            admission_number="S-SP10-002",
            first_name="Doc",
            last_name="Beta",
            date_of_birth=date(2013, 4, 1),
            gender="F",
            is_active=True,
        )

        StudentDocument.objects.create(
            student=self.student_a,
            file=SimpleUploadedFile("alpha_report.pdf", b"alpha-content", content_type="application/pdf"),
        )
        StudentDocument.objects.create(
            student=self.student_b,
            file=SimpleUploadedFile("beta_id.pdf", b"beta-content", content_type="application/pdf"),
        )

    def test_documents_csv_export_respects_search_and_student_filter(self):
        request = self.factory.get(
            f"/api/students/documents/export/csv/?student={self.student_b.id}&search=beta"
        )
        force_authenticate(request, user=self.user)
        response = StudentsDocumentsCsvExportView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("students_documents_report.csv", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("beta_id.pdf", content)
        self.assertNotIn("alpha_report.pdf", content)
