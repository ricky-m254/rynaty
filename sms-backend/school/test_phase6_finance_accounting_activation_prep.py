from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from finance.application import accounting_queries
from finance.application.accounting_queries import (
    get_account_ledger_payload,
    get_trial_balance_payload,
)
from finance.presentation.accounting_views import (
    AccountingLedgerView as StagedAccountingLedgerView,
    AccountingTrialBalanceView as StagedAccountingTrialBalanceView,
)
from finance.presentation.accounting_viewsets import (
    AccountingPeriodViewSet as StagedAccountingPeriodViewSet,
    ChartOfAccountViewSet as StagedChartOfAccountViewSet,
    JournalEntryViewSet as StagedJournalEntryViewSet,
)
from school.models import (
    AccountingPeriod,
    ChartOfAccount,
    JournalEntry,
    JournalLine,
    Module,
    Role,
    UserModuleAssignment,
    UserProfile,
)
from school.views import (
    AccountingLedgerView as LiveAccountingLedgerView,
    AccountingPeriodViewSet as LiveAccountingPeriodViewSet,
    AccountingTrialBalanceView as LiveAccountingTrialBalanceView,
    ChartOfAccountViewSet as LiveChartOfAccountViewSet,
    JournalEntryViewSet as LiveJournalEntryViewSet,
)


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="finance_phase6_accounting_prep_test",
                defaults={
                    "name": "Finance Phase 6 Accounting Prep Test School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="finance-phase6-accounting-prep.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class FinanceAccountingActivationPrepTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="finance_phase6_accounting_user", password="pass1234")
        role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "School Administrator"})
        UserProfile.objects.get_or_create(user=self.user, defaults={"role": role})
        finance_module, _ = Module.objects.get_or_create(key="FINANCE", defaults={"name": "Finance"})
        UserModuleAssignment.objects.get_or_create(user=self.user, module=finance_module)

        self.open_period = AccountingPeriod.objects.create(
            name="FY2026-T1",
            start_date="2026-01-01",
            end_date="2026-03-31",
            is_closed=False,
        )
        self.closed_period = AccountingPeriod.objects.create(
            name="FY2025-T4",
            start_date="2025-10-01",
            end_date="2025-12-31",
            is_closed=True,
            closed_at=timezone.now(),
            closed_by=self.user,
        )
        self.cash_account = ChartOfAccount.objects.create(
            code="1000",
            name="Cash and Bank",
            account_type="ASSET",
            is_active=True,
        )
        self.revenue_account = ChartOfAccount.objects.create(
            code="4000",
            name="Fee Revenue",
            account_type="REVENUE",
            is_active=True,
        )
        self.expense_account = ChartOfAccount.objects.create(
            code="6000",
            name="Operating Expenses",
            account_type="EXPENSE",
            is_active=True,
        )

        self.entry_one = JournalEntry.objects.create(
            entry_date="2026-01-10",
            memo="January fee collection",
            source_type="Payment",
            source_id=1,
            entry_key="JE-ACC-001",
            posted_by=self.user,
        )
        JournalLine.objects.create(
            entry=self.entry_one,
            account=self.cash_account,
            debit=Decimal("5000.00"),
            credit=Decimal("0.00"),
            description="Cash received",
        )
        JournalLine.objects.create(
            entry=self.entry_one,
            account=self.revenue_account,
            debit=Decimal("0.00"),
            credit=Decimal("5000.00"),
            description="Revenue recognized",
        )

        self.entry_two = JournalEntry.objects.create(
            entry_date="2026-01-15",
            memo="Utility payment",
            source_type="Expense",
            source_id=1,
            entry_key="JE-ACC-002",
            posted_by=self.user,
        )
        JournalLine.objects.create(
            entry=self.entry_two,
            account=self.expense_account,
            debit=Decimal("1200.00"),
            credit=Decimal("0.00"),
            description="Utility expense",
        )
        JournalLine.objects.create(
            entry=self.entry_two,
            account=self.cash_account,
            debit=Decimal("0.00"),
            credit=Decimal("1200.00"),
            description="Cash paid",
        )

    def _invoke_viewset(self, viewset_class, method, action, path, data=None, **kwargs):
        request = getattr(self.factory, method.lower())(path, data=data, format="json")
        force_authenticate(request, user=self.user)
        return viewset_class.as_view({method.lower(): action})(request, **kwargs)

    def _invoke_api_view(self, view_class, path):
        request = self.factory.get(path)
        force_authenticate(request, user=self.user)
        return view_class.as_view()(request)

    def _normalize_period_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("created_at", None)
        normalized.pop("closed_at", None)
        return normalized

    def _normalize_account_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("created_at", None)
        return normalized

    def test_staged_accounting_period_list_matches_live_contract(self):
        path = "/api/finance/accounting/periods/"
        live_response = self._invoke_viewset(LiveAccountingPeriodViewSet, "get", "list", path)
        staged_response = self._invoke_viewset(StagedAccountingPeriodViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_accounting_period_close_and_reopen_match_live_contract(self):
        close_path = f"/api/finance/accounting/periods/{self.open_period.id}/close/"
        live_close = self._invoke_viewset(
            LiveAccountingPeriodViewSet,
            "post",
            "close_period",
            close_path,
            pk=self.open_period.id,
        )
        self.assertEqual(live_close.status_code, 200)
        self.open_period.refresh_from_db()
        self.open_period.is_closed = False
        self.open_period.closed_by = None
        self.open_period.closed_at = None
        self.open_period.save(update_fields=["is_closed", "closed_by", "closed_at"])

        staged_close = self._invoke_viewset(
            StagedAccountingPeriodViewSet,
            "post",
            "close_period",
            close_path,
            pk=self.open_period.id,
        )

        self.assertEqual(staged_close.status_code, live_close.status_code)
        self.assertEqual(
            self._normalize_period_payload(staged_close.data),
            self._normalize_period_payload(live_close.data),
        )

        reopen_path = f"/api/finance/accounting/periods/{self.closed_period.id}/reopen/"
        live_reopen = self._invoke_viewset(
            LiveAccountingPeriodViewSet,
            "post",
            "reopen_period",
            reopen_path,
            pk=self.closed_period.id,
        )
        self.assertEqual(live_reopen.status_code, 200)
        self.closed_period.refresh_from_db()
        self.closed_period.is_closed = True
        self.closed_period.closed_by = self.user
        self.closed_period.closed_at = timezone.now()
        self.closed_period.save(update_fields=["is_closed", "closed_by", "closed_at"])

        staged_reopen = self._invoke_viewset(
            StagedAccountingPeriodViewSet,
            "post",
            "reopen_period",
            reopen_path,
            pk=self.closed_period.id,
        )

        self.assertEqual(staged_reopen.status_code, live_reopen.status_code)
        self.assertEqual(
            self._normalize_period_payload(staged_reopen.data),
            self._normalize_period_payload(live_reopen.data),
        )

    def test_staged_chart_of_account_list_matches_live_contract(self):
        path = "/api/finance/accounting/accounts/?search=1000&account_type=ASSET"
        live_response = self._invoke_viewset(LiveChartOfAccountViewSet, "get", "list", path)
        staged_response = self._invoke_viewset(StagedChartOfAccountViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_chart_of_account_create_matches_live_contract(self):
        payload = {
            "code": "2000",
            "name": "Accounts Payable",
            "account_type": "LIABILITY",
            "is_active": True,
        }

        live_response = self._invoke_viewset(
            LiveChartOfAccountViewSet,
            "post",
            "create",
            "/api/finance/accounting/accounts/",
            data=payload,
        )
        self.assertEqual(live_response.status_code, 201)
        ChartOfAccount.objects.filter(code="2000").delete()

        staged_response = self._invoke_viewset(
            StagedChartOfAccountViewSet,
            "post",
            "create",
            "/api/finance/accounting/accounts/",
            data=payload,
        )

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_account_payload(staged_response.data),
            self._normalize_account_payload(live_response.data),
        )

    def test_staged_journal_list_matches_live_contract(self):
        path = f"/api/finance/accounting/journals/?account_id={self.cash_account.id}&date_from=2026-01-01&date_to=2026-01-31"
        live_response = self._invoke_viewset(LiveJournalEntryViewSet, "get", "list", path)
        staged_response = self._invoke_viewset(StagedJournalEntryViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_trial_balance_matches_live_contract(self):
        path = "/api/finance/accounting/trial-balance/?date_from=2026-01-01&date_to=2026-01-31"
        live_response = self._invoke_api_view(LiveAccountingTrialBalanceView, path)
        staged_response = self._invoke_api_view(StagedAccountingTrialBalanceView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_ledger_matches_live_contract(self):
        path = f"/api/finance/accounting/ledger/?account_id={self.cash_account.id}&date_from=2026-01-01&date_to=2026-01-31"
        live_response = self._invoke_api_view(LiveAccountingLedgerView, path)
        staged_response = self._invoke_api_view(StagedAccountingLedgerView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_ledger_missing_account_error_matches_live_contract(self):
        path = "/api/finance/accounting/ledger/"
        live_response = self._invoke_api_view(LiveAccountingLedgerView, path)
        staged_response = self._invoke_api_view(StagedAccountingLedgerView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_trial_balance_helper_aggregates_one_row_per_account_and_balances(self):
        payload = get_trial_balance_payload(date_from="2026-01-01", date_to="2026-01-31")

        self.assertEqual(payload["total_debit"], 6200.0)
        self.assertEqual(payload["total_credit"], 6200.0)
        self.assertTrue(payload["is_balanced"])
        self.assertEqual([row["code"] for row in payload["rows"]], ["1000", "4000", "6000"])
        self.assertEqual(
            payload["rows"],
            [
                {
                    "account_id": self.cash_account.id,
                    "code": "1000",
                    "name": "Cash and Bank",
                    "type": "ASSET",
                    "debit": 5000.0,
                    "credit": 1200.0,
                },
                {
                    "account_id": self.revenue_account.id,
                    "code": "4000",
                    "name": "Fee Revenue",
                    "type": "REVENUE",
                    "debit": 0.0,
                    "credit": 5000.0,
                },
                {
                    "account_id": self.expense_account.id,
                    "code": "6000",
                    "name": "Operating Expenses",
                    "type": "EXPENSE",
                    "debit": 1200.0,
                    "credit": 0.0,
                },
            ],
        )

    def test_trial_balance_helper_honors_date_filters(self):
        payload = get_trial_balance_payload(date_from="2026-01-11", date_to="2026-01-31")

        self.assertEqual(payload["rows"], [
            {
                "account_id": self.cash_account.id,
                "code": "1000",
                "name": "Cash and Bank",
                "type": "ASSET",
                "debit": 0.0,
                "credit": 1200.0,
            },
            {
                "account_id": self.expense_account.id,
                "code": "6000",
                "name": "Operating Expenses",
                "type": "EXPENSE",
                "debit": 1200.0,
                "credit": 0.0,
            },
        ])
        self.assertEqual(payload["total_debit"], 1200.0)
        self.assertEqual(payload["total_credit"], 1200.0)
        self.assertTrue(payload["is_balanced"])

    def test_trial_balance_helper_uses_single_query(self):
        with CaptureQueriesContext(connection) as queries:
            payload = get_trial_balance_payload(date_from="2026-01-01", date_to="2026-01-31")

        self.assertEqual(payload["total_debit"], 6200.0)
        self.assertLessEqual(len(queries), 2)

    def test_ledger_helper_honors_date_filters(self):
        payload = get_account_ledger_payload(
            account_id=str(self.cash_account.id),
            date_from="2026-01-11",
            date_to="2026-01-31",
        )

        self.assertEqual(payload["account_id"], self.cash_account.id)
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["rows"][0]["entry_id"], self.entry_two.id)
        self.assertEqual(payload["rows"][0]["credit"], 1200.0)
        self.assertEqual(payload["rows"][0]["running_balance"], -1200.0)
        self.assertEqual(payload["closing_balance"], -1200.0)

    def test_ledger_helper_preserves_order_and_running_balance(self):
        entry_three = JournalEntry.objects.create(
            entry_date="2026-01-15",
            memo="Additional bank charge",
            source_type="Expense",
            source_id=2,
            entry_key="JE-ACC-003",
            posted_by=self.user,
        )
        JournalLine.objects.create(
            entry=entry_three,
            account=self.expense_account,
            debit=Decimal("300.00"),
            credit=Decimal("0.00"),
            description="Bank charge expense",
        )
        JournalLine.objects.create(
            entry=entry_three,
            account=self.cash_account,
            debit=Decimal("0.00"),
            credit=Decimal("300.00"),
            description="Cash paid",
        )

        payload = get_account_ledger_payload(
            account_id=str(self.cash_account.id),
            date_from="2026-01-01",
            date_to="2026-01-31",
        )

        self.assertEqual([row["entry_id"] for row in payload["rows"]], [self.entry_one.id, self.entry_two.id, entry_three.id])
        self.assertEqual([row["running_balance"] for row in payload["rows"]], [5000.0, 3800.0, 3500.0])
        self.assertEqual(payload["closing_balance"], 3500.0)

    def test_ledger_helper_zero_result_returns_requested_account(self):
        dormant_account = ChartOfAccount.objects.create(
            code="7000",
            name="Dormant Account",
            account_type="EXPENSE",
            is_active=True,
        )

        payload = get_account_ledger_payload(
            account_id=str(dormant_account.id),
            date_from="2026-01-01",
            date_to="2026-01-31",
        )

        self.assertEqual(payload, {"account_id": dormant_account.id, "rows": [], "closing_balance": 0.0})

    def test_ledger_helper_falls_back_without_window_support(self):
        with patch.object(accounting_queries.connection.features, "supports_over_clause", False):
            payload = get_account_ledger_payload(
                account_id=str(self.cash_account.id),
                date_from="2026-01-01",
                date_to="2026-01-31",
            )

        self.assertEqual([row["running_balance"] for row in payload["rows"]], [5000.0, 3800.0])
        self.assertEqual(payload["closing_balance"], 3800.0)

    def test_ledger_helper_uses_single_query(self):
        with CaptureQueriesContext(connection) as queries:
            payload = get_account_ledger_payload(
                account_id=str(self.cash_account.id),
                date_from="2026-01-01",
                date_to="2026-01-31",
            )

        self.assertEqual(payload["closing_balance"], 3800.0)
        self.assertLessEqual(len(queries), 2)
