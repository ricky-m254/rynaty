import hashlib
import hmac
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Tenant, Domain
from school.models import (
    Role,
    UserProfile,
    Module,
    UserModuleAssignment,
    Student,
    Payment,
    BankStatementLine,
)
from school.views import FinanceGatewayWebhookView, BankStatementLineViewSet


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="finance_phase4_test",
                name="Finance Phase4 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="finance-phase4.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class FinancePhase4WebhookAndReconciliationTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        self.user = User.objects.create_user(username="finance_user", password="pass1234")
        role = Role.objects.create(name="ACCOUNTANT", description="Finance")
        UserProfile.objects.create(user=self.user, role=role)
        finance_module = Module.objects.create(key="FINANCE", name="Finance")
        UserModuleAssignment.objects.create(user=self.user, module=finance_module, is_active=True)

        self.student = Student.objects.create(
            admission_number="S-P4-001",
            first_name="Amina",
            last_name="Otieno",
            date_of_birth="2012-01-10",
            gender="F",
            is_active=True,
        )

    @override_settings(FINANCE_WEBHOOK_TOKEN="token-123", FINANCE_WEBHOOK_SHARED_SECRET="")
    def test_gateway_webhook_rejects_invalid_token(self):
        payload = {"event_id": "evt-1", "event_type": "payment.succeeded"}
        request = self.factory.post(
            "/api/finance/gateway/webhooks/mpesa/",
            payload,
            format="json",
            HTTP_X_WEBHOOK_TOKEN="bad-token",
        )
        response = FinanceGatewayWebhookView.as_view()(request, provider="mpesa")
        self.assertEqual(response.status_code, 401)

    @override_settings(FINANCE_WEBHOOK_TOKEN="token-abc", FINANCE_WEBHOOK_SHARED_SECRET="secret-xyz")
    def test_gateway_webhook_accepts_valid_token_and_signature(self):
        body = {
            "event_id": "evt-2",
            "event_type": "payment.succeeded",
            "external_id": "tx-2002",
            "status": "SUCCEEDED",
            "amount": "1500.00",
            "student_id": self.student.id,
        }
        raw = json.dumps(body).encode("utf-8")
        signature = hmac.new(b"secret-xyz", raw, hashlib.sha256).hexdigest()
        request = self.factory.post(
            "/api/finance/gateway/webhooks/mpesa/",
            raw,
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="token-abc",
            HTTP_X_WEBHOOK_SIGNATURE=f"sha256={signature}",
        )
        response = FinanceGatewayWebhookView.as_view()(request, provider="mpesa")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["processed"], True)

    @override_settings(
        FINANCE_WEBHOOK_TOKEN="",
        FINANCE_WEBHOOK_SHARED_SECRET="",
        FINANCE_WEBHOOK_STRICT_MODE=True,
    )
    def test_gateway_webhook_rejects_unconfigured_verification_in_strict_mode(self):
        payload = {"event_id": "evt-3", "event_type": "payment.succeeded"}
        request = self.factory.post(
            "/api/finance/gateway/webhooks/mpesa/",
            payload,
            format="json",
        )
        response = FinanceGatewayWebhookView.as_view()(request, provider="mpesa")
        self.assertEqual(response.status_code, 401)

    @override_settings(
        FINANCE_WEBHOOK_TOKEN="",
        FINANCE_WEBHOOK_SHARED_SECRET="",
        FINANCE_WEBHOOK_STRICT_MODE=False,
    )
    def test_gateway_webhook_allows_unconfigured_verification_in_non_strict_mode(self):
        payload = {"event_id": "evt-4", "event_type": "payment.succeeded"}
        request = self.factory.post(
            "/api/finance/gateway/webhooks/mpesa/",
            payload,
            format="json",
        )
        response = FinanceGatewayWebhookView.as_view()(request, provider="mpesa")
        self.assertEqual(response.status_code, 201)

    def test_bank_line_auto_match_uses_payment_reference(self):
        payment = Payment.objects.create(
            student=self.student,
            amount="500.00",
            payment_method="Bank Transfer",
            reference_number="BANK-REF-9001",
            notes="test payment",
        )
        line = BankStatementLine.objects.create(
            statement_date="2026-02-14",
            amount="500.00",
            reference="BANK-REF-9001",
            source="manual",
            status="UNMATCHED",
        )

        request = self.factory.post(f"/api/finance/reconciliation/bank-lines/{line.id}/auto-match/")
        force_authenticate(request, user=self.user)
        response = BankStatementLineViewSet.as_view({"post": "auto_match"})(request, pk=line.id)
        self.assertEqual(response.status_code, 200)
        line.refresh_from_db()
        self.assertEqual(line.status, "MATCHED")
        self.assertEqual(line.matched_payment_id, payment.id)
