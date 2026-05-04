from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicYear, Term
from clients.models import Domain, Tenant
from finance.presentation.views import (
    CashbookSummaryView as StagedCashbookSummaryView,
    FinanceArrearsByTermReportView as StagedFinanceArrearsByTermReportView,
    FinanceArrearsView as StagedFinanceArrearsView,
    FinanceBudgetVarianceReportView as StagedFinanceBudgetVarianceReportView,
    FinanceClassBalancesReportView as StagedFinanceClassBalancesReportView,
    FinanceInstallmentAgingView as StagedFinanceInstallmentAgingView,
    FinanceOverdueAccountsCsvExportView as StagedFinanceOverdueAccountsCsvExportView,
    FinanceOverdueAccountsView as StagedFinanceOverdueAccountsView,
    FinanceReceivablesAgingCsvExportView as StagedFinanceReceivablesAgingCsvExportView,
    FinanceReceivablesAgingView as StagedFinanceReceivablesAgingView,
    FinanceSummaryCsvExportView as StagedFinanceSummaryCsvExportView,
    FinanceSummaryPdfExportView as StagedFinanceSummaryPdfExportView,
    FinanceVoteHeadAllocationReportView as StagedFinanceVoteHeadAllocationReportView,
    FinanceVoteHeadBudgetReportView as StagedFinanceVoteHeadBudgetReportView,
    FinancialSummaryView as StagedFinancialSummaryView,
)
from school.models import (
    Budget,
    CashbookEntry,
    Enrollment,
    Expense,
    Invoice,
    InvoiceInstallment,
    InvoiceInstallmentPlan,
    Module,
    Payment,
    Role,
    SchoolClass,
    Student,
    UserModuleAssignment,
    UserProfile,
    VoteHead,
    VoteHeadPaymentAllocation,
)
from school.views import (
    CashbookSummaryView as LiveCashbookSummaryView,
    FinanceArrearsByTermReportView as LiveFinanceArrearsByTermReportView,
    FinanceArrearsView as LiveFinanceArrearsView,
    FinanceBudgetVarianceReportView as LiveFinanceBudgetVarianceReportView,
    FinanceClassBalancesReportView as LiveFinanceClassBalancesReportView,
    FinanceInstallmentAgingView as LiveFinanceInstallmentAgingView,
    FinanceOverdueAccountsCsvExportView as LiveFinanceOverdueAccountsCsvExportView,
    FinanceOverdueAccountsView as LiveFinanceOverdueAccountsView,
    FinanceReceivablesAgingCsvExportView as LiveFinanceReceivablesAgingCsvExportView,
    FinanceReceivablesAgingView as LiveFinanceReceivablesAgingView,
    FinanceSummaryCsvExportView as LiveFinanceSummaryCsvExportView,
    FinanceSummaryPdfExportView as LiveFinanceSummaryPdfExportView,
    FinanceVoteHeadAllocationReportView as LiveFinanceVoteHeadAllocationReportView,
    FinancialSummaryView as LiveFinancialSummaryView,
    VoteHeadBudgetReportView as LiveFinanceVoteHeadBudgetReportView,
)


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="finance_phase6_reports_test",
                defaults={
                    "name": "Finance Phase 6 Reports Test School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="finance-phase6-reports.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class FinanceReportActivationPrepTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="finance_phase6_reports_user", password="pass1234")
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
        self.other_term = Term.objects.create(
            academic_year=self.year,
            name="Term 2",
            start_date="2026-05-01",
            end_date="2026-08-31",
            is_active=True,
        )

        today = timezone.now().date()
        self.student_one = Student.objects.create(
            admission_number="FRP-001",
            first_name="Alice",
            last_name="Mumo",
            gender="F",
            date_of_birth="2011-01-01",
            is_active=True,
        )
        self.student_two = Student.objects.create(
            admission_number="FRP-002",
            first_name="Brian",
            last_name="Otieno",
            gender="M",
            date_of_birth="2011-01-02",
            is_active=True,
        )
        self.student_three = Student.objects.create(
            admission_number="FRP-003",
            first_name="Caro",
            last_name="Wanjiku",
            gender="F",
            date_of_birth="2011-01-03",
            is_active=True,
        )
        self.class_a = SchoolClass.objects.create(
            name="Grade 7",
            stream="A",
            academic_year_id=self.year.id,
            is_active=True,
        )
        self.class_b = SchoolClass.objects.create(
            name="Grade 8",
            stream="B",
            academic_year_id=self.year.id,
            is_active=True,
        )
        Enrollment.objects.create(
            student=self.student_one,
            school_class_id=self.class_a.id,
            term_id=self.term.id,
            status="Active",
            is_active=True,
        )
        Enrollment.objects.create(
            student=self.student_two,
            school_class_id=self.class_b.id,
            term_id=self.term.id,
            status="Active",
            is_active=True,
        )
        Enrollment.objects.create(
            student=self.student_three,
            school_class_id=self.class_a.id,
            term_id=self.other_term.id,
            status="Active",
            is_active=True,
        )

        self.invoice_recent = Invoice.objects.create(
            student=self.student_one,
            term_id=self.term.id,
            due_date=today - timedelta(days=10),
            total_amount=Decimal("100.00"),
            status="ISSUED",
            is_active=True,
        )
        self.invoice_older = Invoice.objects.create(
            student=self.student_two,
            term_id=self.term.id,
            due_date=today - timedelta(days=45),
            total_amount=Decimal("250.00"),
            status="ISSUED",
            is_active=True,
        )
        self.invoice_future = Invoice.objects.create(
            student=self.student_three,
            term_id=self.term.id,
            due_date=today + timedelta(days=5),
            total_amount=Decimal("150.00"),
            status="CONFIRMED",
            is_active=True,
        )
        Invoice.objects.create(
            student=self.student_three,
            term_id=self.term.id,
            due_date=today - timedelta(days=80),
            total_amount=Decimal("999.00"),
            status="VOID",
            is_active=True,
        )
        Invoice.objects.create(
            student=self.student_three,
            term_id=self.other_term.id,
            due_date=today - timedelta(days=20),
            total_amount=Decimal("80.00"),
            status="ISSUED",
            is_active=True,
        )

        Budget.objects.create(
            academic_year_id=self.year.id,
            term_id=self.term.id,
            name="General Budget",
            monthly_budget=Decimal("1000.00"),
            quarterly_budget=Decimal("3000.00"),
            annual_budget=Decimal("12000.00"),
            is_active=True,
        )
        self.expense_one = Expense.objects.create(
            category="Utilities",
            amount=Decimal("150.00"),
            expense_date=today - timedelta(days=3),
            vendor="Power Co",
            payment_method="Bank",
            invoice_number="EXP-001",
            approval_status="Approved",
            description="Electricity",
            is_active=True,
        )
        self.expense_two = Expense.objects.create(
            category="Supplies",
            amount=Decimal("200.00"),
            expense_date=today - timedelta(days=7),
            vendor="Stationers",
            payment_method="Cash",
            invoice_number="EXP-002",
            approval_status="Approved",
            description="Stationery",
            is_active=True,
        )
        self.payment_one = Payment.objects.create(
            student=self.student_one,
            amount=Decimal("90.00"),
            payment_method="Cash",
            reference_number="PAY-P6-RPT-001",
            notes="Phase 6 report parity payment one",
            is_active=True,
        )
        self.payment_two = Payment.objects.create(
            student=self.student_two,
            amount=Decimal("110.00"),
            payment_method="Bank Transfer",
            reference_number="PAY-P6-RPT-002",
            notes="Phase 6 report parity payment two",
            is_active=True,
        )
        payment_one_datetime = timezone.now() - timedelta(days=2)
        payment_two_datetime = timezone.now() - timedelta(days=15)
        Payment.objects.filter(pk=self.payment_one.pk).update(payment_date=payment_one_datetime)
        Payment.objects.filter(pk=self.payment_two.pk).update(payment_date=payment_two_datetime)
        self.payment_one.refresh_from_db()
        self.payment_two.refresh_from_db()

        self.vote_head_tuition = VoteHead.objects.create(
            name="Tuition",
            allocation_percentage=Decimal("50.00"),
            order=1,
            is_active=True,
        )
        self.vote_head_transport = VoteHead.objects.create(
            name="Transport",
            allocation_percentage=Decimal("30.00"),
            order=2,
            is_active=True,
        )
        self.vote_head_activity = VoteHead.objects.create(
            name="Activity",
            allocation_percentage=Decimal("20.00"),
            order=3,
            is_active=True,
        )
        VoteHeadPaymentAllocation.objects.create(
            payment=self.payment_one,
            vote_head=self.vote_head_tuition,
            amount=Decimal("60.00"),
        )
        VoteHeadPaymentAllocation.objects.create(
            payment=self.payment_one,
            vote_head=self.vote_head_transport,
            amount=Decimal("30.00"),
        )
        VoteHeadPaymentAllocation.objects.create(
            payment=self.payment_two,
            vote_head=self.vote_head_tuition,
            amount=Decimal("110.00"),
        )
        CashbookEntry.objects.create(
            book_type="CASH",
            entry_date=today - timedelta(days=20),
            entry_type="OPENING",
            reference="OPEN-CASH",
            description="Cash opening balance",
            amount_in=Decimal("100.00"),
            running_balance=Decimal("100.00"),
        )
        CashbookEntry.objects.create(
            book_type="CASH",
            entry_date=today - timedelta(days=2),
            entry_type="RECEIPT",
            reference=self.payment_one.receipt_number or self.payment_one.reference_number,
            description="Cash receipt",
            amount_in=Decimal("90.00"),
            running_balance=Decimal("190.00"),
            payment=self.payment_one,
        )
        CashbookEntry.objects.create(
            book_type="BANK",
            entry_date=today - timedelta(days=20),
            entry_type="OPENING",
            reference="OPEN-BANK",
            description="Bank opening balance",
            amount_in=Decimal("200.00"),
            running_balance=Decimal("200.00"),
        )
        CashbookEntry.objects.create(
            book_type="BANK",
            entry_date=today - timedelta(days=1),
            entry_type="EXPENSE",
            reference="BANK-EXP-001",
            description="Bank expense",
            amount_out=Decimal("70.00"),
            running_balance=Decimal("130.00"),
            expense=self.expense_one,
        )

        plan = InvoiceInstallmentPlan.objects.create(invoice=self.invoice_recent, installment_count=4)
        InvoiceInstallment.objects.create(
            plan=plan,
            sequence=1,
            due_date=today - timedelta(days=12),
            amount=Decimal("25.00"),
            status="PENDING",
        )
        InvoiceInstallment.objects.create(
            plan=plan,
            sequence=2,
            due_date=today - timedelta(days=52),
            amount=Decimal("25.00"),
            status="OVERDUE",
        )
        InvoiceInstallment.objects.create(
            plan=plan,
            sequence=3,
            due_date=today + timedelta(days=2),
            amount=Decimal("25.00"),
            status="PENDING",
        )
        InvoiceInstallment.objects.create(
            plan=plan,
            sequence=4,
            due_date=today - timedelta(days=100),
            amount=Decimal("25.00"),
            status="WAIVED",
        )

    def _invoke(self, view_class, path):
        request = self.factory.get(path)
        force_authenticate(request, user=self.user)
        return view_class.as_view()(request)

    def _assert_csv_contract_matches(self, live_response, staged_response):
        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.get("Content-Type"), live_response.get("Content-Type"))
        self.assertEqual(staged_response.get("Content-Disposition"), live_response.get("Content-Disposition"))
        self.assertEqual(staged_response.content, live_response.content)

    def _assert_pdf_contract_matches(self, live_response, staged_response):
        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.get("Content-Type"), live_response.get("Content-Type"))
        self.assertEqual(staged_response.get("Content-Disposition"), live_response.get("Content-Disposition"))
        self.assertGreater(len(live_response.content), 0)
        self.assertGreater(len(staged_response.content), 0)
        self.assertTrue(live_response.content.startswith(b"%PDF"))
        self.assertTrue(staged_response.content.startswith(b"%PDF"))

    def test_staged_finance_receivables_aging_matches_live_contract(self):
        path = "/api/finance/reports/receivables-aging/"
        live_response = self._invoke(LiveFinanceReceivablesAgingView, path)
        staged_response = self._invoke(StagedFinanceReceivablesAgingView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_overdue_accounts_matches_live_contract(self):
        path = "/api/finance/reports/overdue-accounts/"
        live_response = self._invoke(LiveFinanceOverdueAccountsView, path)
        staged_response = self._invoke(StagedFinanceOverdueAccountsView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_overdue_accounts_search_matches_live_contract(self):
        path = "/api/finance/reports/overdue-accounts/?search=FRP-002"
        live_response = self._invoke(LiveFinanceOverdueAccountsView, path)
        staged_response = self._invoke(StagedFinanceOverdueAccountsView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_installment_aging_matches_live_contract(self):
        path = "/api/finance/reports/installments-aging/"
        live_response = self._invoke(LiveFinanceInstallmentAgingView, path)
        staged_response = self._invoke(StagedFinanceInstallmentAgingView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_arrears_matches_live_contract(self):
        path = f"/api/finance/reports/arrears/?term={self.term.id}"
        live_response = self._invoke(LiveFinanceArrearsView, path)
        staged_response = self._invoke(StagedFinanceArrearsView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_arrears_grouped_by_class_matches_live_contract(self):
        path = f"/api/finance/reports/arrears/?term={self.term.id}&group_by=class"
        live_response = self._invoke(LiveFinanceArrearsView, path)
        staged_response = self._invoke(StagedFinanceArrearsView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_class_balances_matches_live_contract(self):
        path = f"/api/finance/reports/class-balances/?term={self.term.id}"
        live_response = self._invoke(LiveFinanceClassBalancesReportView, path)
        staged_response = self._invoke(StagedFinanceClassBalancesReportView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_arrears_by_term_matches_live_contract(self):
        path = "/api/finance/reports/arrears-by-term/"
        live_response = self._invoke(LiveFinanceArrearsByTermReportView, path)
        staged_response = self._invoke(StagedFinanceArrearsByTermReportView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_budget_variance_matches_live_contract(self):
        path = f"/api/finance/reports/budget-variance/?academic_year={self.year.id}&term={self.term.id}"
        live_response = self._invoke(LiveFinanceBudgetVarianceReportView, path)
        staged_response = self._invoke(StagedFinanceBudgetVarianceReportView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_financial_summary_matches_live_contract(self):
        path = "/api/finance/summary/"
        live_response = self._invoke(LiveFinancialSummaryView, path)
        staged_response = self._invoke(StagedFinancialSummaryView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_cashbook_summary_matches_live_contract(self):
        path = "/api/finance/cashbook/summary/"
        live_response = self._invoke(LiveCashbookSummaryView, path)
        staged_response = self._invoke(StagedCashbookSummaryView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_receivables_aging_csv_matches_live_contract(self):
        path = "/api/finance/reports/receivables-aging/export/csv/"
        live_response = self._invoke(LiveFinanceReceivablesAgingCsvExportView, path)
        staged_response = self._invoke(StagedFinanceReceivablesAgingCsvExportView, path)

        self._assert_csv_contract_matches(live_response, staged_response)

    def test_staged_finance_overdue_accounts_csv_matches_live_contract(self):
        path = "/api/finance/reports/overdue-accounts/export/csv/"
        live_response = self._invoke(LiveFinanceOverdueAccountsCsvExportView, path)
        staged_response = self._invoke(StagedFinanceOverdueAccountsCsvExportView, path)

        self._assert_csv_contract_matches(live_response, staged_response)

    def test_staged_finance_summary_csv_matches_live_contract(self):
        path = "/api/finance/reports/summary/export/csv/"
        live_response = self._invoke(LiveFinanceSummaryCsvExportView, path)
        staged_response = self._invoke(StagedFinanceSummaryCsvExportView, path)

        self._assert_csv_contract_matches(live_response, staged_response)

    def test_staged_finance_summary_pdf_matches_live_contract(self):
        path = "/api/finance/reports/summary/export/pdf/"
        live_response = self._invoke(LiveFinanceSummaryPdfExportView, path)
        staged_response = self._invoke(StagedFinanceSummaryPdfExportView, path)

        self._assert_pdf_contract_matches(live_response, staged_response)

    def test_staged_finance_vote_head_allocation_matches_live_contract(self):
        path = "/api/finance/reports/vote-head-allocation/"
        live_response = self._invoke(LiveFinanceVoteHeadAllocationReportView, path)
        staged_response = self._invoke(StagedFinanceVoteHeadAllocationReportView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_vote_head_allocation_filtered_matches_live_contract(self):
        path = (
            f"/api/finance/reports/vote-head-allocation/?date_from={self.payment_one.payment_date.date()}"
            f"&date_to={self.payment_one.payment_date.date()}"
        )
        live_response = self._invoke(LiveFinanceVoteHeadAllocationReportView, path)
        staged_response = self._invoke(StagedFinanceVoteHeadAllocationReportView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_vote_head_budget_matches_live_contract(self):
        path = "/api/finance/reports/vote-head-budget/"
        live_response = self._invoke(LiveFinanceVoteHeadBudgetReportView, path)
        staged_response = self._invoke(StagedFinanceVoteHeadBudgetReportView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_vote_head_budget_filtered_matches_live_contract(self):
        path = (
            f"/api/finance/reports/vote-head-budget/?date_from={self.payment_one.payment_date.date()}"
            f"&date_to={self.payment_one.payment_date.date()}"
        )
        live_response = self._invoke(LiveFinanceVoteHeadBudgetReportView, path)
        staged_response = self._invoke(StagedFinanceVoteHeadBudgetReportView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)
