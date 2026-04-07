import importlib.util

from django.test import SimpleTestCase
from django.urls import resolve

from finance import urls as staged_finance_urls
from school import urls as school_urls


class Phase6ArchitectureGuardrailTests(SimpleTestCase):
    def test_finance_reference_routes_now_cut_over_to_finance_presentation(self):
        self.assertIsNotNone(importlib.util.find_spec("finance.urls"))
        self.assertIsNotNone(importlib.util.find_spec("finance.presentation.views"))
        self.assertTrue(
            {
                "finance_ref_students",
                "finance_ref_enrollments",
                "finance_ref_classes",
            }.issubset(
                {pattern.name for pattern in staged_finance_urls.urlpatterns}
            )
        )

        students_match = resolve("/api/finance/ref/students/")
        enrollments_match = resolve("/api/finance/ref/enrollments/")
        classes_match = resolve("/api/finance/ref/classes/")

        self.assertEqual(students_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(enrollments_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(classes_match.func.view_class.__module__, "finance.presentation.views")

    def test_finance_report_route_owners_reflect_current_cutover_state(self):
        self.assertTrue(
            {
                "financial_summary",
                "finance_cashbook_summary",
                "finance_receivables_aging",
                "finance_installments_aging",
                "finance_overdue_accounts",
                "finance_vote_head_allocation_report",
                "finance_arrears_report",
                "finance_class_balances_report",
                "finance_arrears_by_term_report",
                "finance_budget_variance_report",
                "finance_vote_head_budget_report",
            }.issubset({pattern.name for pattern in staged_finance_urls.urlpatterns})
        )

        summary_match = resolve("/api/finance/summary/")
        cashbook_summary_match = resolve("/api/finance/cashbook/summary/")
        receivables_match = resolve("/api/finance/reports/receivables-aging/")
        overdue_match = resolve("/api/finance/reports/overdue-accounts/")
        installments_match = resolve("/api/finance/reports/installments-aging/")
        vote_head_allocation_match = resolve("/api/finance/reports/vote-head-allocation/")
        arrears_match = resolve("/api/finance/reports/arrears/")
        class_balances_match = resolve("/api/finance/reports/class-balances/")
        arrears_by_term_match = resolve("/api/finance/reports/arrears-by-term/")
        budget_variance_match = resolve("/api/finance/reports/budget-variance/")
        vote_head_budget_match = resolve("/api/finance/reports/vote-head-budget/")

        self.assertEqual(summary_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(cashbook_summary_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(receivables_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(overdue_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(installments_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(vote_head_allocation_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(arrears_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(class_balances_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(arrears_by_term_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(budget_variance_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(vote_head_budget_match.func.view_class.__module__, "finance.presentation.views")

    def test_router_registry_keeps_current_runtime_owner_modules_explicit(self):
        staged_registered = {
            prefix: viewset for prefix, viewset, _basename in staged_finance_urls.router.registry
        }
        registered = {prefix: viewset for prefix, viewset, _basename in school_urls.router.registry}

        self.assertEqual(staged_registered["cashbook"].__module__, "finance.presentation.viewsets")
        self.assertEqual(staged_registered["carry-forwards"].__module__, "finance.presentation.viewsets")
        self.assertEqual(staged_registered["fee-assignments"].__module__, "finance.presentation.viewsets")
        self.assertEqual(staged_registered["fees"].__module__, "finance.presentation.viewsets")
        self.assertEqual(staged_registered["invoice-adjustments"].__module__, "finance.presentation.viewsets")
        self.assertEqual(staged_registered["invoices"].__module__, "finance.presentation.viewsets")
        self.assertEqual(staged_registered["optional-charges"].__module__, "finance.presentation.viewsets")
        self.assertEqual(staged_registered["payment-reversals"].__module__, "finance.presentation.viewsets")
        self.assertEqual(staged_registered["payments"].__module__, "finance.presentation.viewsets")
        self.assertEqual(staged_registered["student-optional-charges"].__module__, "finance.presentation.viewsets")
        self.assertEqual(staged_registered["vote-heads"].__module__, "finance.presentation.viewsets")
        self.assertEqual(staged_registered["write-offs"].__module__, "finance.presentation.viewsets")
        self.assertEqual(staged_registered["terms"].__module__, "finance.presentation.governance_viewsets")
        self.assertEqual(staged_registered["terms"].module_key, "FINANCE")
        self.assertEqual(
            [permission.__name__ for permission in staged_registered["terms"].permission_classes],
            ["IsAccountant", "HasModuleAccess"],
        )
        self.assertEqual(staged_registered["scholarships"].__module__, "finance.presentation.governance_viewsets")
        self.assertEqual(staged_registered["expenses"].__module__, "finance.presentation.governance_viewsets")
        self.assertEqual(staged_registered["budgets"].__module__, "finance.presentation.governance_viewsets")
        self.assertEqual(staged_registered["vote-head-allocations"].__module__, "finance.presentation.governance_viewsets")
        self.assertEqual(staged_registered["gateway/transactions"].__module__, "finance.presentation.collection_ops_viewsets")
        self.assertEqual(staged_registered["gateway/events"].__module__, "finance.presentation.collection_ops_viewsets")
        self.assertEqual(staged_registered["reconciliation/bank-lines"].__module__, "finance.presentation.collection_ops_viewsets")
        self.assertEqual(staged_registered["late-fee-rules"].__module__, "finance.presentation.collection_ops_viewsets")
        self.assertEqual(staged_registered["reminders"].__module__, "finance.presentation.collection_ops_viewsets")
        self.assertEqual(staged_registered["accounting/periods"].__module__, "finance.presentation.accounting_viewsets")
        self.assertEqual(staged_registered["accounting/accounts"].__module__, "finance.presentation.accounting_viewsets")
        self.assertEqual(staged_registered["accounting/journals"].__module__, "finance.presentation.accounting_viewsets")

        for prefix in [
            "finance/cashbook",
            "finance/carry-forwards",
            "finance/fee-assignments",
            "finance/fees",
            "finance/invoice-adjustments",
            "finance/invoices",
            "finance/optional-charges",
            "finance/payment-reversals",
            "finance/payments",
            "finance/student-optional-charges",
            "finance/vote-heads",
            "finance/write-offs",
        ]:
            self.assertEqual(registered[prefix].__module__, "finance.presentation.viewsets")

        self.assertEqual(registered["finance/budgets"].__module__, "finance.presentation.governance_viewsets")
        self.assertEqual(registered["finance/accounting/periods"].__module__, "finance.presentation.accounting_viewsets")
        self.assertEqual(registered["finance/accounting/accounts"].__module__, "finance.presentation.accounting_viewsets")
        self.assertEqual(registered["finance/accounting/journals"].__module__, "finance.presentation.accounting_viewsets")

        for prefix in [
            "finance/terms",
            "finance/scholarships",
            "finance/expenses",
            "finance/gateway/transactions",
            "finance/gateway/events",
            "finance/reconciliation/bank-lines",
            "finance/late-fee-rules",
            "finance/reminders",
            "finance/vote-head-allocations",
            "dispensary/visits",
            "dispensary/stock",
        ]:
            self.assertEqual(registered[prefix].__module__, "school.views")

        self.assertEqual(registered["finance/terms"].module_key, "ACADEMICS")
        self.assertEqual(
            [permission.__name__ for permission in registered["finance/terms"].permission_classes],
            ["IsSchoolAdmin", "HasModuleAccess"],
        )

        for prefix in [
            "store/categories",
            "store/items",
            "store/orders",
            "store/transactions",
        ]:
            self.assertEqual(registered[prefix].__module__, "domains.inventory.presentation.views")

    def test_summary_and_dashboard_routes_resolve_to_expected_owner_modules(self):
        finance_match = resolve("/api/finance/summary/")
        fee_assign_by_class_match = resolve("/api/finance/fee-assignments/by-class/")
        optional_charge_by_class_match = resolve("/api/finance/optional-charges/by-class/")
        finance_receipt_pdf_match = resolve("/api/finance/payments/1/receipt/pdf/")
        finance_student_ledger_match = resolve("/api/finance/students/1/ledger/")
        store_match = resolve("/api/store/dashboard/")
        store_reports_match = resolve("/api/store/reports/")
        dispensary_match = resolve("/api/dispensary/dashboard/")

        self.assertEqual(finance_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(fee_assign_by_class_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(optional_charge_by_class_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(finance_receipt_pdf_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(finance_student_ledger_match.func.view_class.__module__, "finance.presentation.views")
        self.assertEqual(store_match.func.view_class.__module__, "domains.inventory.presentation.views")
        self.assertEqual(store_reports_match.func.view_class.__module__, "domains.inventory.presentation.views")
        self.assertEqual(dispensary_match.func.view_class.__module__, "school.views")

    def test_reporting_routes_remain_owned_by_reporting_module_boundary(self):
        reporting_ref_match = resolve("/api/reporting/ref/audit-logs/")
        reporting_list_match = resolve("/api/reporting/audit-logs/")

        self.assertEqual(reporting_ref_match.func.view_class.__module__, "reporting.views")
        self.assertEqual(reporting_list_match.func.cls.__module__, "reporting.views")

    def test_accounting_paths_reflect_current_cutover_state_while_webhook_stays_school_owned(self):
        self.assertTrue(
            {
                "finance_accounting_trial_balance",
                "finance_accounting_ledger",
                "finance_gateway_webhook",
            }.issubset({pattern.name for pattern in staged_finance_urls.urlpatterns})
        )

        trial_balance_match = resolve("/api/finance/accounting/trial-balance/")
        ledger_match = resolve("/api/finance/accounting/ledger/")
        webhook_match = resolve("/api/finance/gateway/webhooks/mpesa/")

        self.assertEqual(trial_balance_match.func.view_class.__module__, "finance.presentation.accounting_views")
        self.assertEqual(ledger_match.func.view_class.__module__, "finance.presentation.accounting_views")
        self.assertEqual(webhook_match.func.view_class.__module__, "school.views")

    def test_portal_route_prefixes_remain_backed_by_parent_portal_package(self):
        parent_match = resolve("/api/parent-portal/dashboard/")
        student_match = resolve("/api/student-portal/dashboard/")
        teacher_match = resolve("/api/teacher-portal/dashboard/")
        legacy_student_match = resolve("/api/portal/my-invoices/")

        self.assertEqual(parent_match.func.view_class.__module__, "parent_portal.views")
        self.assertEqual(student_match.func.view_class.__module__, "parent_portal.student_portal_views")
        self.assertEqual(teacher_match.func.view_class.__module__, "parent_portal.teacher_portal_views")
        self.assertEqual(legacy_student_match.func.view_class.__module__, "parent_portal.student_portal_views")




