from unittest.mock import patch

from cryptography.fernet import InvalidToken
from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, SchoolProfile, TenantSecret, TenantSettings, UserModuleAssignment, UserProfile
from school.mpesa import MpesaError, _get_credentials
from school.tenant_secrets import get_tenant_secret, sanitize_tenant_setting_value_for_storage, set_tenant_secret
from school.views import SchoolProfileView, TenantSettingDeleteView, TenantSettingsView


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="tenant_secret_store_test",
                name="Tenant Secret Store Test",
                paid_until="2030-01-01",
            )
            Domain.objects.create(
                domain="tenant-secret-store.localhost",
                tenant=cls.tenant,
                is_primary=True,
            )

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username=f"tenant_secret_admin_{self._testMethodName}", password="pass1234")
        admin_role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "School Administrator"})
        students_module, _ = Module.objects.get_or_create(key="STUDENTS", defaults={"name": "Students"})
        UserProfile.objects.get_or_create(user=self.user, defaults={"role": admin_role})
        UserModuleAssignment.objects.get_or_create(user=self.user, module=students_module, defaults={"is_active": True})

    def tearDown(self):
        TenantSecret.objects.all().delete()
        TenantSettings.objects.all().delete()
        self.schema_ctx.__exit__(None, None, None)


class TenantSecretStoreTests(TenantTestBase):
    def _auth(self, request):
        request.tenant = self.tenant
        force_authenticate(request, user=self.user)
        return request

    def test_school_profile_patch_moves_secret_fields_out_of_plain_columns(self):
        profile = SchoolProfile.objects.create(
            school_name="Secret School",
            smtp_host="smtp.example.com",
            smtp_user="alerts@example.com",
            is_active=True,
        )

        request = self._auth(
            self.factory.patch(
                "/api/school/profile/",
                {
                    "smtp_password": "smtp-secret-123",
                    "sms_api_key": "sms-secret-456",
                    "whatsapp_api_key": "wa-secret-789",
                },
                format="json",
            )
        )

        response = SchoolProfileView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.smtp_password, "")
        self.assertEqual(profile.sms_api_key, "")
        self.assertEqual(profile.whatsapp_api_key, "")
        smtp_secret = TenantSecret.objects.get(key="school_profile:smtp_password")
        sms_secret = TenantSecret.objects.get(key="school_profile:sms_api_key")
        whatsapp_secret = TenantSecret.objects.get(key="school_profile:whatsapp_api_key")
        self.assertEqual(smtp_secret.updated_by_id, self.user.id)
        self.assertEqual(sms_secret.updated_by_id, self.user.id)
        self.assertEqual(whatsapp_secret.updated_by_id, self.user.id)

    def test_deleting_tenant_setting_removes_secret_rows(self):
        request = self._auth(
            self.factory.post(
                "/settings/",
                {
                    "key": "integrations.stripe",
                    "value": {
                        "enabled": True,
                        "publishable_key": "pk_test_demo",
                        "secret_key": "sk_test_demo",
                        "webhook_secret": "whsec_demo",
                    },
                    "category": "integrations",
                },
                format="json",
            )
        )
        response = TenantSettingsView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        stripe_secret = TenantSecret.objects.get(key="tenant_setting:integrations.stripe:secret_key")
        webhook_secret = TenantSecret.objects.get(key="tenant_setting:integrations.stripe:webhook_secret")
        self.assertEqual(stripe_secret.updated_by_id, self.user.id)
        self.assertEqual(webhook_secret.updated_by_id, self.user.id)

        delete_request = self._auth(self.factory.delete("/settings/integrations.stripe/"))
        delete_response = TenantSettingDeleteView.as_view()(delete_request, setting_key="integrations.stripe")

        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(TenantSecret.objects.filter(key__startswith="tenant_setting:integrations.stripe:").exists())

    def test_sanitize_tenant_setting_keeps_inline_secrets_when_secret_store_write_fails(self):
        payload = {
            "consumer_key": "ck_demo",
            "consumer_secret": "cs_demo",
            "shortcode": "174379",
            "passkey": "pk_demo",
            "environment": "sandbox",
        }

        with patch("school.tenant_secrets.set_tenant_secret", side_effect=DatabaseError("tenant secret table unavailable")):
            sanitized = sanitize_tenant_setting_value_for_storage("integrations.mpesa", payload, updated_by=self.user)

        self.assertEqual(sanitized["consumer_key"], "ck_demo")
        self.assertEqual(sanitized["consumer_secret"], "cs_demo")
        self.assertEqual(sanitized["passkey"], "pk_demo")
        self.assertEqual(sanitized["shortcode"], "174379")
        self.assertEqual(sanitized["environment"], "sandbox")

    def test_get_tenant_secret_returns_default_when_decryption_fails(self):
        set_tenant_secret(
            "tenant_setting:integrations.mpesa:consumer_key",
            "ck_live_demo",
            updated_by=self.user,
            description="mpesa consumer key",
        )

        with patch("school.tenant_secrets.decrypt_secret", side_effect=InvalidToken()):
            value = get_tenant_secret(
                "tenant_setting:integrations.mpesa:consumer_key",
                default="fallback",
            )

        self.assertEqual(value, "fallback")

    def test_mpesa_credentials_report_keyring_error_when_secret_rows_exist_but_are_unreadable(self):
        TenantSettings.objects.create(
            key="integrations.mpesa",
            value={"shortcode": "174379", "environment": "production"},
            category="integrations",
        )
        set_tenant_secret(
            "tenant_setting:integrations.mpesa:consumer_key",
            "ck_prod_demo",
            updated_by=self.user,
            description="mpesa consumer key",
        )
        set_tenant_secret(
            "tenant_setting:integrations.mpesa:consumer_secret",
            "cs_prod_demo",
            updated_by=self.user,
            description="mpesa consumer secret",
        )
        set_tenant_secret(
            "tenant_setting:integrations.mpesa:passkey",
            "pk_prod_demo",
            updated_by=self.user,
            description="mpesa passkey",
        )

        with patch("school.tenant_secrets.decrypt_secret", side_effect=InvalidToken()):
            with self.assertRaises(MpesaError) as exc:
                _get_credentials()

        self.assertIn("could not be decrypted", str(exc.exception))
        self.assertIn("DJANGO_TENANT_SECRET_KEYS", str(exc.exception))
