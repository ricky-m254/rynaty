import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Tenant, Domain
from clients.models import RevenueLog
from school.models import (
    Role,
    UserProfile,
    Module,
    UserModuleAssignment,
    Student,
    Payment,
    BankStatementLine,
    TenantSettings,
    PaymentGatewayTransaction,
    PaymentGatewayWebhookEvent,
)
from school.views import (
    BankStatementLineViewSet,
    FinanceLaunchReadinessView,
    FinanceGatewayWebhookView,
    MpesaStkCallbackView,
    MpesaStkStatusView,
    PaymentGatewayWebhookEventViewSet,
    StripeCheckoutSessionView,
    StripeTestConnectionView,
)


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

        self.user, _ = User.objects.get_or_create(username="finance_user", defaults={"email": "finance@example.com"})
        self.user.set_password("pass1234")
        self.user.save(update_fields=["password"])
        role, _ = Role.objects.get_or_create(name="ACCOUNTANT", defaults={"description": "Finance"})
        UserProfile.objects.update_or_create(user=self.user, defaults={"role": role})
        finance_module, _ = Module.objects.get_or_create(key="FINANCE", defaults={"name": "Finance"})
        UserModuleAssignment.objects.update_or_create(
            user=self.user,
            module=finance_module,
            defaults={"is_active": True},
        )

        self.student, _ = Student.objects.update_or_create(
            admission_number="S-P4-001",
            defaults={
                "first_name": "Amina",
                "last_name": "Otieno",
                "date_of_birth": "2012-01-10",
                "gender": "F",
                "is_active": True,
            },
        )

    def _mpesa_success_payload(self, checkout_id, receipt, amount="500.00"):
        return {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "29115-34620561-1",
                    "CheckoutRequestID": checkout_id,
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": amount},
                            {"Name": "MpesaReceiptNumber", "Value": receipt},
                            {"Name": "TransactionDate", "Value": "20260417103045"},
                            {"Name": "PhoneNumber", "Value": 254700123456},
                        ]
                    },
                }
            }
        }

    def _post_mpesa_callback(self, payload):
        raw = json.dumps(payload).encode("utf-8")
        request = self.factory.post(
            "/api/finance/mpesa/callback/",
            raw,
            content_type="application/json",
        )
        return MpesaStkCallbackView.as_view()(request)

    def _post_stripe_webhook(self, payload, secret, header=""):
        raw = json.dumps(payload).encode("utf-8")
        timestamp = str(int(timezone.now().timestamp()))
        signature = hmac.new(
            secret.encode("utf-8"),
            f"{timestamp}.{raw.decode('utf-8')}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        request = self.factory.post(
            "/api/finance/gateway/webhooks/stripe/",
            raw,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=header or f"t={timestamp},v1={signature}",
        )
        return FinanceGatewayWebhookView.as_view()(request, provider="stripe")

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

    @override_settings(
        FINANCE_WEBHOOK_TOKEN="",
        FINANCE_WEBHOOK_SHARED_SECRET="",
        FINANCE_WEBHOOK_STRICT_MODE=False,
    )
    def test_gateway_webhook_falls_back_to_raw_body_when_parser_cannot_handle_content_type(self):
        raw = json.dumps(
            {
                "event_id": "evt-raw-body-001",
                "event_type": "payment.succeeded",
            }
        ).encode("utf-8")
        request = self.factory.post(
            "/api/finance/gateway/webhooks/mpesa/",
            raw,
            content_type="text/plain",
        )
        response = FinanceGatewayWebhookView.as_view()(request, provider="mpesa")

        self.assertEqual(response.status_code, 201)
        event = PaymentGatewayWebhookEvent.objects.get(event_id="evt-raw-body-001")
        self.assertEqual(event.provider, "mpesa")

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

    def test_bank_line_import_csv_creates_rows_and_supports_match_then_clear(self):
        payment = Payment.objects.create(
            student=self.student,
            amount="500.00",
            payment_method="Bank Transfer",
            reference_number="BANK-CSV-9001",
            notes="csv import verification payment",
        )
        upload = SimpleUploadedFile(
            "bank-lines.csv",
            (
                "statement_date,value_date,amount,reference,narration,source\n"
                "2026-02-14,2026-02-14,500.00,BANK-CSV-9001,Parent transfer,csv\n"
                "2026-02-15,2026-02-15,1250.00,BANK-CSV-9002,Second transfer,csv\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        import_request = self.factory.post(
            "/api/finance/reconciliation/bank-lines/import-csv/",
            {"file": upload},
            format="multipart",
        )
        force_authenticate(import_request, user=self.user)
        import_response = BankStatementLineViewSet.as_view({"post": "import_csv"})(import_request)

        self.assertEqual(import_response.status_code, 201)
        self.assertEqual(import_response.data["created"], 2)
        line = BankStatementLine.objects.get(reference="BANK-CSV-9001")
        self.assertEqual(line.source, "csv")
        self.assertEqual(line.status, "UNMATCHED")

        match_request = self.factory.post(f"/api/finance/reconciliation/bank-lines/{line.id}/auto-match/")
        force_authenticate(match_request, user=self.user)
        match_response = BankStatementLineViewSet.as_view({"post": "auto_match"})(match_request, pk=line.id)

        self.assertEqual(match_response.status_code, 200)
        line.refresh_from_db()
        self.assertEqual(line.status, "MATCHED")
        self.assertEqual(line.matched_payment_id, payment.id)

        clear_request = self.factory.post(f"/api/finance/reconciliation/bank-lines/{line.id}/clear/")
        force_authenticate(clear_request, user=self.user)
        clear_response = BankStatementLineViewSet.as_view({"post": "clear"})(clear_request, pk=line.id)

        self.assertEqual(clear_response.status_code, 200)
        line.refresh_from_db()
        self.assertEqual(line.status, "CLEARED")

    def test_bank_line_manual_patch_match_sets_status_to_matched(self):
        payment = Payment.objects.create(
            student=self.student,
            amount="640.00",
            payment_method="Bank Transfer",
            reference_number="BANK-MANUAL-9001",
            notes="manual reconciliation target",
        )
        line = BankStatementLine.objects.create(
            statement_date="2026-02-16",
            amount="640.00",
            reference="BANK-MANUAL-9001",
            source="manual",
            status="UNMATCHED",
        )

        request = self.factory.patch(
            f"/api/finance/reconciliation/bank-lines/{line.id}/",
            {"matched_payment": payment.id},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = BankStatementLineViewSet.as_view({"patch": "partial_update"})(request, pk=line.id)

        self.assertEqual(response.status_code, 200)
        line.refresh_from_db()
        self.assertEqual(line.status, "MATCHED")
        self.assertEqual(line.matched_payment_id, payment.id)

    def test_bank_line_patch_rejects_direct_status_changes(self):
        line = BankStatementLine.objects.create(
            statement_date="2026-02-17",
            amount="910.00",
            reference="BANK-STATUS-REJECT",
            source="manual",
            status="UNMATCHED",
        )

        request = self.factory.patch(
            f"/api/finance/reconciliation/bank-lines/{line.id}/",
            {"status": "CLEARED"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = BankStatementLineViewSet.as_view({"patch": "partial_update"})(request, pk=line.id)

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Use the clear, unmatch, or ignore actions",
            response.data["error"]["message"],
        )
        self.assertIn(
            "Use the clear, unmatch, or ignore actions",
            response.data["error"]["details"]["status"][0],
        )
        line.refresh_from_db()
        self.assertEqual(line.status, "UNMATCHED")

    def test_mpesa_callback_is_idempotent_for_duplicate_payloads(self):
        PaymentGatewayTransaction.objects.create(
            provider="mpesa",
            external_id="ws_CO_DUPLICATE",
            student=self.student,
            amount="500.00",
            status="PENDING",
            payload={},
        )
        payload = self._mpesa_success_payload(
            checkout_id="ws_CO_DUPLICATE",
            receipt="MPESA-REPLAY-001",
        )

        first = self._post_mpesa_callback(payload)
        second = self._post_mpesa_callback(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Payment.objects.filter(reference_number="MPESA-REPLAY-001").count(), 1)
        self.assertEqual(PaymentGatewayWebhookEvent.objects.count(), 1)

        event = PaymentGatewayWebhookEvent.objects.get()
        self.assertTrue(event.processed)
        self.assertEqual(event.error, "")

    def test_mpesa_status_returns_receipt_urls_after_successful_callback(self):
        PaymentGatewayTransaction.objects.create(
            provider="mpesa",
            external_id="ws_CO_STATUS",
            student=self.student,
            amount="500.00",
            status="PENDING",
            payload={"reference": "FEES-STATUS"},
        )
        payload = self._mpesa_success_payload(
            checkout_id="ws_CO_STATUS",
            receipt="MPESA-STATUS-001",
        )

        callback_response = self._post_mpesa_callback(payload)
        self.assertEqual(callback_response.status_code, 200)

        payment = Payment.objects.get(reference_number="MPESA-STATUS-001")
        self.assertTrue(payment.receipt_number)

        tx = PaymentGatewayTransaction.objects.get(external_id="ws_CO_STATUS")
        self.assertTrue(tx.is_reconciled)
        self.assertEqual(tx.payload.get("payment_id"), payment.id)
        self.assertEqual(tx.payload.get("payment_reference"), payment.reference_number)

        status_request = self.factory.get(
            "/api/finance/mpesa/status/",
            {"checkout_request_id": "ws_CO_STATUS"},
        )
        force_authenticate(status_request, user=self.user)
        status_response = MpesaStkStatusView.as_view()(status_request)

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.data["status"], "SUCCEEDED")
        self.assertEqual(status_response.data["mpesa_receipt"], "MPESA-STATUS-001")
        self.assertEqual(status_response.data["payment_id"], payment.id)
        self.assertEqual(status_response.data["payment_reference"], payment.reference_number)
        self.assertEqual(status_response.data["payment_receipt_number"], payment.receipt_number)
        self.assertTrue(
            status_response.data["receipt_json_url"].endswith(
                f"/api/finance/payments/{payment.id}/receipt/?format=json"
            )
        )
        self.assertTrue(
            status_response.data["receipt_pdf_url"].endswith(
                f"/api/finance/payments/{payment.id}/receipt/pdf/"
            )
        )

    @patch("clients.billing_engine.BillingEngine.for_tenant")
    def test_mpesa_callback_records_billing_fee_using_active_tenant_context(self, mock_for_tenant):
        PaymentGatewayTransaction.objects.create(
            provider="mpesa",
            external_id="ws_CO_BILLING",
            student=self.student,
            amount="500.00",
            status="PENDING",
            payload={},
        )
        payload = self._mpesa_success_payload(
            checkout_id="ws_CO_BILLING",
            receipt="MPESA-BILLING-001",
        )

        response = self._post_mpesa_callback(payload)

        self.assertEqual(response.status_code, 200)
        mock_for_tenant.assert_called_once_with(
            schema_name=self.tenant.schema_name,
            school_name=self.tenant.name,
        )
        mock_for_tenant.return_value.record_transaction_fee.assert_called_once()

    def test_mpesa_callback_can_be_reprocessed_after_missing_transaction_is_fixed(self):
        payload = self._mpesa_success_payload(
            checkout_id="ws_CO_REPROCESS",
            receipt="MPESA-RETRY-001",
        )

        first = self._post_mpesa_callback(payload)
        self.assertEqual(first.status_code, 200)

        event = PaymentGatewayWebhookEvent.objects.get()
        self.assertFalse(event.processed)
        self.assertIn("Unknown M-Pesa checkout_request_id", event.error)

        PaymentGatewayTransaction.objects.create(
            provider="mpesa",
            external_id="ws_CO_REPROCESS",
            student=self.student,
            amount="500.00",
            status="PENDING",
            payload={},
        )

        request = self.factory.post(f"/api/finance/gateway/events/{event.id}/reprocess/")
        force_authenticate(request, user=self.user)
        response = PaymentGatewayWebhookEventViewSet.as_view({"post": "reprocess"})(request, pk=event.id)

        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertTrue(event.processed)
        self.assertEqual(event.error, "")
        self.assertEqual(Payment.objects.filter(reference_number="MPESA-RETRY-001").count(), 1)

    def test_mpesa_callback_retry_path_logs_at_info_for_missing_transaction(self):
        payload = self._mpesa_success_payload(
            checkout_id="ws_CO_RETRY_LOG",
            receipt="MPESA-RETRY-LOG-001",
        )

        with self.assertLogs("school.views", level="INFO") as logs:
            response = self._post_mpesa_callback(payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any("M-Pesa callback stored for retry" in entry for entry in logs.output))
        self.assertFalse(
            any(
                "WARNING:school.views:M-Pesa callback stored for retry" in entry
                for entry in logs.output
            )
        )

    def test_bank_line_auto_match_falls_back_to_unique_amount_and_date_window(self):
        payment = Payment.objects.create(
            student=self.student,
            amount="725.00",
            payment_method="Bank Transfer",
            reference_number="BANK-REF-FALLBACK",
            notes="manual bank posting",
        )
        target_time = timezone.now() - timedelta(days=1)
        Payment.objects.filter(pk=payment.pk).update(payment_date=target_time)

        line = BankStatementLine.objects.create(
            statement_date=target_time.date(),
            amount="725.00",
            reference="",
            narration="",
            source="csv",
            status="UNMATCHED",
        )

        request = self.factory.post(f"/api/finance/reconciliation/bank-lines/{line.id}/auto-match/")
        force_authenticate(request, user=self.user)
        response = BankStatementLineViewSet.as_view({"post": "auto_match"})(request, pk=line.id)

        self.assertEqual(response.status_code, 200)
        line.refresh_from_db()
        self.assertEqual(line.status, "MATCHED")
        self.assertEqual(line.matched_payment_id, payment.id)

    def test_bank_line_auto_match_leaves_ambiguous_amount_matches_unmatched(self):
        first = Payment.objects.create(
            student=self.student,
            amount="810.00",
            payment_method="Bank Transfer",
            reference_number="BANK-AMB-001",
            notes="ambiguous payment 1",
        )
        second = Payment.objects.create(
            student=self.student,
            amount="810.00",
            payment_method="Bank Transfer",
            reference_number="BANK-AMB-002",
            notes="ambiguous payment 2",
        )
        target_time = timezone.now()
        Payment.objects.filter(pk__in=[first.pk, second.pk]).update(payment_date=target_time)

        line = BankStatementLine.objects.create(
            statement_date=target_time.date(),
            amount="810.00",
            reference="",
            narration="",
            source="csv",
            status="UNMATCHED",
        )

        request = self.factory.post(f"/api/finance/reconciliation/bank-lines/{line.id}/auto-match/")
        force_authenticate(request, user=self.user)
        response = BankStatementLineViewSet.as_view({"post": "auto_match"})(request, pk=line.id)

        self.assertEqual(response.status_code, 200)
        line.refresh_from_db()
        self.assertEqual(line.status, "UNMATCHED")
        self.assertIsNone(line.matched_payment_id)

    def test_bank_line_auto_match_uses_gateway_payload_reference_fields(self):
        tx = PaymentGatewayTransaction.objects.create(
            provider="stripe",
            external_id="cs_test_ref_match_001",
            student=self.student,
            amount="1120.00",
            currency="KES",
            status="SUCCEEDED",
            payload={
                "reference": "STR-FAST-1120",
                "stripe_payment_intent_id": "pi_fast_1120",
            },
        )
        line = BankStatementLine.objects.create(
            statement_date=timezone.now().date(),
            amount="1120.00",
            reference="STR-FAST-1120",
            source="csv",
            status="UNMATCHED",
        )

        request = self.factory.post(f"/api/finance/reconciliation/bank-lines/{line.id}/auto-match/")
        force_authenticate(request, user=self.user)
        response = BankStatementLineViewSet.as_view({"post": "auto_match"})(request, pk=line.id)

        self.assertEqual(response.status_code, 200)
        line.refresh_from_db()
        self.assertEqual(line.status, "MATCHED")
        self.assertEqual(line.matched_gateway_transaction_id, tx.id)

    @patch("school.stripe.create_checkout_session")
    def test_stripe_checkout_session_creates_pending_gateway_transaction(self, mock_create_checkout_session):
        TenantSettings.objects.create(
            key="integrations.stripe",
            value={"secret_key": "sk_test_demo", "webhook_secret": "whsec_demo"},
            category="integrations",
        )
        mock_create_checkout_session.return_value = {
            "id": "cs_test_fasttrack_001",
            "url": "https://checkout.stripe.test/session/cs_test_fasttrack_001",
            "payment_status": "unpaid",
            "status": "open",
            "payment_intent": None,
            "configured_mode": "test",
        }

        request = self.factory.post(
            "/api/finance/stripe/checkout-session/",
            {
                "student_id": self.student.id,
                "amount": "875.00",
                "notes": "Fast-track Stripe checkout",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = StripeCheckoutSessionView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        tx = PaymentGatewayTransaction.objects.get(external_id="cs_test_fasttrack_001")
        self.assertEqual(tx.provider, "stripe")
        self.assertEqual(str(tx.amount), "875.00")
        self.assertEqual(tx.status, "PENDING")
        self.assertEqual(response.data["checkout_session_id"], "cs_test_fasttrack_001")
        self.assertIn("checkout.stripe.test", response.data["checkout_url"])

    @patch("school.stripe.test_connection")
    def test_stripe_test_connection_returns_account_summary(self, mock_test_connection):
        mock_test_connection.return_value = {
            "account_id": "acct_test_123",
            "display_name": "Fast Track School",
            "mode": "test",
            "livemode": False,
        }
        request = self.factory.post(
            "/api/finance/stripe/test-connection/",
            {"secret_key": "sk_test_demo"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = StripeTestConnectionView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["account_id"], "acct_test_123")
        self.assertIn("Fast Track School", response.data["message"])

    def test_finance_launch_readiness_flags_missing_configuration(self):
        request = self.factory.get("/api/finance/launch-readiness/")
        force_authenticate(request, user=self.user)
        response = FinanceLaunchReadinessView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["ready"])
        self.assertIn("Configure integrations.stripe.secret_key for this tenant.", response.data["blocking_issues"])
        self.assertIn("Configure integrations.mpesa for this tenant.", response.data["blocking_issues"])
        self.assertEqual(
            response.data["validation_paths"]["stripe_test_connection"],
            "/api/finance/stripe/test-connection/",
        )

    def test_finance_launch_readiness_reports_ready_config_and_ops_warnings(self):
        TenantSettings.objects.create(
            key="integrations.stripe",
            value={"secret_key": "sk_test_demo", "webhook_secret": "whsec_demo"},
            category="integrations",
        )
        TenantSettings.objects.create(
            key="integrations.mpesa",
            value={
                "enabled": True,
                "consumer_key": "ck_demo",
                "consumer_secret": "cs_demo",
                "shortcode": "174379",
                "passkey": "passkey_demo",
                "environment": "sandbox",
            },
            category="integrations",
        )
        TenantSettings.objects.create(
            key="system.callback_base_url",
            value="https://school.example.com",
            category="system",
        )
        PaymentGatewayWebhookEvent.objects.create(
            event_id="evt_launch_warning_001",
            provider="stripe",
            event_type="checkout.session.completed",
            payload={"id": "evt_launch_warning_001"},
            processed=False,
            error="Waiting for transaction to exist.",
        )
        BankStatementLine.objects.create(
            statement_date=timezone.now().date(),
            amount="650.00",
            reference="BANK-LAUNCH-001",
            source="csv",
            status="UNMATCHED",
        )

        request = self.factory.get("/api/finance/launch-readiness/")
        force_authenticate(request, user=self.user)
        response = FinanceLaunchReadinessView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["ready"])
        self.assertEqual(response.data["public_base_url"], "https://school.example.com")
        self.assertTrue(response.data["stripe"]["configured"])
        self.assertTrue(response.data["mpesa"]["configured"])
        self.assertEqual(response.data["operations"]["unprocessed_webhook_events"], 1)
        self.assertEqual(response.data["operations"]["reprocessable_webhook_events"], 1)
        self.assertEqual(response.data["operations"]["unmatched_bank_lines"], 1)
        self.assertEqual(response.data["operations"]["imported_csv_lines"], 1)
        self.assertTrue(
            any("still unprocessed" in warning for warning in response.data["warnings"])
        )
        self.assertTrue(
            any("bank-lines" in action for action in response.data["next_actions"])
        )

    def test_finance_launch_readiness_uses_tenant_domain_when_callback_base_url_missing(self):
        TenantSettings.objects.create(
            key="integrations.stripe",
            value={"secret_key": "sk_test_demo", "webhook_secret": "whsec_demo"},
            category="integrations",
        )
        TenantSettings.objects.create(
            key="integrations.mpesa",
            value={
                "enabled": True,
                "consumer_key": "ck_demo",
                "consumer_secret": "cs_demo",
                "shortcode": "174379",
                "passkey": "passkey_demo",
                "environment": "sandbox",
            },
            category="integrations",
        )

        request = self.factory.get("/api/finance/launch-readiness/")
        force_authenticate(request, user=self.user)
        response = FinanceLaunchReadinessView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["ready"])
        self.assertEqual(response.data["public_base_url"], "https://finance-phase4.localhost")
        self.assertEqual(response.data["mpesa"]["callback_source"], "tenant_domain")
        self.assertEqual(
            response.data["mpesa"]["callback_url"],
            "https://finance-phase4.localhost/api/finance/mpesa/callback/",
        )
        self.assertEqual(
            response.data["stripe"]["webhook_url"],
            "https://finance-phase4.localhost/api/finance/gateway/webhooks/stripe/",
        )

    def test_stripe_webhook_rejects_invalid_signature(self):
        TenantSettings.objects.create(
            key="integrations.stripe",
            value={"webhook_secret": "whsec_valid"},
            category="integrations",
        )
        payload = {
            "id": "evt_stripe_bad_sig",
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_missing", "payment_status": "paid"}},
        }
        response = self._post_stripe_webhook(payload, "whsec_valid", header="t=123,v1=bad")
        self.assertEqual(response.status_code, 401)

    def test_stripe_webhook_finalizes_payment_through_shared_gateway_path(self):
        TenantSettings.objects.create(
            key="integrations.stripe",
            value={"secret_key": "sk_test_demo", "webhook_secret": "whsec_valid"},
            category="integrations",
        )
        PaymentGatewayTransaction.objects.create(
            provider="stripe",
            external_id="cs_test_complete_001",
            student=self.student,
            amount="900.00",
            currency="KES",
            status="PENDING",
            payload={},
        )
        payload = {
            "id": "evt_stripe_complete_001",
            "type": "checkout.session.completed",
            "livemode": False,
            "data": {
                "object": {
                    "id": "cs_test_complete_001",
                    "payment_status": "paid",
                    "status": "complete",
                    "amount_total": 90000,
                    "currency": "kes",
                    "payment_intent": "pi_test_complete_001",
                    "client_reference_id": "STR-REF-001",
                    "customer_details": {"email": "parent@example.com"},
                    "metadata": {
                        "student_id": str(self.student.id),
                        "amount": "900.00",
                        "currency": "KES",
                    },
                }
            },
        }

        response = self._post_stripe_webhook(payload, "whsec_valid")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["processed"])
        self.assertEqual(Payment.objects.filter(reference_number="pi_test_complete_001").count(), 1)

        tx = PaymentGatewayTransaction.objects.get(external_id="cs_test_complete_001")
        self.assertEqual(tx.status, "SUCCEEDED")
        self.assertTrue(tx.is_reconciled)
        self.assertEqual(tx.payload.get("stripe_event_type"), "checkout.session.completed")

        revenue = RevenueLog.objects.get(mpesa_receipt="pi_test_complete_001")
        self.assertEqual(revenue.schema_name, self.tenant.schema_name)
        self.assertEqual(revenue.source, "TRANSACTION_FEE")
        self.assertEqual(revenue.metadata.get("gateway_provider"), "stripe")
        self.assertEqual(revenue.metadata.get("gateway_external_id"), "cs_test_complete_001")

    def test_stripe_webhook_can_be_reprocessed_after_missing_transaction_is_fixed(self):
        TenantSettings.objects.create(
            key="integrations.stripe",
            value={"secret_key": "sk_test_demo", "webhook_secret": "whsec_valid"},
            category="integrations",
        )
        payload = {
            "id": "evt_stripe_retry_001",
            "type": "checkout.session.completed",
            "livemode": False,
            "data": {
                "object": {
                    "id": "cs_test_reprocess_001",
                    "payment_status": "paid",
                    "status": "complete",
                    "amount_total": 91000,
                    "currency": "kes",
                    "payment_intent": "pi_test_reprocess_001",
                    "customer_details": {"email": "parent@example.com"},
                }
            },
        }

        first = self._post_stripe_webhook(payload, "whsec_valid")
        self.assertEqual(first.status_code, 201)

        event = PaymentGatewayWebhookEvent.objects.get(event_id="evt_stripe_retry_001")
        self.assertFalse(event.processed)
        self.assertIn("Unknown Stripe checkout session id", event.error)

        PaymentGatewayTransaction.objects.create(
            provider="stripe",
            external_id="cs_test_reprocess_001",
            student=self.student,
            amount="910.00",
            currency="KES",
            status="PENDING",
            payload={},
        )

        request = self.factory.post(f"/api/finance/gateway/events/{event.id}/reprocess/")
        force_authenticate(request, user=self.user)
        response = PaymentGatewayWebhookEventViewSet.as_view({"post": "reprocess"})(request, pk=event.id)

        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertTrue(event.processed)
        self.assertEqual(event.error, "")
        self.assertEqual(Payment.objects.filter(reference_number="pi_test_reprocess_001").count(), 1)

        tx = PaymentGatewayTransaction.objects.get(external_id="cs_test_reprocess_001")
        self.assertEqual(tx.status, "SUCCEEDED")
        self.assertTrue(tx.is_reconciled)

        revenue = RevenueLog.objects.get(mpesa_receipt="pi_test_reprocess_001")
        self.assertEqual(revenue.schema_name, self.tenant.schema_name)
        self.assertEqual(revenue.metadata.get("gateway_provider"), "stripe")
