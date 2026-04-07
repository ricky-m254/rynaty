from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, Student, StudentDocument, UserModuleAssignment, UserProfile
from school.views import StudentViewSet


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="students_phase1_test",
                name="Students Phase1 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="students-phase1.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class StudentsPhase1DocumentsEndpointTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        students_module = Module.objects.create(key="STUDENTS", name="Students")
        role = Role.objects.create(name="ADMIN", description="Admin")
        self.user = User.objects.create_user(username="students_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=role)
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

        self.student = Student.objects.create(
            admission_number="S-SP1-001",
            first_name="Jane",
            last_name="Mwangi",
            date_of_birth="2012-01-01",
            gender="F",
            is_active=True,
        )
        StudentDocument.objects.create(
            student=self.student,
            file=SimpleUploadedFile("birth_cert.pdf", b"dummy-content", content_type="application/pdf"),
        )

    def test_students_documents_list_returns_rows(self):
        request = self.factory.get("/api/students/documents/")
        force_authenticate(request, user=self.user)
        response = StudentViewSet.as_view({"get": "documents"})(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["student_id"], self.student.id)
        self.assertEqual(row["admission_number"], self.student.admission_number)

