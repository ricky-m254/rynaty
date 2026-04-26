import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django_tenants.utils import schema_context

from clients.models import Domain, Tenant
from school.models import AuditLog, TenantSecret
from school.tenant_secrets import (
    current_secret_key_version,
    get_tenant_secret,
    reset_secret_keyring_cache,
    set_tenant_secret,
)


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="tenant_secret_rotation_test",
                name="Tenant Secret Rotation Test",
                paid_until="2030-01-01",
            )
            Domain.objects.create(
                domain="tenant-secret-rotation.localhost",
                tenant=cls.tenant,
                is_primary=True,
            )

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()
        self.user = User.objects.create_user(
            username=f"tenant_secret_rotation_{self._testMethodName}",
            password="pass1234",
        )

    def tearDown(self):
        TenantSecret.objects.all().delete()
        self.schema_ctx.__exit__(None, None, None)
        reset_secret_keyring_cache()

    def _seed_old_secret(self, key, value):
        with override_settings(DJANGO_TENANT_SECRET_KEYS=["legacy-secret-key"]):
            reset_secret_keyring_cache()
            set_tenant_secret(key, value, updated_by=self.user, description="legacy test secret")
            secret = TenantSecret.objects.get(key=key)
            old_version = secret.key_version
        reset_secret_keyring_cache()
        return old_version


class TenantSecretRotationCommandTests(TenantTestBase):
    def test_rotate_tenant_secrets_reencrypts_to_current_primary_key(self):
        secret_key = "tenant_setting:integrations.mpesa:consumer_key"
        old_version = self._seed_old_secret(secret_key, "ck_legacy_demo")

        with override_settings(DJANGO_TENANT_SECRET_KEYS=["new-primary-secret", "legacy-secret-key"]):
            reset_secret_keyring_cache()
            stdout = io.StringIO()
            call_command("rotate_tenant_secrets", "--actor-username", self.user.username, stdout=stdout)

            secret = TenantSecret.objects.get(key=secret_key)
            self.assertNotEqual(secret.key_version, old_version)
            self.assertEqual(secret.key_version, current_secret_key_version())
            self.assertEqual(get_tenant_secret(secret_key), "ck_legacy_demo")
            self.assertIn("rotated=1", stdout.getvalue())
            audit = AuditLog.objects.filter(action="SECRET_ROTATE", object_id="all").latest("timestamp")
            self.assertEqual(audit.user_id, self.user.id)
            self.assertIn("rotated=1", audit.details)

    def test_rotate_tenant_secrets_dry_run_reports_without_rewriting(self):
        secret_key = "school_profile:smtp_password"
        old_version = self._seed_old_secret(secret_key, "smtp-legacy-password")

        with override_settings(DJANGO_TENANT_SECRET_KEYS=["new-primary-secret", "legacy-secret-key"]):
            reset_secret_keyring_cache()
            stdout = io.StringIO()
            call_command("rotate_tenant_secrets", "--dry-run", stdout=stdout)

            secret = TenantSecret.objects.get(key=secret_key)
            self.assertEqual(secret.key_version, old_version)
            self.assertEqual(get_tenant_secret(secret_key), "smtp-legacy-password")
            self.assertIn("would rotate", stdout.getvalue())
            self.assertIn("rotated=1", stdout.getvalue())
            audit = AuditLog.objects.filter(action="SECRET_ROTATE_PREVIEW", object_id="all").latest("timestamp")
            self.assertIn("dry_run", audit.details)
