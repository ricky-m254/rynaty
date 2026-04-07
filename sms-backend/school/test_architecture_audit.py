import re
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory

from clients.middleware import TenantHeaderMiddleware
from clients.models import Domain, Tenant


class TenantResolutionAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="audit_tenant_resolution",
                name="Audit Tenant",
                paid_until="2030-01-01",
            )
            Domain.objects.create(
                domain="audit-tenant.localhost",
                tenant=cls.tenant,
                is_primary=True,
            )

    def test_tenant_resolution_paths_are_explicitly_configured(self):
        self.assertEqual(settings.PUBLIC_SCHEMA_URLCONF, "config.public_urls")
        self.assertIn("X-Tenant-ID", settings.TENANT_HEADERS)
        self.assertIn("django_tenants.middleware.main.TenantMainMiddleware", settings.MIDDLEWARE)
        tenant_mw_idx = settings.MIDDLEWARE.index("django_tenants.middleware.main.TenantMainMiddleware")
        auth_mw_idx = settings.MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware")
        self.assertLess(tenant_mw_idx, auth_mw_idx)

    def test_header_tenant_resolution_delegates_to_tenant_middleware(self):
        factory = APIRequestFactory()
        request = factory.get("/api/finance/summary/", HTTP_X_TENANT_ID=self.tenant.schema_name)
        middleware = TenantHeaderMiddleware(lambda _request: None)
        with patch.object(TenantMainMiddleware, "process_request", return_value=None) as parent_process:
            middleware.process_request(request)
        self.assertEqual(request.tenant.schema_name, self.tenant.schema_name)
        parent_process.assert_called_once()


class CrossModuleBoundaryAuditTests(TestCase):
    def test_critical_modules_do_not_directly_write_foreign_module_data(self):
        base = Path(__file__).resolve().parents[1]
        targets = {
            "admissions/views.py": base / "admissions" / "views.py",
            "academics/views.py": base / "academics" / "views.py",
        }
        forbidden = re.compile(
            r"\b(?:Invoice|Payment|FeeStructure|Expense|Budget|Message|CommunicationMessage)\.objects\."
            r"(?:create|bulk_create|update|update_or_create|get_or_create|delete)\b"
        )

        violations = []
        for label, path in targets.items():
            text = path.read_text(encoding="utf-8")
            for idx, line in enumerate(text.splitlines(), start=1):
                if forbidden.search(line):
                    violations.append(f"{label}:{idx}:{line.strip()}")

        self.assertEqual(violations, [], f"Cross-module direct write violations found: {violations}")

