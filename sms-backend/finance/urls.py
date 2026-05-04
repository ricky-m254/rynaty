"""
Staged finance URLConf.

Live tenant routing is mounted through `school.urls`, which re-exports the
finance presentation views on the production `/api/finance/*` surface.
This module stays importable for staged parity checks and direct inspection,
but it is intentionally not mounted in `config.urls` to avoid duplicate routes.
"""

from django.urls import path
from rest_framework.routers import SimpleRouter

from finance.presentation.views import (
    BulkFeeAssignByClassView,
    BulkOptionalChargeByClassView,
    CashbookSummaryView,
    FinanceArrearsByTermReportView,
    FinanceArrearsView,
    FinanceBudgetVarianceReportView,
    FinanceClassRefView,
    FinanceClassBalancesReportView,
    FinanceEnrollmentRefView,
    FinanceInstallmentAgingView,
    FinanceOverdueAccountsView,
    FinanceOverdueAccountsCsvExportView,
    FinanceReceiptPdfView,
    FinanceReceivablesAgingView,
    FinanceReceivablesAgingCsvExportView,
    FinanceStudentDetailView,
    FinanceStudentRefView,
    FinanceStudentLedgerView,
    FinanceSummaryCsvExportView,
    FinanceSummaryPdfExportView,
    FinanceVoteHeadAllocationReportView,
    FinanceVoteHeadBudgetReportView,
    FinancialSummaryView,
)
from finance.presentation.accounting_views import (
    AccountingLedgerView,
    AccountingTrialBalanceView,
)
from finance.presentation.accounting_viewsets import (
    AccountingPeriodViewSet,
    ChartOfAccountViewSet,
    JournalEntryViewSet,
)
from finance.presentation.collection_ops_views import FinanceGatewayWebhookView
from finance.presentation.collection_ops_viewsets import (
    BankStatementLineViewSet,
    FeeReminderLogViewSet,
    LateFeeRuleViewSet,
    PaymentGatewayTransactionViewSet,
    PaymentGatewayWebhookEventViewSet,
)
from finance.presentation.governance_viewsets import (
    BudgetViewSet,
    ExpenseViewSet,
    ScholarshipAwardViewSet,
    TermViewSet,
    VoteHeadPaymentAllocationViewSet,
)
from finance.presentation.viewsets import (
    BalanceCarryForwardViewSet,
    CashbookEntryViewSet,
    FeeAssignmentViewSet,
    FeeStructureViewSet,
    InvoiceAdjustmentViewSet,
    InvoiceViewSet,
    InvoiceWriteOffRequestViewSet,
    OptionalChargeViewSet,
    PaymentReversalRequestViewSet,
    PaymentViewSet,
    StudentOptionalChargeViewSet,
    VoteHeadViewSet,
)


router = SimpleRouter()
router.register("fees", FeeStructureViewSet, basename="feestructure")
router.register("fee-assignments", FeeAssignmentViewSet, basename="feeassignment")
router.register("optional-charges", OptionalChargeViewSet, basename="optional-charge")
router.register("student-optional-charges", StudentOptionalChargeViewSet, basename="student-optional-charge")
router.register("invoice-adjustments", InvoiceAdjustmentViewSet, basename="invoiceadjustment")
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("payments", PaymentViewSet, basename="payment")
router.register("payment-reversals", PaymentReversalRequestViewSet, basename="payment-reversal")
router.register("write-offs", InvoiceWriteOffRequestViewSet, basename="invoice-writeoff-request")
router.register("cashbook", CashbookEntryViewSet, basename="cashbook-entry")
router.register("carry-forwards", BalanceCarryForwardViewSet, basename="carry-forward")
router.register("vote-heads", VoteHeadViewSet, basename="vote-head")
router.register("terms", TermViewSet, basename="term")
router.register("scholarships", ScholarshipAwardViewSet, basename="scholarshipaward")
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("budgets", BudgetViewSet, basename="budget")
router.register("gateway/transactions", PaymentGatewayTransactionViewSet, basename="payment-gateway-transaction")
router.register("gateway/events", PaymentGatewayWebhookEventViewSet, basename="payment-gateway-event")
router.register("reconciliation/bank-lines", BankStatementLineViewSet, basename="bank-statement-line")
router.register("late-fee-rules", LateFeeRuleViewSet, basename="late-fee-rule")
router.register("reminders", FeeReminderLogViewSet, basename="fee-reminder")
router.register("accounting/periods", AccountingPeriodViewSet, basename="accounting-period")
router.register("accounting/accounts", ChartOfAccountViewSet, basename="accounting-account")
router.register("accounting/journals", JournalEntryViewSet, basename="accounting-journal")
router.register("vote-head-allocations", VoteHeadPaymentAllocationViewSet, basename="vote-head-allocation")


urlpatterns = [
    path("fee-assignments/by-class/", BulkFeeAssignByClassView.as_view(), name="fee_assign_by_class"),
    path("optional-charges/by-class/", BulkOptionalChargeByClassView.as_view(), name="optional_charge_by_class"),
    path("payments/<int:pk>/receipt/pdf/", FinanceReceiptPdfView.as_view(), name="finance_receipt_pdf"),
    path("students/<int:student_id>/ledger/", FinanceStudentLedgerView.as_view(), name="finance_student_ledger"),
    path("ref/students/", FinanceStudentRefView.as_view(), name="finance_ref_students"),
    path("ref/enrollments/", FinanceEnrollmentRefView.as_view(), name="finance_ref_enrollments"),
    path("ref/classes/", FinanceClassRefView.as_view(), name="finance_ref_classes"),
    path("summary/", FinancialSummaryView.as_view(), name="financial_summary"),
    path("cashbook/summary/", CashbookSummaryView.as_view(), name="finance_cashbook_summary"),
    path("reports/receivables-aging/", FinanceReceivablesAgingView.as_view(), name="finance_receivables_aging"),
    path("reports/installments-aging/", FinanceInstallmentAgingView.as_view(), name="finance_installments_aging"),
    path("reports/overdue-accounts/", FinanceOverdueAccountsView.as_view(), name="finance_overdue_accounts"),
    path(
        "reports/receivables-aging/export/csv/",
        FinanceReceivablesAgingCsvExportView.as_view(),
        name="finance_receivables_aging_csv",
    ),
    path(
        "reports/overdue-accounts/export/csv/",
        FinanceOverdueAccountsCsvExportView.as_view(),
        name="finance_overdue_accounts_csv",
    ),
    path("reports/summary/export/csv/", FinanceSummaryCsvExportView.as_view(), name="finance_reports_summary_csv"),
    path("reports/summary/export/pdf/", FinanceSummaryPdfExportView.as_view(), name="finance_reports_summary_pdf"),
    path(
        "reports/vote-head-allocation/",
        FinanceVoteHeadAllocationReportView.as_view(),
        name="finance_vote_head_allocation_report",
    ),
    path("reports/arrears/", FinanceArrearsView.as_view(), name="finance_arrears_report"),
    path("reports/class-balances/", FinanceClassBalancesReportView.as_view(), name="finance_class_balances_report"),
    path("reports/arrears-by-term/", FinanceArrearsByTermReportView.as_view(), name="finance_arrears_by_term_report"),
    path("reports/budget-variance/", FinanceBudgetVarianceReportView.as_view(), name="finance_budget_variance_report"),
    path(
        "reports/vote-head-budget/",
        FinanceVoteHeadBudgetReportView.as_view(),
        name="finance_vote_head_budget_report",
    ),
    path("accounting/trial-balance/", AccountingTrialBalanceView.as_view(), name="finance_accounting_trial_balance"),
    path("accounting/ledger/", AccountingLedgerView.as_view(), name="finance_accounting_ledger"),
    path("students/<int:student_id>/", FinanceStudentDetailView.as_view(), name="finance_student_detail"),
    path("gateway/webhooks/<str:provider>/", FinanceGatewayWebhookView.as_view(), name="finance_gateway_webhook"),
] + router.urls
