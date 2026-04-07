import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicYear, Term
from clients.models import Domain, Tenant
from finance.presentation.collection_ops_views import FinanceGatewayWebhookView as StagedFinanceGatewayWebhookView
from finance.presentation.collection_ops_viewsets import (
    BankStatementLineViewSet as StagedBankStatementLineViewSet,
    FeeReminderLogViewSet as StagedFeeReminderLogViewSet,
    LateFeeRuleViewSet as StagedLateFeeRuleViewSet,
    PaymentGatewayTransactionViewSet as StagedPaymentGatewayTransactionViewSet,
    PaymentGatewayWebhookEventViewSet as StagedPaymentGatewayWebhookEventViewSet,
)
from school.models import (
    BankStatementLine,
    FeeReminderLog,
    Guardian,
    Invoice,
    InvoiceInstallment,
    InvoiceInstallmentPlan,
    LateFeeRule,
    Module,
    Payment,
    PaymentGatewayTransaction,
    PaymentGatewayWebhookEvent,
    Role,
    Student,
    UserModuleAssignment,
    UserProfile,
)
from school.views import (
    BankStatementLineViewSet as LiveBankStatementLineViewSet,
    FeeReminderLogViewSet as LiveFeeReminderLogViewSet,
    FinanceGatewayWebhookView as LiveFinanceGatewayWebhookView,
    LateFeeRuleViewSet as LiveLateFeeRuleViewSet,
    PaymentGatewayTransactionViewSet as LivePaymentGatewayTransactionViewSet,
    PaymentGatewayWebhookEventViewSet as LivePaymentGatewayWebhookEventViewSet,
)


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="finance_phase6_collection_ops_prep_test",
                defaults={
                    "name": "Finance Phase 6 Collection Ops Prep Test School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="finance-phase6-collection-ops-prep.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class FinanceCollectionOpsActivationPrepTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="finance_phase6_collection_user", password="pass1234")
        role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "School Administrator"})
        UserProfile.objects.get_or_create(user=self.user, defaults={"role": role})
        finance_module, _ = Module.objects.get_or_create(key="FINANCE", defaults={"name": "Finance"})
        UserModuleAssignment.objects.get_or_create(user=self.user, module=finance_module)

        self.year = AcademicYear.objects.create(
            name="2026-2027",
            start_date="2026-01-01",
            end_date="2026-12-31",
            is_active=True,
            is_current=True,
        )
        self.term = Term.objects.create(
            academic_year=self.year,
            name="Term 1",
            start_date="2026-01-01",
            end_date="2026-04-30",
            billing_date="2026-01-05",
            is_active=True,
            is_current=True,
        )
        self.student = Student.objects.create(
            admission_number="COL-001",
            first_name="Brian",
            last_name="Otieno",
            gender="M",
            date_of_birth="2011-01-01",
            is_active=True,
        )
        Guardian.objects.create(
            student=self.student,
            name="Jane Otieno",
            relationship="Mother",
            phone="+254700000001",
            email="jane.otieno@example.com",
            is_active=True,
        )
        self.invoice = Invoice.objects.create(
            student=self.student,
            term_id=self.term.id,
            due_date=timezone.now().date() - timedelta(days=14),
            total_amount=Decimal("12000.00"),
            status="ISSUED",
            is_active=True,
        )
        self.installment_plan = InvoiceInstallmentPlan.objects.create(invoice=self.invoice, installment_count=2)
        InvoiceInstallment.objects.create(
            plan=self.installment_plan,
            sequence=1,
            due_date=timezone.now().date() - timedelta(days=12),
            amount=Decimal("6000.00"),
            status="PENDING",
            late_fee_applied=False,
        )
        InvoiceInstallment.objects.create(
            plan=self.installment_plan,
            sequence=2,
            due_date=timezone.now().date() + timedelta(days=7),
            amount=Decimal("6000.00"),
            status="PENDING",
            late_fee_applied=False,
        )

        self.late_fee_rule = LateFeeRule.objects.create(
            grace_days=3,
            fee_type="FLAT",
            value=Decimal("250.00"),
            max_fee=Decimal("500.00"),
            is_active=True,
        )
        self.seed_reminder = FeeReminderLog.objects.create(
            invoice=self.invoice,
            channel="EMAIL",
            recipient="jane.otieno@example.com",
            status="SENT",
            message="Seed reminder",
        )
        self.payment = Payment.objects.create(
            student=self.student,
            amount=Decimal("12000.00"),
            payment_method="BANK",
            reference_number="COL-PAY-001",
            notes="Collection ops parity payment",
            is_active=True,
        )
        self.gateway_transaction = PaymentGatewayTransaction.objects.create(
            provider="mpesa",
            external_id="COL-TX-001",
            student=self.student,
            invoice=self.invoice,
            amount=Decimal("12000.00"),
            currency="KES",
            status="PENDING",
            payload={"seed": True},
            is_reconciled=False,
        )
        self.gateway_event = PaymentGatewayWebhookEvent.objects.create(
            event_id="COL-EVT-001",
            provider="mpesa",
            event_type="payment.pending",
            signature="sig-seed",
            payload={"seed": True},
            processed=True,
            processed_at=timezone.now(),
        )
        self.bank_line = BankStatementLine.objects.create(
            statement_date=timezone.now().date() - timedelta(days=1),
            value_date=timezone.now().date() - timedelta(days=1),
            amount=Decimal("12000.00"),
            reference="COL-PAY-001",
            narration="Fee payment received",
            source="manual",
            status="UNMATCHED",
        )

    def _invoke_viewset(self, viewset_class, method, action, path, data=None, **kwargs):
        request = getattr(self.factory, method.lower())(path, data=data, format="json")
        force_authenticate(request, user=self.user)
        return viewset_class.as_view({method.lower(): action})(request, **kwargs)

    def _invoke_api_view(self, view_class, method, path, data=None, content_type=None, **kwargs):
        if content_type:
            request = getattr(self.factory, method.lower())(path, data=data, content_type=content_type, **kwargs)
        else:
            request = getattr(self.factory, method.lower())(path, data=data, format="json", **kwargs)
        force_authenticate(request, user=self.user)
        return view_class.as_view()(request, **kwargs)

    def _normalize_late_fee_rule_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        return normalized

    def _normalize_gateway_transaction_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("created_at", None)
        normalized.pop("updated_at", None)
        return normalized

    def _normalize_bank_line_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("imported_at", None)
        return normalized

    def _normalize_webhook_response(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        return normalized

    def _extract_results(self, payload):
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        return payload

    def _normalize_reminder_logs(self):
        logs = FeeReminderLog.objects.order_by("id")
        return [
            {
                "invoice": log.invoice_id,
                "channel": log.channel,
                "recipient": log.recipient,
                "status": log.status,
                "message": log.message,
            }
            for log in logs
        ]

    def _signed_webhook_request(self, event_id, external_id):
        body = {
            "event_id": event_id,
            "event_type": "payment.pending",
            "external_id": external_id,
            "status": "PENDING",
            "amount": "12000.00",
            "student_id": self.student.id,
            "invoice_id": self.invoice.id,
        }
        raw = json.dumps(body).encode("utf-8")
        signature = hmac.new(b"secret-xyz", raw, hashlib.sha256).hexdigest()
        return raw, signature

    def test_staged_late_fee_rule_list_matches_live_contract(self):
        path = "/api/finance/late-fee-rules/"
        live_response = self._invoke_viewset(LiveLateFeeRuleViewSet, "get", "list", path)
        staged_response = self._invoke_viewset(StagedLateFeeRuleViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_late_fee_rule_create_matches_live_contract(self):
        payload = {
            "grace_days": 7,
            "fee_type": "PERCENT",
            "value": "2.50",
            "max_fee": "750.00",
            "is_active": False,
        }

        live_response = self._invoke_viewset(
            LiveLateFeeRuleViewSet,
            "post",
            "create",
            "/api/finance/late-fee-rules/",
            data=payload,
        )
        self.assertEqual(live_response.status_code, 201)
        LateFeeRule.objects.filter(grace_days=7, fee_type="PERCENT").delete()

        staged_response = self._invoke_viewset(
            StagedLateFeeRuleViewSet,
            "post",
            "create",
            "/api/finance/late-fee-rules/",
            data=payload,
        )

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_late_fee_rule_payload(staged_response.data),
            self._normalize_late_fee_rule_payload(live_response.data),
        )

    def test_staged_late_fee_preview_matches_live_contract(self):
        payload = {"dry_run": True}
        path = "/api/finance/late-fee-rules/apply/"
        live_response = self._invoke_viewset(
            LiveLateFeeRuleViewSet,
            "post",
            "apply_rules",
            path,
            data=payload,
        )
        staged_response = self._invoke_viewset(
            StagedLateFeeRuleViewSet,
            "post",
            "apply_rules",
            path,
            data=payload,
        )

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_reminder_list_matches_live_contract(self):
        recent_reminder = FeeReminderLog.objects.create(
            invoice=self.invoice,
            channel="SMS",
            recipient="+254700000001",
            status="SENT",
            message="Recent reminder",
        )
        recent_reminder.sent_at = self.seed_reminder.sent_at + timedelta(minutes=5)
        recent_reminder.save(update_fields=["sent_at"])

        path = "/api/finance/reminders/"
        live_response = self._invoke_viewset(LiveFeeReminderLogViewSet, "get", "list", path)
        staged_response = self._invoke_viewset(StagedFeeReminderLogViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)
        live_results = self._extract_results(live_response.data)
        staged_results = self._extract_results(staged_response.data)
        self.assertEqual(live_results[0]["id"], recent_reminder.id)
        self.assertEqual(staged_results[0]["id"], recent_reminder.id)

    def test_staged_send_overdue_reminders_matches_live_contract(self):
        FeeReminderLog.objects.all().delete()
        payload = {"channel": "EMAIL"}
        path = "/api/finance/reminders/send-overdue/"
        live_response = self._invoke_viewset(
            LiveFeeReminderLogViewSet,
            "post",
            "send_overdue",
            path,
            data=payload,
        )
        self.assertEqual(live_response.status_code, 200)
        live_logs = self._normalize_reminder_logs()

        FeeReminderLog.objects.all().delete()

        staged_response = self._invoke_viewset(
            StagedFeeReminderLogViewSet,
            "post",
            "send_overdue",
            path,
            data=payload,
        )
        staged_logs = self._normalize_reminder_logs()

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)
        self.assertEqual(staged_logs, live_logs)

    def test_staged_gateway_transaction_list_matches_live_contract(self):
        path = "/api/finance/gateway/transactions/?provider=mpesa&status=PENDING&is_reconciled=false"
        live_response = self._invoke_viewset(LivePaymentGatewayTransactionViewSet, "get", "list", path)
        staged_response = self._invoke_viewset(StagedPaymentGatewayTransactionViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_gateway_transaction_create_matches_live_contract(self):
        payload = {
            "provider": "mpesa",
            "external_id": "COL-TX-CREATE-001",
            "student": self.student.id,
            "invoice": self.invoice.id,
            "amount": "5000.00",
            "currency": "KES",
            "status": "INITIATED",
            "payload": {"source": "phase6-prep"},
        }

        live_response = self._invoke_viewset(
            LivePaymentGatewayTransactionViewSet,
            "post",
            "create",
            "/api/finance/gateway/transactions/",
            data=payload,
        )
        self.assertEqual(live_response.status_code, 201)
        PaymentGatewayTransaction.objects.filter(external_id="COL-TX-CREATE-001").delete()

        staged_response = self._invoke_viewset(
            StagedPaymentGatewayTransactionViewSet,
            "post",
            "create",
            "/api/finance/gateway/transactions/",
            data=payload,
        )

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_gateway_transaction_payload(staged_response.data),
            self._normalize_gateway_transaction_payload(live_response.data),
        )

    def test_staged_gateway_transaction_mark_reconciled_matches_live_contract(self):
        path = f"/api/finance/gateway/transactions/{self.gateway_transaction.id}/mark-reconciled/"
        live_response = self._invoke_viewset(
            LivePaymentGatewayTransactionViewSet,
            "post",
            "mark_reconciled",
            path,
            pk=self.gateway_transaction.id,
        )
        self.assertEqual(live_response.status_code, 200)
        self.gateway_transaction.refresh_from_db()
        self.gateway_transaction.is_reconciled = False
        self.gateway_transaction.save(update_fields=["is_reconciled", "updated_at"])

        staged_response = self._invoke_viewset(
            StagedPaymentGatewayTransactionViewSet,
            "post",
            "mark_reconciled",
            path,
            pk=self.gateway_transaction.id,
        )

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_gateway_transaction_payload(staged_response.data),
            self._normalize_gateway_transaction_payload(live_response.data),
        )

    def test_staged_gateway_event_list_matches_live_contract(self):
        path = "/api/finance/gateway/events/?provider=mpesa&processed=true"
        live_response = self._invoke_viewset(LivePaymentGatewayWebhookEventViewSet, "get", "list", path)
        staged_response = self._invoke_viewset(StagedPaymentGatewayWebhookEventViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    @override_settings(FINANCE_WEBHOOK_TOKEN="token-abc", FINANCE_WEBHOOK_SHARED_SECRET="secret-xyz")
    def test_staged_finance_gateway_webhook_matches_live_contract(self):
        raw, signature = self._signed_webhook_request("COL-EVT-WEBHOOK-001", "COL-TX-WEBHOOK-001")

        live_request = self.factory.post(
            "/api/finance/gateway/webhooks/mpesa/",
            raw,
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="token-abc",
            HTTP_X_WEBHOOK_SIGNATURE=f"sha256={signature}",
        )
        live_response = LiveFinanceGatewayWebhookView.as_view()(live_request, provider="mpesa")
        self.assertEqual(live_response.status_code, 201)

        PaymentGatewayWebhookEvent.objects.filter(event_id="COL-EVT-WEBHOOK-001").delete()
        PaymentGatewayTransaction.objects.filter(external_id="COL-TX-WEBHOOK-001").delete()

        staged_request = self.factory.post(
            "/api/finance/gateway/webhooks/mpesa/",
            raw,
            content_type="application/json",
            HTTP_X_WEBHOOK_TOKEN="token-abc",
            HTTP_X_WEBHOOK_SIGNATURE=f"sha256={signature}",
        )
        staged_response = StagedFinanceGatewayWebhookView.as_view()(staged_request, provider="mpesa")

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_webhook_response(staged_response.data),
            self._normalize_webhook_response(live_response.data),
        )

    def test_staged_bank_line_list_matches_live_contract(self):
        path = "/api/finance/reconciliation/bank-lines/?status=UNMATCHED&search=COL-PAY-001"
        live_response = self._invoke_viewset(LiveBankStatementLineViewSet, "get", "list", path)
        staged_response = self._invoke_viewset(StagedBankStatementLineViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_bank_line_auto_match_matches_live_contract(self):
        path = f"/api/finance/reconciliation/bank-lines/{self.bank_line.id}/auto-match/"
        live_response = self._invoke_viewset(
            LiveBankStatementLineViewSet,
            "post",
            "auto_match",
            path,
            pk=self.bank_line.id,
        )
        self.assertEqual(live_response.status_code, 200)
        self.bank_line.refresh_from_db()
        self.bank_line.status = "UNMATCHED"
        self.bank_line.matched_payment = None
        self.bank_line.matched_gateway_transaction = None
        self.bank_line.save(update_fields=["status", "matched_payment", "matched_gateway_transaction"])

        staged_response = self._invoke_viewset(
            StagedBankStatementLineViewSet,
            "post",
            "auto_match",
            path,
            pk=self.bank_line.id,
        )

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_bank_line_payload(staged_response.data),
            self._normalize_bank_line_payload(live_response.data),
        )
