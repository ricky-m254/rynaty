from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from django_tenants.utils import schema_context

from clients.models import Domain, Tenant
from school.models import AcademicYear, Invoice, Payment, PaymentGatewayTransaction, Student, TenantSettings, Term


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="mpesa_reconcile_test",
                name="M-Pesa Reconcile Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="mpesa-reconcile.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class MpesaReconcilePendingCommandTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.student = Student.objects.create(
            first_name="Amina",
            last_name="Otieno",
            date_of_birth=date(2012, 1, 10),
            admission_number="MPESA-REC-001",
            gender="F",
            is_active=True,
        )
        self.year = AcademicYear.objects.create(
            name="2026-2027",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        self.term = Term.objects.create(
            academic_year=self.year,
            name="Term 1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            is_active=True,
        )
        self.invoice = Invoice.objects.create(
            student=self.student,
            term=self.term,
            due_date=date(2026, 2, 1),
            total_amount=Decimal("500.00"),
            status="ISSUED",
            is_active=True,
        )

    def _pending_tx(self, external_id, amount="500.00", age_minutes=30):
        tx = PaymentGatewayTransaction.objects.create(
            provider="mpesa",
            external_id=external_id,
            student=self.student,
            invoice=self.invoice,
            amount=Decimal(str(amount)),
            currency="KES",
            status="PENDING",
            payload={},
            is_reconciled=False,
        )
        PaymentGatewayTransaction.objects.filter(pk=tx.pk).update(
            created_at=timezone.now() - timedelta(minutes=age_minutes)
        )
        tx.refresh_from_db()
        return tx

    @patch("school.mpesa.query_stk_status")
    def test_command_reconciles_successful_pending_transaction(self, mock_query_stk_status):
        tx = self._pending_tx("ws_CO_RECON_SUCCESS")
        mock_query_stk_status.return_value = {
            "success": True,
            "result_code": 0,
            "result_desc": "The service request is processed successfully.",
            "friendly_message": "Payment confirmed successfully.",
            "mpesa_receipt": "MPESA-RECON-001",
            "amount": Decimal("500.00"),
            "checkout_request_id": tx.external_id,
        }

        call_command("reconcile_mpesa_pending", minutes=15)

        tx.refresh_from_db()
        self.invoice.refresh_from_db()
        payment = Payment.objects.get(reference_number="MPESA-RECON-001")

        self.assertEqual(tx.status, "SUCCEEDED")
        self.assertTrue(tx.is_reconciled)
        self.assertEqual(tx.payload.get("mpesa_receipt"), "MPESA-RECON-001")
        self.assertEqual(payment.student_id, self.student.id)
        self.assertEqual(payment.amount, Decimal("500.00"))
        self.assertEqual(str(self.invoice.balance_due), "0.00")
        self.assertEqual(self.invoice.status, "PAID")
        self.assertEqual(payment.allocations.count(), 1)
        self.assertEqual(payment.allocations.first().invoice_id, self.invoice.id)
        self.assertEqual(payment.allocations.first().amount_allocated, Decimal("500.00"))

    @patch("school.mpesa.query_stk_status")
    def test_command_marks_failed_pending_transaction(self, mock_query_stk_status):
        tx = self._pending_tx("ws_CO_RECON_FAIL")
        mock_query_stk_status.return_value = {
            "success": False,
            "result_code": 1032,
            "result_desc": "Request cancelled by user",
            "friendly_message": "The customer cancelled the payment request on their phone.",
            "mpesa_receipt": None,
            "amount": None,
            "checkout_request_id": tx.external_id,
        }

        call_command("reconcile_mpesa_pending", minutes=15)

        tx.refresh_from_db()
        self.assertEqual(tx.status, "FAILED")
        self.assertTrue(tx.is_reconciled)
        self.assertEqual(tx.payload.get("result_code"), 1032)
        self.assertEqual(tx.payload.get("result_desc"), "Request cancelled by user")
        self.assertEqual(Payment.objects.count(), 0)

    @patch("school.mpesa.query_stk_status")
    def test_command_dry_run_does_not_mutate_transaction_state(self, mock_query_stk_status):
        tx = self._pending_tx("ws_CO_RECON_DRY")
        mock_query_stk_status.return_value = {
            "success": True,
            "result_code": 0,
            "result_desc": "The service request is processed successfully.",
            "friendly_message": "Payment confirmed successfully.",
            "mpesa_receipt": "MPESA-RECON-DRY-001",
            "amount": Decimal("500.00"),
            "checkout_request_id": tx.external_id,
        }

        call_command("reconcile_mpesa_pending", minutes=15, dry_run=True)

        tx.refresh_from_db()
        self.assertEqual(tx.status, "PENDING")
        self.assertFalse(tx.is_reconciled)
        self.assertEqual(Payment.objects.count(), 0)

    @patch("school.mpesa.query_stk_status")
    def test_command_uses_saved_reconciliation_interval_when_minutes_omitted(self, mock_query_stk_status):
        TenantSettings.objects.create(
            key="finance.operations",
            value={"mpesa_reconciliation_minutes": 5},
            category="finance",
        )
        tx = self._pending_tx("ws_CO_RECON_SETTINGS", age_minutes=8)
        mock_query_stk_status.return_value = {
            "success": True,
            "result_code": 0,
            "result_desc": "The service request is processed successfully.",
            "friendly_message": "Payment confirmed successfully.",
            "mpesa_receipt": "MPESA-RECON-SETTINGS-001",
            "amount": Decimal("500.00"),
            "checkout_request_id": tx.external_id,
        }

        call_command("reconcile_mpesa_pending")

        tx.refresh_from_db()
        self.assertEqual(tx.status, "SUCCEEDED")
        self.assertTrue(tx.is_reconciled)
        self.assertEqual(Payment.objects.filter(reference_number="MPESA-RECON-SETTINGS-001").count(), 1)
