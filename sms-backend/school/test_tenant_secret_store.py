from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, SchoolProfile, TenantSecret, TenantSettings, UserModuleAssignment, UserProfile
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
