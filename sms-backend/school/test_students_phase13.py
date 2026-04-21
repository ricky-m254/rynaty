import os
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import resolve
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import (
    AdmissionApplication,
    AdmissionDocument,
    Module,
    Role,
    Student,
    StudentDocument,
    UserModuleAssignment,
    UserProfile,
)
from school.views import AdmissionApplicationViewSet, StudentViewSet


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="students_phase13_test",
                name="Students Phase13 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(
                domain="students-phase13.localhost",
                tenant=cls.tenant,
                is_primary=True,
            )

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()
        self._file_paths: list[str] = []

    def tearDown(self):
        for file_path in self._file_paths:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        self.schema_ctx.__exit__(None, None, None)


class StudentsPhase13MediaPipelineTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        students_module, _ = Module.objects.get_or_create(
            key="STUDENTS",
            defaults={"name": "Students"},
        )
        role, _ = Role.objects.get_or_create(
            name="ADMIN",
            defaults={"description": "Admin"},
        )
        self.user, _ = User.objects.get_or_create(
            username="students_phase13_admin",
            defaults={"email": "students_phase13_admin@example.com"},
        )
        self.user.set_password("pass1234")
        self.user.save(update_fields=["password"])
        UserProfile.objects.get_or_create(user=self.user, defaults={"role": role})
        UserModuleAssignment.objects.get_or_create(
            user=self.user,
            module=students_module,
            defaults={"is_active": True},
        )

        self.student, _ = Student.objects.get_or_create(
            admission_number="S-SP13-001",
            defaults={
                "first_name": "Media",
                "last_name": "Student",
                "date_of_birth": "2012-02-02",
                "gender": "F",
                "is_active": True,
            },
        )
        self.application = AdmissionApplication.objects.create(
            student_first_name="Apply",
            student_last_name="Photo",
            student_dob=date(2013, 3, 3),
            student_gender="Male",
            application_date=date(2026, 4, 20),
            guardian_name="Parent Demo",
            guardian_phone="+254700000000",
            guardian_email="parent@example.com",
        )

    def test_student_upload_endpoints_return_absolute_media_urls(self):
        photo_request = self.factory.post(
            f"/api/students/{self.student.id}/photo/",
            {
                "photo": SimpleUploadedFile(
                    "avatar.png",
                    b"fake-image-bytes",
                    content_type="image/png",
                )
            },
            format="multipart",
        )
        force_authenticate(photo_request, user=self.user)
        photo_response = StudentViewSet.as_view({"post": "upload_photo"})(
            photo_request,
            pk=self.student.id,
        )

        self.assertEqual(photo_response.status_code, 200)
        self.assertTrue(photo_response.data["photo"].startswith("http://testserver/media/"))
        self.assertEqual(photo_response.data["photo"], photo_response.data["photo_url"])

        self.student.refresh_from_db()
        if self.student.photo:
            self._file_paths.append(self.student.photo.path)

        documents_request = self.factory.post(
            f"/api/students/{self.student.id}/documents/",
            {
                "documents": [
                    SimpleUploadedFile(
                        "report.pdf",
                        b"student-document",
                        content_type="application/pdf",
                    )
                ]
            },
            format="multipart",
        )
        force_authenticate(documents_request, user=self.user)
        documents_response = StudentViewSet.as_view({"post": "upload_documents"})(
            documents_request,
            pk=self.student.id,
        )

        self.assertEqual(documents_response.status_code, 201)
        self.assertEqual(documents_response.data["documents"][0]["name"], "report.pdf")
        self.assertTrue(
            documents_response.data["documents"][0]["url"].startswith("http://testserver/media/")
        )

        created_document = StudentDocument.objects.order_by("-id").first()
        self.assertIsNotNone(created_document)
        if created_document and created_document.file:
            self._file_paths.append(created_document.file.path)

    def test_admission_retrieve_returns_absolute_photo_and_document_urls(self):
        self.application.student_photo = SimpleUploadedFile(
            "application-photo.png",
            b"fake-application-image",
            content_type="image/png",
        )
        self.application.save(update_fields=["student_photo"])
        if self.application.student_photo:
            self._file_paths.append(self.application.student_photo.path)

        admission_document = AdmissionDocument.objects.create(
            application=self.application,
            file=SimpleUploadedFile(
                "application-form.pdf",
                b"application-document",
                content_type="application/pdf",
            ),
        )
        self._file_paths.append(admission_document.file.path)

        request = self.factory.get(f"/api/admissions/applications/{self.application.id}/")
        force_authenticate(request, user=self.user)
        response = AdmissionApplicationViewSet.as_view({"get": "retrieve"})(
            request,
            pk=self.application.id,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["student_photo"].startswith("http://testserver/media/"))
        self.assertEqual(response.data["uploaded_documents"][0]["name"], "application-form.pdf")
        self.assertTrue(
            response.data["uploaded_documents"][0]["url"].startswith("http://testserver/media/")
        )

    def test_media_files_are_served_for_local_storage_urls(self):
        document = StudentDocument.objects.create(
            student=self.student,
            file=SimpleUploadedFile(
                "servable.pdf",
                b"servable-document",
                content_type="application/pdf",
            ),
        )
        self._file_paths.append(document.file.path)

        request = RequestFactory().get(document.file.url)
        match = resolve(document.file.url)
        response = match.func(request, **match.kwargs)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"servable-document")
