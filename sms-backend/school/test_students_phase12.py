from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
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
                schema_name="students_phase12_test",
                name="Students Phase12 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="students-phase12.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class StudentsPhase12DocumentsListTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        students_module = Module.objects.create(key="STUDENTS", name="Students")
        role = Role.objects.create(name="ADMIN", description="Admin")
        self.user = User.objects.create_user(username="students_phase12_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=role)
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

        student = Student.objects.create(
            admission_number="S-SP12-001",
            first_name="Doc",
            last_name="Timeline",
            date_of_birth=date(2013, 7, 1),
            gender="F",
            is_active=True,
        )

        self.new_doc = StudentDocument.objects.create(
            student=student,
            file=SimpleUploadedFile("recent.pdf", b"recent-content", content_type="application/pdf"),
        )
        self.old_doc = StudentDocument.objects.create(
            student=student,
            file=SimpleUploadedFile("old.pdf", b"old-content", content_type="application/pdf"),
        )
        StudentDocument.objects.filter(id=self.new_doc.id).update(
            uploaded_at=timezone.make_aware(datetime(2026, 2, 14, 10, 0, 0))
        )
        StudentDocument.objects.filter(id=self.old_doc.id).update(
            uploaded_at=timezone.make_aware(datetime(2026, 1, 10, 10, 0, 0))
        )

    def test_documents_action_supports_date_filter_and_pagination(self):
        request = self.factory.get("/api/students/documents/?date_from=2026-02-01&page=1&page_size=1")
        force_authenticate(request, user=self.user)
        response = StudentViewSet.as_view({"get": "documents"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["file_name"], "recent.pdf")
