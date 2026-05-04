from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicYear, Term
from clients.models import Domain, Tenant
from communication.models import SmsMessage
from finance.presentation.views import (
    FinanceReceiptPdfView as StagedFinanceReceiptPdfView,
    FinanceStudentLedgerView as StagedFinanceStudentLedgerView,
)
from finance.presentation.viewsets import (
    InvoiceAdjustmentViewSet as StagedInvoiceAdjustmentViewSet,
    InvoiceViewSet as StagedInvoiceViewSet,
    InvoiceWriteOffRequestViewSet as StagedInvoiceWriteOffRequestViewSet,
    PaymentReversalRequestViewSet as StagedPaymentReversalRequestViewSet,
    PaymentViewSet as StagedPaymentViewSet,
)
from school.models import (
    Enrollment,
    FeeStructure,
    Invoice,
    InvoiceAdjustment,
    InvoiceWriteOffRequest,
    Module,
    Payment,
    PaymentAllocation,
    PaymentReversalRequest,
    Role,
    SchoolClass,
    Student,
    Guardian,
    UserModuleAssignment,
    UserProfile,
    VoteHead,
    VoteHeadPaymentAllocation,
)
from school.views import (
    FinanceReceiptPdfView as LiveFinanceReceiptPdfView,
    FinanceStudentLedgerView as LiveFinanceStudentLedgerView,
    InvoiceAdjustmentViewSet as LiveInvoiceAdjustmentViewSet,
    InvoiceViewSet as LiveInvoiceViewSet,
    InvoiceWriteOffRequestViewSet as LiveInvoiceWriteOffRequestViewSet,
    PaymentReversalRequestViewSet as LivePaymentReversalRequestViewSet,
    PaymentViewSet as LivePaymentViewSet,
)
from school.services import FinanceService


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="finance_phase6_receivables_prep_test",
                defaults={
                    "name": "Finance Phase 6 Receivables Prep Test School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="finance-phase6-receivables-prep.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class FinanceReceivablesActivationPrepTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="finance_phase6_receivables_user", password="pass1234")
        role, _ = Role.objects.get_or_create(name="ACCOUNTANT", defaults={"description": "Finance Manager"})
        UserProfile.objects.get_or_create(user=self.user, defaults={"role": role})
        finance_module, _ = Module.objects.get_or_create(key="FINANCE", defaults={"name": "Finance"})
        UserModuleAssignment.objects.get_or_create(user=self.user, module=finance_module)

        self.year = AcademicYear.objects.create(
            name="2026-2027",
            start_date="2026-01-01",
            end_date="2026-12-31",
            is_active=True,
        )
        self.term = Term.objects.create(
            academic_year=self.year,
            name="Term 1",
            start_date="2026-01-01",
            end_date="2026-04-30",
            is_active=True,
        )
        self.school_class = SchoolClass.objects.create(
            name="Grade 8",
            stream="A",
            academic_year_id=self.year.id,
            is_active=True,
        )
        self.student = Student.objects.create(
            admission_number="REC-001",
            first_name="Amina",
            last_name="Njeri",
            gender="F",
            date_of_birth="2011-01-01",
            is_active=True,
        )
        Enrollment.objects.create(
            student=self.student,
            school_class_id=self.school_class.id,
            term_id=self.term.id,
            status="Active",
            is_active=True,
        )
        self.fee_structure = FeeStructure.objects.create(
            name="Tuition",
            category="Tuition",
            amount=Decimal("15000.00"),
            academic_year_id=self.year.id,
            term_id=self.term.id,
            billing_cycle="TERMLY",
            is_mandatory=True,
            description="Core tuition charge",
            is_active=True,
        )

    def _invoke_viewset(self, viewset_class, method, action, path, data=None, **kwargs):
        request = getattr(self.factory, method.lower())(path, data=data, format="json")
        force_authenticate(request, user=self.user)
        return viewset_class.as_view({method.lower(): action})(request, **kwargs)

    def _invoke_api_view(self, view_class, method, path, data=None, **kwargs):
        request = getattr(self.factory, method.lower())(path, data=data, format="json")
        force_authenticate(request, user=self.user)
        return view_class.as_view()(request, **kwargs)

    def _normalize_invoice_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("invoice_number", None)
        normalized.pop("invoice_date", None)
        normalized.pop("created_at", None)
        line_items = []
        for item in normalized.get("line_items", []):
            line_item = dict(item)
            line_item.pop("id", None)
            line_items.append(line_item)
        normalized["line_items"] = line_items
        return normalized

    def _normalize_payment_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("payment_date", None)
        normalized.pop("created_at", None)
        normalized.pop("receipt_number", None)
        normalized.pop("receipt_no", None)
        normalized.pop("receipt_json_url", None)
        normalized.pop("receipt_pdf_url", None)
        allocations = []
        for item in normalized.get("allocations", []):
            allocation = dict(item)
            allocation.pop("id", None)
            allocation.pop("allocated_at", None)
            allocations.append(allocation)
        normalized["allocations"] = allocations
        return normalized

    def _normalize_adjustment_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("created_at", None)
        return normalized

    def _normalize_reversal_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("requested_at", None)
        return normalized

    def _normalize_writeoff_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("requested_at", None)
        return normalized

    def test_staged_invoice_and_payment_lists_match_live_contract(self):
        invoice = Invoice.objects.create(
            student=self.student,
            term_id=self.term.id,
            due_date="2026-04-30",
            total_amount=Decimal("15000.00"),
            status="ISSUED",
            is_active=True,
        )
        payment = Payment.objects.create(
            student=self.student,
            amount=Decimal("3500.00"),
            payment_method="BANK",
            reference_number="LIST-PAY-001",
            notes="List test payment",
            is_active=True,
        )
        vote_head = VoteHead.objects.create(
            name="Tuition",
            description="Core tuition vote head",
        )
        VoteHeadPaymentAllocation.objects.create(
            payment=payment,
            vote_head=vote_head,
            amount=Decimal("3500.00"),
        )

        invoice_path = f"/api/finance/invoices/?search={self.student.admission_number}&status=ISSUED"
        live_invoice_list = self._invoke_viewset(LiveInvoiceViewSet, "get", "list", invoice_path)
        staged_invoice_list = self._invoke_viewset(StagedInvoiceViewSet, "get", "list", invoice_path)
        self.assertEqual(staged_invoice_list.status_code, live_invoice_list.status_code)
        self.assertEqual(staged_invoice_list.data, live_invoice_list.data)

        payment_path = "/api/finance/payments/?payment_method=BANK&allocation_status=unallocated"
        live_payment_list = self._invoke_viewset(LivePaymentViewSet, "get", "list", payment_path)
        staged_payment_list = self._invoke_viewset(StagedPaymentViewSet, "get", "list", payment_path)
        self.assertEqual(staged_payment_list.status_code, live_payment_list.status_code)
        self.assertEqual(staged_payment_list.data, live_payment_list.data)
        self.assertEqual(live_payment_list.data["results"][0]["receipt_no"], payment.receipt_number)
        self.assertEqual(live_payment_list.data["results"][0]["transaction_code"], payment.reference_number)
        self.assertEqual(live_payment_list.data["results"][0]["vote_head_summary"], vote_head.name)
        self.assertEqual(live_payment_list.data["results"][0]["status"], "Active")
        self.assertTrue(live_payment_list.data["results"][0]["created_at"])

    def test_staged_invoice_create_and_issue_match_live_contract(self):
        Invoice.objects.all().delete()
        payload = {
            "student": self.student.id,
            "term": self.term.id,
            "due_date": "2026-04-30",
            "line_items": [
                {
                    "fee_structure": self.fee_structure.id,
                    "amount": "15000.00",
                    "description": "Term tuition",
                }
            ],
        }

        live_create = self._invoke_viewset(LiveInvoiceViewSet, "post", "create", "/api/finance/invoices/", data=payload)
        Invoice.objects.all().delete()
        staged_create = self._invoke_viewset(StagedInvoiceViewSet, "post", "create", "/api/finance/invoices/", data=payload)

        self.assertEqual(staged_create.status_code, live_create.status_code)
        if live_create.status_code < 400:
            self.assertEqual(
                self._normalize_invoice_payload(staged_create.data),
                self._normalize_invoice_payload(live_create.data),
            )
        else:
            self.assertEqual(staged_create.data, live_create.data)

        issue_invoice = Invoice.objects.create(
            student=self.student,
            term_id=self.term.id,
            due_date="2026-04-30",
            total_amount=Decimal("8000.00"),
            status="DRAFT",
            is_active=True,
        )
        issue_path = f"/api/finance/invoices/{issue_invoice.id}/issue/"
        live_issue = self._invoke_viewset(LiveInvoiceViewSet, "post", "issue", issue_path, pk=issue_invoice.id)
        issue_invoice.refresh_from_db()
        issue_invoice.status = "DRAFT"
        issue_invoice.save(update_fields=["status"])
        staged_issue = self._invoke_viewset(StagedInvoiceViewSet, "post", "issue", issue_path, pk=issue_invoice.id)

        self.assertEqual(staged_issue.status_code, live_issue.status_code)
        self.assertEqual(staged_issue.data, live_issue.data)

    def test_staged_payment_create_and_allocate_match_live_contract(self):
        Payment.objects.all().delete()
        payload = {
            "student": self.student.id,
            "amount": "4000.00",
            "payment_method": "BANK",
            "reference_number": "PAY-CRT-001",
            "notes": "New payment",
        }

        live_create = self._invoke_viewset(LivePaymentViewSet, "post", "create", "/api/finance/payments/", data=payload)
        Payment.objects.all().delete()
        staged_create = self._invoke_viewset(StagedPaymentViewSet, "post", "create", "/api/finance/payments/", data=payload)

        self.assertEqual(staged_create.status_code, live_create.status_code)
        if live_create.status_code < 400:
            self.assertEqual(
                self._normalize_payment_payload(staged_create.data),
                self._normalize_payment_payload(live_create.data),
            )
        else:
            self.assertEqual(staged_create.data, live_create.data)

        allocation_invoice = Invoice.objects.create(
            student=self.student,
            term_id=self.term.id,
            due_date="2026-04-30",
            total_amount=Decimal("6000.00"),
            status="ISSUED",
            is_active=True,
        )
        allocation_payment = Payment.objects.create(
            student=self.student,
            amount=Decimal("6000.00"),
            payment_method="BANK",
            reference_number="ALLOC-001",
            notes="Allocation test",
            is_active=True,
        )
        allocate_payload = {"invoice_id": allocation_invoice.id, "amount": "2000.00"}
        allocate_path = f"/api/finance/payments/{allocation_payment.id}/allocate/"

        live_allocate = self._invoke_viewset(
            LivePaymentViewSet,
            "post",
            "allocate",
            allocate_path,
            data=allocate_payload,
            pk=allocation_payment.id,
        )
        self.assertEqual(PaymentAllocation.objects.count(), 1)
        PaymentAllocation.objects.all().delete()
        allocation_invoice.status = "ISSUED"
        allocation_invoice.save(update_fields=["status"])

        staged_allocate = self._invoke_viewset(
            StagedPaymentViewSet,
            "post",
            "allocate",
            allocate_path,
            data=allocate_payload,
            pk=allocation_payment.id,
        )
        self.assertEqual(staged_allocate.status_code, live_allocate.status_code)
        self.assertEqual(staged_allocate.data, live_allocate.data)
        self.assertEqual(PaymentAllocation.objects.count(), 1)

    def test_staged_payment_artifacts_and_student_ledger_match_live_contract(self):
        ledger_invoice = Invoice.objects.create(
            student=self.student,
            term_id=self.term.id,
            due_date="2026-04-30",
            total_amount=Decimal("9000.00"),
            status="ISSUED",
            is_active=True,
        )
        ledger_payment = Payment.objects.create(
            student=self.student,
            amount=Decimal("3000.00"),
            payment_method="BANK",
            reference_number="LEDGER-001",
            notes="Ledger payment",
            is_active=True,
        )
        PaymentAllocation.objects.create(
            payment=ledger_payment,
            invoice=ledger_invoice,
            amount_allocated=Decimal("3000.00"),
        )
        vote_head = VoteHead.objects.create(
            name="Receipt Test Vote Head",
            description="Receipt test vote head",
        )
        VoteHeadPaymentAllocation.objects.create(
            payment=ledger_payment,
            vote_head=vote_head,
            amount=Decimal("3000.00"),
        )

        receipt_path = f"/api/finance/payments/{ledger_payment.id}/receipt/"
        live_receipt = self._invoke_viewset(LivePaymentViewSet, "get", "receipt", receipt_path, pk=ledger_payment.id)
        staged_receipt = self._invoke_viewset(StagedPaymentViewSet, "get", "receipt", receipt_path, pk=ledger_payment.id)
        self.assertEqual(staged_receipt.status_code, live_receipt.status_code)
        self.assertEqual(staged_receipt["Content-Type"], live_receipt["Content-Type"])
        self.assertEqual(staged_receipt["Content-Disposition"], live_receipt["Content-Disposition"])
        self.assertEqual(staged_receipt.content, live_receipt.content)

        receipt_json_path = f"/api/finance/payments/{ledger_payment.id}/receipt/?format=json"
        live_receipt_json = self._invoke_viewset(
            LivePaymentViewSet,
            "get",
            "receipt",
            receipt_json_path,
            pk=ledger_payment.id,
        )
        staged_receipt_json = self._invoke_viewset(
            StagedPaymentViewSet,
            "get",
            "receipt",
            receipt_json_path,
            pk=ledger_payment.id,
        )
        self.assertEqual(staged_receipt_json.status_code, live_receipt_json.status_code)
        self.assertEqual(staged_receipt_json.data, live_receipt_json.data)
        self.assertEqual(live_receipt_json.data["receipt_no"], ledger_payment.receipt_number)
        self.assertEqual(live_receipt_json.data["transaction_code"], ledger_payment.reference_number)
        self.assertEqual(live_receipt_json.data["vote_head_summary"], vote_head.name)
        self.assertEqual(live_receipt_json.data["student"], f"{self.student.first_name} {self.student.last_name}".strip())
        self.assertEqual(live_receipt_json.data["admission_number"], self.student.admission_number)
        self.assertEqual(str(live_receipt_json.data["amount"]), str(ledger_payment.amount))
        self.assertEqual(live_receipt_json.data["method"], ledger_payment.payment_method)
        self.assertEqual(live_receipt_json.data["status"], "Active")
        self.assertTrue(live_receipt_json.data["receipt_json_url"].endswith(receipt_json_path))
        self.assertTrue(live_receipt_json.data["receipt_pdf_url"].endswith(f"/api/finance/payments/{ledger_payment.id}/receipt/pdf/"))
        self.assertEqual(len(live_receipt_json.data["allocations"]), 1)
        self.assertEqual(len(live_receipt_json.data["vote_head_allocations"]), 1)
        self.assertEqual(live_receipt_json.data["vote_head_allocations"][0]["vote_head"], vote_head.name)

        pdf_path = f"/api/finance/payments/{ledger_payment.id}/receipt/pdf/"
        live_pdf = self._invoke_api_view(LiveFinanceReceiptPdfView, "get", pdf_path, pk=ledger_payment.id)
        staged_pdf = self._invoke_api_view(StagedFinanceReceiptPdfView, "get", pdf_path, pk=ledger_payment.id)
        self.assertEqual(staged_pdf.status_code, live_pdf.status_code)
        self.assertEqual(staged_pdf["Content-Type"], live_pdf["Content-Type"])
        self.assertEqual(staged_pdf["Content-Disposition"], live_pdf["Content-Disposition"])
        self.assertTrue(live_pdf.content.startswith(b"%PDF"))
        self.assertEqual(staged_pdf.content[:4], live_pdf.content[:4])

        ledger_path = f"/api/finance/students/{self.student.id}/ledger/?term={self.term.id}"
        live_ledger = self._invoke_api_view(
            LiveFinanceStudentLedgerView,
            "get",
            ledger_path,
            student_id=self.student.id,
        )
        staged_ledger = self._invoke_api_view(
            StagedFinanceStudentLedgerView,
            "get",
            ledger_path,
            student_id=self.student.id,
        )
        self.assertEqual(staged_ledger.status_code, live_ledger.status_code)
        self.assertEqual(staged_ledger.data, live_ledger.data)

    def test_record_payment_emits_sms_audit_trail(self):
        guardian = Guardian.objects.create(
            student=self.student,
            name="Grace Njeri",
            relationship="Mother",
            phone="0712345678",
            email="grace@example.com",
            is_active=True,
        )

        payment = FinanceService.record_payment(
            student=self.student,
            amount=Decimal("2500.00"),
            payment_method="CASH",
            reference_number="SMS-001",
            notes="SMS trail test",
        )

        sms_message = SmsMessage.objects.get()
        self.assertEqual(sms_message.recipient_phone, guardian.phone)
        self.assertEqual(sms_message.channel, "SMS")
        self.assertIn(payment.receipt_number, sms_message.message)
        self.assertIn(self.student.admission_number, sms_message.message)
        self.assertIn("KES 2,500.00", sms_message.message)
        self.assertIn("SMS-001", sms_message.message)
        self.assertIn(sms_message.status, {"Queued", "Sent", "Delivered", "Failed"})

    def test_record_payment_is_idempotent_for_duplicate_reference(self):
        Guardian.objects.create(
            student=self.student,
            name="Grace Njeri",
            relationship="Mother",
            phone="0712345678",
            email="grace@example.com",
            is_active=True,
        )

        first_payment = FinanceService.record_payment(
            student=self.student,
            amount=Decimal("2500.00"),
            payment_method="CASH",
            reference_number="SMS-002",
            notes="Duplicate reference test",
        )
        second_payment = FinanceService.record_payment(
            student=self.student,
            amount=Decimal("2500.00"),
            payment_method="CASH",
            reference_number="SMS-002",
            notes="Duplicate reference test",
        )

        self.assertEqual(first_payment.id, second_payment.id)
        self.assertFalse(getattr(second_payment, "_was_created", True))
        self.assertEqual(Payment.objects.filter(reference_number="SMS-002").count(), 1)
        self.assertEqual(SmsMessage.objects.filter(message__icontains="SMS-002").count(), 1)

    def test_staged_invoice_adjustment_create_matches_live_contract(self):
        adjustment_invoice = Invoice.objects.create(
            student=self.student,
            term_id=self.term.id,
            due_date="2026-04-30",
            total_amount=Decimal("5000.00"),
            status="ISSUED",
            is_active=True,
        )
        payload = {
            "invoice": adjustment_invoice.id,
            "adjustment_type": "CREDIT",
            "amount": "500.00",
            "reason": "Scholarship adjustment",
        }

        live_create = self._invoke_viewset(
            LiveInvoiceAdjustmentViewSet,
            "post",
            "create",
            "/api/finance/invoice-adjustments/",
            data=payload,
        )
        InvoiceAdjustment.objects.all().delete()

        staged_create = self._invoke_viewset(
            StagedInvoiceAdjustmentViewSet,
            "post",
            "create",
            "/api/finance/invoice-adjustments/",
            data=payload,
        )
        self.assertEqual(staged_create.status_code, live_create.status_code)
        if live_create.status_code < 400:
            self.assertEqual(
                self._normalize_adjustment_payload(staged_create.data),
                self._normalize_adjustment_payload(live_create.data),
            )
        else:
            self.assertEqual(staged_create.data, live_create.data)

    def test_staged_reversal_and_writeoff_request_create_match_live_contract(self):
        reversal_payment = Payment.objects.create(
            student=self.student,
            amount=Decimal("2500.00"),
            payment_method="CASH",
            reference_number="REV-001",
            notes="Reversal request seed",
            is_active=True,
        )
        reversal_payload = {
            "payment": reversal_payment.id,
            "reason": "Duplicate payment captured",
        }
        live_reversal = self._invoke_viewset(
            LivePaymentReversalRequestViewSet,
            "post",
            "create",
            "/api/finance/payment-reversals/",
            data=reversal_payload,
        )
        PaymentReversalRequest.objects.all().delete()

        staged_reversal = self._invoke_viewset(
            StagedPaymentReversalRequestViewSet,
            "post",
            "create",
            "/api/finance/payment-reversals/",
            data=reversal_payload,
        )
        self.assertEqual(staged_reversal.status_code, live_reversal.status_code)
        if live_reversal.status_code < 400:
            self.assertEqual(
                self._normalize_reversal_payload(staged_reversal.data),
                self._normalize_reversal_payload(live_reversal.data),
            )
        else:
            self.assertEqual(staged_reversal.data, live_reversal.data)

        writeoff_invoice = Invoice.objects.create(
            student=self.student,
            term_id=self.term.id,
            due_date="2026-04-30",
            total_amount=Decimal("7000.00"),
            status="ISSUED",
            is_active=True,
        )
        writeoff_payload = {
            "invoice": writeoff_invoice.id,
            "amount": "700.00",
            "reason": "Approved hardship relief",
        }
        live_writeoff = self._invoke_viewset(
            LiveInvoiceWriteOffRequestViewSet,
            "post",
            "create",
            "/api/finance/write-offs/",
            data=writeoff_payload,
        )
        InvoiceWriteOffRequest.objects.all().delete()

        staged_writeoff = self._invoke_viewset(
            StagedInvoiceWriteOffRequestViewSet,
            "post",
            "create",
            "/api/finance/write-offs/",
            data=writeoff_payload,
        )
        self.assertEqual(staged_writeoff.status_code, live_writeoff.status_code)
        if live_writeoff.status_code < 400:
            self.assertEqual(
                self._normalize_writeoff_payload(staged_writeoff.data),
                self._normalize_writeoff_payload(live_writeoff.data),
            )
        else:
            self.assertEqual(staged_writeoff.data, live_writeoff.data)
