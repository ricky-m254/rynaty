from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicYear, Term
from clients.models import Domain, Tenant
from finance.presentation.governance_viewsets import (
    BudgetViewSet as StagedBudgetViewSet,
    ExpenseViewSet as StagedExpenseViewSet,
    ScholarshipAwardViewSet as StagedScholarshipAwardViewSet,
    TermViewSet as StagedTermViewSet,
    VoteHeadPaymentAllocationViewSet as StagedVoteHeadPaymentAllocationViewSet,
)
from school.models import (
    Budget,
    ChartOfAccount,
    Expense,
    JournalEntry,
    JournalLine,
    Module,
    Payment,
    Role,
    ScholarshipAward,
    Student,
    UserModuleAssignment,
    UserProfile,
    VoteHead,
    VoteHeadPaymentAllocation,
)
from school.views import (
    BudgetViewSet as LiveBudgetViewSet,
    ExpenseViewSet as LiveExpenseViewSet,
    ScholarshipAwardViewSet as LiveScholarshipAwardViewSet,
    TermViewSet as LiveTermViewSet,
    VoteHeadPaymentAllocationViewSet as LiveVoteHeadPaymentAllocationViewSet,
)


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="finance_phase6_governance_prep_test",
                defaults={
                    "name": "Finance Phase 6 Governance Prep Test School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="finance-phase6-governance-prep.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class FinanceGovernanceActivationPrepTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="finance_phase6_governance_user", password="pass1234")
        role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "School Administrator"})
        UserProfile.objects.get_or_create(user=self.user, defaults={"role": role})
        finance_module, _ = Module.objects.get_or_create(key="FINANCE", defaults={"name": "Finance"})
        academics_module, _ = Module.objects.get_or_create(key="ACADEMICS", defaults={"name": "Academics"})
        UserModuleAssignment.objects.get_or_create(user=self.user, module=finance_module)
        UserModuleAssignment.objects.get_or_create(user=self.user, module=academics_module)

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
        self.other_term = Term.objects.create(
            academic_year=self.year,
            name="Term 2",
            start_date="2026-05-01",
            end_date="2026-08-31",
            billing_date="2026-05-05",
            is_active=True,
            is_current=False,
        )
        self.student = Student.objects.create(
            admission_number="GOV-001",
            first_name="Amina",
            last_name="Mwangi",
            gender="F",
            date_of_birth="2011-01-01",
            is_active=True,
        )
        self.payment = Payment.objects.create(
            student=self.student,
            amount=Decimal("8000.00"),
            payment_method="BANK",
            reference_number="GOV-PAY-001",
            notes="Governance parity seed payment",
            is_active=True,
        )
        self.vote_head_tuition = VoteHead.objects.create(
            name="Tuition",
            description="Core tuition vote head",
            allocation_percentage=Decimal("60.00"),
            is_preloaded=True,
            is_active=True,
            order=1,
        )
        self.vote_head_transport = VoteHead.objects.create(
            name="Transport",
            description="Transport vote head",
            allocation_percentage=Decimal("40.00"),
            is_preloaded=False,
            is_active=True,
            order=2,
        )
        VoteHeadPaymentAllocation.objects.create(
            payment=self.payment,
            vote_head=self.vote_head_tuition,
            amount=Decimal("5000.00"),
        )
        VoteHeadPaymentAllocation.objects.create(
            payment=self.payment,
            vote_head=self.vote_head_transport,
            amount=Decimal("3000.00"),
        )

        Budget.objects.create(
            academic_year_id=self.year.id,
            term_id=self.term.id,
            name="Operations Budget",
            monthly_budget=Decimal("10000.00"),
            quarterly_budget=Decimal("30000.00"),
            annual_budget=Decimal("120000.00"),
            categories=["Utilities", "Salaries"],
            is_active=True,
        )

    def _invoke(self, viewset_class, method, action, path, data=None, **kwargs):
        request = getattr(self.factory, method.lower())(path, data=data, format="json")
        force_authenticate(request, user=kwargs.pop("user", self.user))
        return viewset_class.as_view({method.lower(): action})(request, **kwargs)

    def _normalize_term_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        return normalized

    def _normalize_budget_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("created_at", None)
        normalized.pop("updated_at", None)
        return normalized

    def _normalize_expense_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("created_at", None)
        return normalized

    def _normalize_scholarship_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("created_at", None)
        normalized.pop("updated_at", None)
        return normalized

    def _expense_journal_snapshot(self):
        entries = JournalEntry.objects.order_by("entry_date", "id").prefetch_related("lines__account")
        snapshot = []
        for entry in entries:
            lines = []
            for line in entry.lines.order_by("account__code", "id"):
                lines.append(
                    {
                        "account_code": line.account.code,
                        "account_name": line.account.name,
                        "account_type": line.account.account_type,
                        "debit": str(line.debit),
                        "credit": str(line.credit),
                        "description": line.description,
                    }
                )
            snapshot.append(
                {
                    "entry_date": str(entry.entry_date),
                    "memo": entry.memo,
                    "source_type": entry.source_type,
                    "lines": lines,
                }
            )
        return snapshot

    def _reset_expense_side_effects(self):
        JournalLine.objects.all().delete()
        JournalEntry.objects.all().delete()
        ChartOfAccount.objects.all().delete()
        Expense.objects.all().delete()

    def test_staged_term_list_matches_live_contract(self):
        path = "/api/finance/terms/"
        live_response = self._invoke(LiveTermViewSet, "get", "list", path)
        staged_response = self._invoke(StagedTermViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_term_list_allows_finance_scope_without_academics_scope(self):
        finance_user = User.objects.create_user(
            username="finance_phase6_terms_accountant",
            password="pass1234",
        )
        role, _ = Role.objects.get_or_create(name="ACCOUNTANT", defaults={"description": "Finance Manager"})
        UserProfile.objects.get_or_create(user=finance_user, defaults={"role": role})
        finance_module = Module.objects.get(key="FINANCE")
        UserModuleAssignment.objects.get_or_create(user=finance_user, module=finance_module)

        path = "/api/finance/terms/"
        staged_response = self._invoke(StagedTermViewSet, "get", "list", path, user=finance_user)
        live_response = self._invoke(LiveTermViewSet, "get", "list", path, user=finance_user)

        self.assertEqual(staged_response.status_code, 200)
        self.assertEqual(live_response.status_code, 403)

    def test_staged_term_create_matches_live_contract(self):
        payload = {
            "name": "Term 3",
            "start_date": "2026-09-01",
            "end_date": "2026-12-15",
            "billing_date": "2026-09-05",
            "academic_year": self.year.id,
            "is_active": True,
            "is_current": False,
        }

        live_response = self._invoke(LiveTermViewSet, "post", "create", "/api/finance/terms/", data=payload)
        staged_response = self._invoke(StagedTermViewSet, "post", "create", "/api/finance/terms/", data=payload)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_term_payload(staged_response.data),
            self._normalize_term_payload(live_response.data),
        )

    def test_staged_budget_list_matches_live_contract(self):
        path = f"/api/finance/budgets/?academic_year={self.year.id}&term={self.term.id}"
        live_response = self._invoke(LiveBudgetViewSet, "get", "list", path)
        staged_response = self._invoke(StagedBudgetViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_budget_create_matches_live_contract(self):
        payload = {
            "name": "Capital Budget",
            "academic_year": self.year.id,
            "term": self.other_term.id,
            "monthly_budget": "2500.00",
            "quarterly_budget": "7500.00",
            "annual_budget": "30000.00",
            "categories": ["Transport", "Maintenance"],
            "is_active": True,
        }

        live_response = self._invoke(LiveBudgetViewSet, "post", "create", "/api/finance/budgets/", data=payload)
        staged_response = self._invoke(StagedBudgetViewSet, "post", "create", "/api/finance/budgets/", data=payload)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_budget_payload(staged_response.data),
            self._normalize_budget_payload(live_response.data),
        )

    def test_staged_expense_create_preserves_journal_side_effects(self):
        self._reset_expense_side_effects()
        payload = {
            "category": "Utilities",
            "amount": "1800.00",
            "expense_date": "2026-02-10",
            "vendor": "Power Co",
            "payment_method": "Bank Transfer",
            "invoice_number": "EXP-GOV-001",
            "approval_status": "Approved",
            "description": "Electricity bill",
            "is_active": True,
        }

        live_response = self._invoke(LiveExpenseViewSet, "post", "create", "/api/finance/expenses/", data=payload)
        self.assertEqual(live_response.status_code, 201)
        live_snapshot = self._expense_journal_snapshot()

        self._reset_expense_side_effects()

        staged_response = self._invoke(StagedExpenseViewSet, "post", "create", "/api/finance/expenses/", data=payload)
        staged_snapshot = self._expense_journal_snapshot()

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_expense_payload(staged_response.data),
            self._normalize_expense_payload(live_response.data),
        )
        self.assertEqual(staged_snapshot, live_snapshot)

    def test_staged_scholarship_create_matches_live_contract(self):
        payload = {
            "student": self.student.id,
            "program_name": "Merit Fund",
            "award_type": "FIXED",
            "amount": "1500.00",
            "percentage": "0.00",
            "start_date": "2026-01-01",
            "end_date": "2026-04-30",
            "status": "ACTIVE",
            "notes": "Phase 6 scholarship parity check",
            "is_active": True,
        }

        live_response = self._invoke(
            LiveScholarshipAwardViewSet,
            "post",
            "create",
            "/api/finance/scholarships/",
            data=payload,
        )
        staged_response = self._invoke(
            StagedScholarshipAwardViewSet,
            "post",
            "create",
            "/api/finance/scholarships/",
            data=payload,
        )

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_scholarship_payload(staged_response.data),
            self._normalize_scholarship_payload(live_response.data),
        )

    def test_staged_vote_head_allocation_list_matches_live_contract(self):
        path = f"/api/finance/vote-head-allocations/?payment={self.payment.id}"
        live_response = self._invoke(LiveVoteHeadPaymentAllocationViewSet, "get", "list", path)
        staged_response = self._invoke(StagedVoteHeadPaymentAllocationViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_vote_head_allocation_create_is_idempotent_for_same_pair(self):
        payment = Payment.objects.create(
            student=self.student,
            amount=Decimal("3200.00"),
            payment_method="BANK",
            reference_number="GOV-PAY-002",
            notes="Vote head idempotency test",
            is_active=True,
        )
        vote_head = VoteHead.objects.create(
            name="Library",
            description="Library vote head",
            allocation_percentage=Decimal("25.00"),
            is_active=True,
            order=3,
        )
        payload = {
            "payment": payment.id,
            "vote_head": vote_head.id,
            "amount": "1200.00",
        }
        path = "/api/finance/vote-head-allocations/"

        first_response = self._invoke(LiveVoteHeadPaymentAllocationViewSet, "post", "create", path, data=payload)
        second_response = self._invoke(LiveVoteHeadPaymentAllocationViewSet, "post", "create", path, data=payload)

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(VoteHeadPaymentAllocation.objects.filter(payment=payment, vote_head=vote_head).count(), 1)
        allocation = VoteHeadPaymentAllocation.objects.get(payment=payment, vote_head=vote_head)
        self.assertEqual(str(allocation.amount), "1200.00")
        self.assertEqual(second_response.data["amount"], "1200.00")


