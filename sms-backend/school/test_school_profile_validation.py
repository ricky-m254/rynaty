from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, SchoolProfile, UserModuleAssignment, UserProfile
from school.views import FinanceSettingsView, SchoolProfileView


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="school_profile_validation",
                name="School Profile Validation Test",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="school-profile-validation.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

        self.factory = APIRequestFactory()
        admin_role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "School Administrator"})
        students_module, _ = Module.objects.get_or_create(key="STUDENTS", defaults={"name": "Students"})
        self.user = User.objects.create_user(username="school_profile_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=admin_role)
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)

    def _auth(self, request):
        request.tenant = self.tenant
        force_authenticate(request, user=self.user)
        return request


class SchoolProfileValidationTests(TenantTestBase):
    def test_model_full_clean_rejects_invalid_sender_id(self):
        profile = SchoolProfile(
            school_name="Validation School",
            sms_sender_id="BAD-SENDER",
            is_active=True,
        )

        with self.assertRaises(ValidationError) as exc:
            profile.full_clean()

        self.assertIn("sms_sender_id", exc.exception.message_dict)

    def test_school_profile_patch_rejects_invalid_sensitive_fields(self):
        SchoolProfile.objects.create(
            school_name="Validation School",
            receipt_prefix="RCT-",
            sms_sender_id="SCHOOL",
            is_active=True,
        )

        request = self._auth(
            self.factory.patch(
                "/api/school/profile/",
                {
                    "receipt_prefix": "rct!",
                    "sms_sender_id": "BAD-SENDER",
                },
                format="json",
            )
        )

        response = SchoolProfileView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        details = response.data["error"]["details"]
        self.assertIn("receipt_prefix", details)
        self.assertIn("sms_sender_id", details)

    def test_finance_settings_patch_rejects_invalid_ranges_and_prefix(self):
        SchoolProfile.objects.create(
            school_name="Validation School",
            receipt_prefix="RCT-",
            invoice_prefix="INV-",
            tax_percentage="10.00",
            is_active=True,
        )

        request = self._auth(
            self.factory.patch(
                "/api/settings/finance/",
                {
                    "tax_percentage": "150.00",
                    "receipt_prefix": "bad prefix",
                    "late_fee_value": "-1.00",
                },
                format="json",
            )
        )

        response = FinanceSettingsView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        details = response.data["error"]["details"]
        self.assertIn("tax_percentage", details)
        self.assertIn("receipt_prefix", details)
        self.assertIn("late_fee_value", details)

    def test_finance_settings_patch_accepts_valid_payload(self):
        SchoolProfile.objects.create(
            school_name="Validation School",
            receipt_prefix="RCT-",
            invoice_prefix="INV-",
            tax_percentage="10.00",
            late_fee_value="0.00",
            accepted_payment_methods=["Cash"],
            is_active=True,
        )

        request = self._auth(
            self.factory.patch(
                "/api/settings/finance/",
                {
                    "tax_percentage": "16.00",
                    "receipt_prefix": "RCT-2026",
                    "late_fee_value": "250.00",
                    "accepted_payment_methods": ["Cash", "Bank Transfer", "M-Pesa"],
                },
                format="json",
            )
        )

        response = FinanceSettingsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["tax_percentage"], "16.00")
        self.assertEqual(response.data["receipt_prefix"], "RCT-2026")
        self.assertEqual(response.data["accepted_payment_methods"], ["Cash", "Bank Transfer", "M-Pesa"])
