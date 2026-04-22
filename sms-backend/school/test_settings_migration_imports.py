from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import AcademicYear, GradeLevel, Payment, Role, Student, Term, UserProfile
from school.views import FeesBulkImportView, MediaUploadView, PaymentsBulkImportView


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="settings_migration_imports",
                name="Settings Migration Imports School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="migration-imports.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class SettingsMigrationImportTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        admin_role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "Admin"})
        self.user = User.objects.create_user(username="migration_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=admin_role)

    def test_media_upload_supports_multi_file_migration_intake(self):
        file_one = SimpleUploadedFile("students.csv", b"first_name,last_name\nJane,Doe\n", content_type="text/csv")
        file_two = SimpleUploadedFile("documents.zip", b"PK\x03\x04", content_type="application/zip")
        request = self.factory.post(
            "/api/settings/media/upload/",
            {
                "module": "LIBRARY",
                "source_system": "Legacy ERP",
                "migration_batch": "batch-001",
                "files": [file_one, file_two],
            },
            format="multipart",
        )
        force_authenticate(request, user=self.user)
        response = MediaUploadView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual({row["file_type"] for row in response.data["results"]}, {"spreadsheet", "archive"})
        self.assertTrue(all(row["module"] == "LIBRARY" for row in response.data["results"]))

    def test_fee_import_validates_and_commits_fee_structures(self):
        year = AcademicYear.objects.create(name="2026-2027", start_date="2026-01-01", end_date="2026-12-31")
        Term.objects.create(academic_year=year, name="Term 1", start_date="2026-01-01", end_date="2026-04-30")
        GradeLevel.objects.create(name="Grade 4", order=4, is_active=True)

        validate_upload = SimpleUploadedFile(
            "fees.csv",
            (
                "name,category,amount,academic_year,term,grade_level,billing_cycle,is_mandatory,description\n"
                "Tuition Term 1,Tuition,15000.00,2026-2027,Term 1,Grade 4,TERMLY,true,Migrated fee\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )
        validate_request = self.factory.post(
            "/api/settings/import/fees/",
            {"file": validate_upload, "validate_only": "true"},
            format="multipart",
        )
        force_authenticate(validate_request, user=self.user)
        validate_response = FeesBulkImportView.as_view()(validate_request)

        self.assertEqual(validate_response.status_code, 200)
        self.assertEqual(validate_response.data["valid_rows"], 1)
        self.assertFalse(validate_response.data["committed"])

        commit_upload = SimpleUploadedFile(
            "fees.csv",
            (
                "name,category,amount,academic_year,term,grade_level,billing_cycle,is_mandatory,description\n"
                "Tuition Term 1,Tuition,15000.00,2026-2027,Term 1,Grade 4,TERMLY,true,Migrated fee\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )
        commit_request = self.factory.post(
            "/api/settings/import/fees/",
            {"file": commit_upload},
            format="multipart",
        )
        force_authenticate(commit_request, user=self.user)
        commit_response = FeesBulkImportView.as_view()(commit_request)

        self.assertEqual(commit_response.status_code, 201)
        self.assertEqual(commit_response.data["created"], 1)

    @patch("school.views.FinanceService.record_payment")
    def test_payment_import_commits_migrated_payment_history(self, record_payment):
        student = Student.objects.create(
            admission_number="ADM-1001",
            first_name="Jane",
            last_name="Doe",
            gender="F",
            date_of_birth="2014-01-01",
        )

        def _create_payment(**kwargs):
            return Payment.objects.create(
                student=kwargs["student"],
                amount=kwargs["amount"],
                payment_method=kwargs["payment_method"],
                reference_number=kwargs["reference_number"],
                notes=kwargs.get("notes", ""),
            )

        record_payment.side_effect = _create_payment

        upload = SimpleUploadedFile(
            "payments.csv",
            (
                "admission_number,amount,payment_date,reference,payment_method,notes\n"
                "ADM-1001,5000.00,2026-01-15 09:30:00,BANK-REF-001,Bank Transfer,Imported opening balance\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )
        request = self.factory.post(
            "/api/settings/import/payments/",
            {"file": upload},
            format="multipart",
        )
        force_authenticate(request, user=self.user)
        response = PaymentsBulkImportView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["created"], 1)
        payment = Payment.objects.get(reference_number="BANK-REF-001")
        self.assertEqual(payment.student_id, student.id)
        self.assertEqual(payment.payment_date.strftime("%Y-%m-%d %H:%M:%S"), "2026-01-15 09:30:00")


class JwtSettingsTests(SimpleTestCase):
    def test_signing_key_is_length_safe(self):
        signing_key = settings.SIMPLE_JWT["SIGNING_KEY"]

        self.assertGreaterEqual(len(signing_key.encode("utf-8")), 32)
