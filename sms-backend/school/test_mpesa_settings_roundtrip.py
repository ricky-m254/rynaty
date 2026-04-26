"""
Round-trip persistence test for M-Pesa credentials stored via TenantSettingsView.

Covers:
  - POST /settings/  saves integrations.mpesa correctly
  - GET  /settings/  returns saved non-secret fields while masking saved secrets
  - GET  /settings/?category=integrations  filters correctly after save
  - An empty (un-configured) response when no entry has been saved
  - Partial responses (missing consumer_key / shortcode) are handled gracefully
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import AuditLog, Role, TenantSecret, TenantSettings, UserProfile
from school.tenant_secrets import SECRET_META_KEY, get_tenant_secret
from school.views import TenantSettingsView

User = get_user_model()

MPESA_CREDS = {
    "consumer_key": "ck_test_abc123",
    "consumer_secret": "cs_test_xyz789",
    "shortcode": "174379",
    "passkey": "pk_bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919",
    "environment": "sandbox",
}


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="mpesa_roundtrip_test",
                name="MPesa RoundTrip Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(
                domain="mpesa-roundtrip.localhost",
                tenant=cls.tenant,
                is_primary=True,
            )

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()
        self.factory = APIRequestFactory()
        username = f"admin_mpesa_{self._testMethodName}"
        self.user = User.objects.create_user(username=username, password="pass1234")
        role, _ = Role.objects.get_or_create(
            name="ADMIN", defaults={"description": "School Administrator"}
        )
        UserProfile.objects.get_or_create(user=self.user, defaults={"role": role})

    def tearDown(self):
        TenantSettings.objects.filter(key="integrations.mpesa").delete()
        TenantSecret.objects.all().delete()
        self.schema_ctx.__exit__(None, None, None)


class MpesaSettingsRoundTripTests(TenantTestBase):
    """Verify that M-Pesa credentials survive a POST→GET round trip."""

    def _post_settings(self, payload):
        request = self.factory.post(
            "/settings/", data=payload, format="json"
        )
        force_authenticate(request, user=self.user)
        return TenantSettingsView.as_view()(request)

    def _get_settings(self, category=None):
        url = "/settings/" if not category else f"/settings/?category={category}"
        request = self.factory.get(url)
        if category:
            request.GET = request.GET.copy()
            request.GET["category"] = category
        force_authenticate(request, user=self.user)
        return TenantSettingsView.as_view()(request)

    def test_save_and_reload_full_credentials(self):
        """POST then GET preserves non-secret values while masking saved credentials."""
        post_resp = self._post_settings(
            {"key": "integrations.mpesa", "value": MPESA_CREDS, "category": "integrations"}
        )
        self.assertEqual(post_resp.status_code, 200)
        self.assertIn("integrations.mpesa", post_resp.data.get("upserted", []))

        get_resp = self._get_settings()
        self.assertEqual(get_resp.status_code, 200)

        settings_flat = get_resp.data.get("settings", {})
        self.assertIn("integrations.mpesa", settings_flat)

        saved = settings_flat["integrations.mpesa"]
        self.assertEqual(saved["shortcode"], MPESA_CREDS["shortcode"])
        self.assertEqual(saved["environment"], MPESA_CREDS["environment"])
        self.assertNotIn("consumer_key", saved)
        self.assertNotIn("consumer_secret", saved)
        self.assertNotIn("passkey", saved)
        self.assertIn(SECRET_META_KEY, saved)
        self.assertTrue(saved[SECRET_META_KEY]["consumer_key"]["configured"])
        self.assertTrue(saved[SECRET_META_KEY]["consumer_secret"]["configured"])
        self.assertTrue(saved[SECRET_META_KEY]["passkey"]["configured"])

        stored = TenantSettings.objects.get(key="integrations.mpesa")
        self.assertNotIn("consumer_key", stored.value)
        self.assertNotIn("consumer_secret", stored.value)
        self.assertNotIn("passkey", stored.value)
        self.assertTrue(TenantSecret.objects.filter(key="tenant_setting:integrations.mpesa:consumer_key").exists())
        self.assertTrue(TenantSecret.objects.filter(key="tenant_setting:integrations.mpesa:consumer_secret").exists())
        self.assertTrue(TenantSecret.objects.filter(key="tenant_setting:integrations.mpesa:passkey").exists())
        self.assertEqual(
            get_tenant_secret("tenant_setting:integrations.mpesa:consumer_secret"),
            MPESA_CREDS["consumer_secret"],
        )

    def test_category_filter_returns_entry_after_save(self):
        """GET ?category=integrations exposes the saved key after POST."""
        self._post_settings(
            {"key": "integrations.mpesa", "value": MPESA_CREDS, "category": "integrations"}
        )
        get_resp = self._get_settings(category="integrations")
        self.assertEqual(get_resp.status_code, 200)
        self.assertIn("integrations.mpesa", get_resp.data.get("settings", {}))

    def test_get_before_any_save_returns_empty_settings(self):
        """GET returns an empty settings dict when no M-Pesa entry exists yet."""
        get_resp = self._get_settings()
        self.assertEqual(get_resp.status_code, 200)
        settings_flat = get_resp.data.get("settings", {})
        self.assertNotIn("integrations.mpesa", settings_flat)

    def test_overwrite_preserves_updated_values(self):
        """A second POST with different credentials replaces values without exposing secrets on read."""
        self._post_settings(
            {"key": "integrations.mpesa", "value": MPESA_CREDS, "category": "integrations"}
        )
        updated_creds = {**MPESA_CREDS, "shortcode": "999888", "environment": "production"}
        update_response = self._post_settings(
            {
                "key": "integrations.mpesa",
                "value": updated_creds,
                "category": "integrations",
                "production_acknowledged": True,
            }
        )
        self.assertEqual(update_response.status_code, 200)

        get_resp = self._get_settings()
        saved = get_resp.data["settings"]["integrations.mpesa"]
        self.assertEqual(saved["shortcode"], "999888")
        self.assertEqual(saved["environment"], "production")
        self.assertIn(SECRET_META_KEY, saved)
        self.assertTrue(saved[SECRET_META_KEY]["consumer_key"]["configured"])

    def test_partial_update_keeps_existing_secrets_when_secret_fields_are_omitted(self):
        """Posting only non-secret fields must preserve the stored secret rows."""
        self._post_settings(
            {"key": "integrations.mpesa", "value": MPESA_CREDS, "category": "integrations"}
        )

        update_response = self._post_settings(
            {
                "key": "integrations.mpesa",
                "value": {"shortcode": "700001", "environment": "production"},
                "category": "integrations",
                "production_acknowledged": True,
            }
        )
        self.assertEqual(update_response.status_code, 200)

        get_resp = self._get_settings()
        saved = get_resp.data["settings"]["integrations.mpesa"]
        self.assertEqual(saved["shortcode"], "700001")
        self.assertEqual(saved["environment"], "production")
        self.assertIn(SECRET_META_KEY, saved)
        self.assertTrue(saved[SECRET_META_KEY]["consumer_key"]["configured"])
        self.assertEqual(
            get_tenant_secret("tenant_setting:integrations.mpesa:consumer_key"),
            MPESA_CREDS["consumer_key"],
        )

    def test_partial_credentials_are_stored_and_retrieved(self):
        """Partial credentials (shortcode only) are stored and readable."""
        self._post_settings(
            {"key": "integrations.mpesa", "value": {"shortcode": "174379"}, "category": "integrations"}
        )
        get_resp = self._get_settings()
        saved = get_resp.data["settings"].get("integrations.mpesa", {})
        self.assertEqual(saved.get("shortcode"), "174379")
        self.assertIsNone(saved.get("consumer_key"))
        self.assertNotIn(SECRET_META_KEY, saved)

    def test_grouped_structure_also_contains_entry(self):
        """The grouped response structure exposes the entry under its category."""
        self._post_settings(
            {"key": "integrations.mpesa", "value": MPESA_CREDS, "category": "integrations"}
        )
        get_resp = self._get_settings()
        grouped = get_resp.data.get("grouped", {})
        self.assertIn("integrations", grouped)
        self.assertIn("integrations.mpesa", grouped["integrations"])
        self.assertEqual(
            grouped["integrations"]["integrations.mpesa"]["value"]["shortcode"],
            MPESA_CREDS["shortcode"],
        )
        self.assertIn(
            SECRET_META_KEY,
            grouped["integrations"]["integrations.mpesa"]["value"],
        )

    def test_masked_secret_settings_read_emits_audit_log(self):
        """Reading masked secret-backed settings must create an audit trail entry."""
        self._post_settings(
            {"key": "integrations.mpesa", "value": MPESA_CREDS, "category": "integrations"}
        )

        get_resp = self._get_settings(category="integrations")

        self.assertEqual(get_resp.status_code, 200)
        audit = AuditLog.objects.filter(action="SECRET_READ", object_id="settings").latest("timestamp")
        self.assertEqual(audit.user_id, self.user.id)
        self.assertEqual(audit.model_name, "TenantSettings")
        self.assertIn("integrations.mpesa", audit.details)
