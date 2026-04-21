from django.test import TestCase
from django_tenants.utils import schema_context

from clients.models import Domain, Tenant
from clockin.models import BiometricDevice, SmartPSSSource
from clockin.serializers import BiometricDeviceSerializer, SmartPSSSourceSerializer
from clockin.smartpss_client import SmartPSSLiteClient


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="clockin_ipv6_support",
                name="Clockin IPv6 Support School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="clockin-ipv6.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class ClockInIpv6SupportTests(TenantTestBase):
    def test_biometric_device_serializer_infers_ipv6(self):
        serializer = BiometricDeviceSerializer(
            data={
                "device_id": "GATE-IPV6",
                "name": "Gate IPv6",
                "location": "North Gate",
                "device_type": "BOTH",
                "ip_address": "2001:db8::10",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["ip_version"], "ipv6")

    def test_smartpss_serializer_brackets_ipv6_api_urls(self):
        source = SmartPSSSource.objects.create(
            name="Main Office SmartPSS",
            host="2001:db8::20",
            ip_version="ipv6",
            port=8443,
            username="admin",
            password="secret",
            use_https=True,
        )
        data = SmartPSSSourceSerializer(source).data
        self.assertEqual(data["api_url"], "https://[2001:db8::20]:8443/evo-apigw")

    def test_smartpss_client_uses_ipv6_safe_base_url(self):
        client = SmartPSSLiteClient(
            host="2001:db8::30",
            port=8443,
            username="admin",
            password="secret",
            use_https=False,
        )
        self.assertEqual(client.base, "http://[2001:db8::30]:8443/evo-apigw")
