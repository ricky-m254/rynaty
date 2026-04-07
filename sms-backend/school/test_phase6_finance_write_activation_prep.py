from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicYear, Term
from clients.models import Domain, Tenant
from finance.presentation.viewsets import (
    BalanceCarryForwardViewSet as StagedBalanceCarryForwardViewSet,
    CashbookEntryViewSet as StagedCashbookEntryViewSet,
    VoteHeadViewSet as StagedVoteHeadViewSet,
)
from school.models import (
    BalanceCarryForward,
    CashbookEntry,
    Module,
    Role,
    Student,
    UserModuleAssignment,
    UserProfile,
    VoteHead,
)
from school.views import (
    BalanceCarryForwardViewSet as LiveBalanceCarryForwardViewSet,
    CashbookEntryViewSet as LiveCashbookEntryViewSet,
    VoteHeadViewSet as LiveVoteHeadViewSet,
)


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="finance_phase6_write_prep_test",
                defaults={
                    "name": "Finance Phase 6 Write Prep Test School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="finance-phase6-write-prep.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class FinanceWriteActivationPrepTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="finance_phase6_write_user", password="pass1234")
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
        self.from_term = Term.objects.create(
            academic_year=self.year,
            name="Term 1",
            start_date="2026-01-01",
            end_date="2026-04-30",
            is_active=True,
        )
        self.to_term = Term.objects.create(
            academic_year=self.year,
            name="Term 2",
            start_date="2026-05-01",
            end_date="2026-08-31",
            is_active=True,
        )
        self.other_term = Term.objects.create(
            academic_year=self.year,
            name="Term 3",
            start_date="2026-09-01",
            end_date="2026-12-15",
            is_active=True,
        )
        self.student = Student.objects.create(
            admission_number="CF-001",
            first_name="Carry",
            last_name="Forward",
            gender="F",
            date_of_birth="2011-01-01",
            is_active=True,
        )
        self.other_student = Student.objects.create(
            admission_number="CF-002",
            first_name="Balance",
            last_name="Mover",
            gender="M",
            date_of_birth="2011-01-02",
            is_active=True,
        )

        VoteHead.objects.create(
            name="Tuition",
            description="Tuition collections",
            allocation_percentage=Decimal("60.00"),
            is_preloaded=True,
            is_active=True,
            order=1,
        )
        VoteHead.objects.create(
            name="Transport",
            description="Transport collections",
            allocation_percentage=Decimal("40.00"),
            is_preloaded=False,
            is_active=False,
            order=2,
        )

    def _invoke(self, viewset_class, method, action, path, data=None, **kwargs):
        request = getattr(self.factory, method.lower())(path, data=data, format="json")
        force_authenticate(request, user=self.user)
        return viewset_class.as_view({method.lower(): action})(request, **kwargs)

    def _normalize_vote_head_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("created_at", None)
        return normalized

    def _normalize_carry_forward_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("created_at", None)
        return normalized

    def _normalize_cashbook_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("created_at", None)
        return normalized

    def _normalize_cashbook_list(self, payload):
        return [self._normalize_cashbook_payload(row) for row in payload]

    def _seed_cashbook_entries(self):
        opening = CashbookEntry.objects.create(
            book_type="CASH",
            entry_date="2026-01-01",
            entry_type="OPENING",
            reference="OB-001",
            description="Opening balance",
            amount_in=Decimal("100.00"),
            amount_out=Decimal("0.00"),
            running_balance=Decimal("100.00"),
        )
        expense = CashbookEntry.objects.create(
            book_type="CASH",
            entry_date="2026-01-02",
            entry_type="EXPENSE",
            reference="EXP-001",
            description="Stationery expense",
            amount_in=Decimal("0.00"),
            amount_out=Decimal("30.00"),
            running_balance=Decimal("70.00"),
        )
        bank_receipt = CashbookEntry.objects.create(
            book_type="BANK",
            entry_date="2026-01-03",
            entry_type="RECEIPT",
            reference="BNK-001",
            description="Bank deposit",
            amount_in=Decimal("250.00"),
            amount_out=Decimal("0.00"),
            running_balance=Decimal("250.00"),
        )
        return {
            "opening": opening,
            "expense": expense,
            "bank_receipt": bank_receipt,
        }

    def test_staged_vote_head_list_matches_live_contract(self):
        path = "/api/finance/vote-heads/"
        live_response = self._invoke(LiveVoteHeadViewSet, "get", "list", path)
        staged_response = self._invoke(StagedVoteHeadViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_vote_head_active_only_matches_live_contract(self):
        path = "/api/finance/vote-heads/?active_only=true"
        live_response = self._invoke(LiveVoteHeadViewSet, "get", "list", path)
        staged_response = self._invoke(StagedVoteHeadViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_vote_head_create_matches_live_contract(self):
        VoteHead.objects.all().delete()
        payload = {
            "name": "Laboratory",
            "description": "Lab charges",
            "allocation_percentage": "15.50",
            "is_preloaded": False,
            "is_active": True,
            "order": 4,
        }

        live_response = self._invoke(
            LiveVoteHeadViewSet,
            "post",
            "create",
            "/api/finance/vote-heads/",
            data=payload,
        )
        self.assertEqual(live_response.status_code, 201)
        normalized_live = self._normalize_vote_head_payload(live_response.data)

        VoteHead.objects.all().delete()

        staged_response = self._invoke(
            StagedVoteHeadViewSet,
            "post",
            "create",
            "/api/finance/vote-heads/",
            data=payload,
        )

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_vote_head_payload(staged_response.data),
            normalized_live,
        )

    def test_staged_vote_head_seed_defaults_matches_live_contract(self):
        VoteHead.objects.all().delete()
        path = "/api/finance/vote-heads/seed-defaults/"
        live_response = self._invoke(LiveVoteHeadViewSet, "post", "seed_defaults", path)

        self.assertEqual(live_response.status_code, 200)
        VoteHead.objects.all().delete()

        staged_response = self._invoke(StagedVoteHeadViewSet, "post", "seed_defaults", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_carry_forward_list_matches_live_contract(self):
        BalanceCarryForward.objects.create(
            student=self.student,
            from_term_id=self.from_term.id,
            to_term_id=self.to_term.id,
            amount=Decimal("250.00"),
            notes="Primary carry forward",
            created_by=self.user,
        )
        BalanceCarryForward.objects.create(
            student=self.other_student,
            from_term_id=self.to_term.id,
            to_term_id=self.other_term.id,
            amount=Decimal("90.00"),
            notes="Secondary carry forward",
            created_by=self.user,
        )

        path = "/api/finance/carry-forwards/"
        live_response = self._invoke(LiveBalanceCarryForwardViewSet, "get", "list", path)
        staged_response = self._invoke(StagedBalanceCarryForwardViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_carry_forward_filtered_list_matches_live_contract(self):
        BalanceCarryForward.objects.create(
            student=self.student,
            from_term_id=self.from_term.id,
            to_term_id=self.to_term.id,
            amount=Decimal("250.00"),
            notes="Primary carry forward",
            created_by=self.user,
        )
        BalanceCarryForward.objects.create(
            student=self.other_student,
            from_term_id=self.to_term.id,
            to_term_id=self.other_term.id,
            amount=Decimal("90.00"),
            notes="Secondary carry forward",
            created_by=self.user,
        )

        path = (
            f"/api/finance/carry-forwards/?student={self.student.id}"
            f"&from_term={self.from_term.id}&to_term={self.to_term.id}"
        )
        live_response = self._invoke(LiveBalanceCarryForwardViewSet, "get", "list", path)
        staged_response = self._invoke(StagedBalanceCarryForwardViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_carry_forward_create_matches_live_contract(self):
        payload = {
            "student": self.student.id,
            "from_term": self.from_term.id,
            "to_term": self.to_term.id,
            "amount": "375.50",
            "notes": "Migration carry forward",
        }

        live_response = self._invoke(
            LiveBalanceCarryForwardViewSet,
            "post",
            "create",
            "/api/finance/carry-forwards/",
            data=payload,
        )
        self.assertEqual(live_response.status_code, 201)
        normalized_live = self._normalize_carry_forward_payload(live_response.data)

        BalanceCarryForward.objects.all().delete()

        staged_response = self._invoke(
            StagedBalanceCarryForwardViewSet,
            "post",
            "create",
            "/api/finance/carry-forwards/",
            data=payload,
        )

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_carry_forward_payload(staged_response.data),
            normalized_live,
        )

    def test_staged_cashbook_filtered_list_matches_live_contract(self):
        self._seed_cashbook_entries()
        path = "/api/finance/cashbook/?book_type=cash&date_from=2026-01-02&date_to=2026-01-02"

        live_response = self._invoke(LiveCashbookEntryViewSet, "get", "list", path)
        staged_response = self._invoke(StagedCashbookEntryViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_cashbook_create_matches_live_contract(self):
        self._seed_cashbook_entries()
        payload = {
            "book_type": "CASH",
            "entry_date": "2026-01-04",
            "entry_type": "EXPENSE",
            "reference": "EXP-002",
            "description": "Transport refund",
            "amount_in": "0.00",
            "amount_out": "15.00",
        }

        live_response = self._invoke(
            LiveCashbookEntryViewSet,
            "post",
            "create",
            "/api/finance/cashbook/",
            data=payload,
        )
        self.assertEqual(live_response.status_code, 201)
        normalized_live = self._normalize_cashbook_payload(live_response.data)

        CashbookEntry.objects.all().delete()
        self._seed_cashbook_entries()

        staged_response = self._invoke(
            StagedCashbookEntryViewSet,
            "post",
            "create",
            "/api/finance/cashbook/",
            data=payload,
        )

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(
            self._normalize_cashbook_payload(staged_response.data),
            normalized_live,
        )

    def test_staged_cashbook_update_matches_live_contract(self):
        seeded = self._seed_cashbook_entries()
        payload = {
            "book_type": "CASH",
            "entry_date": "2026-01-02",
            "entry_type": "EXPENSE",
            "reference": "EXP-001",
            "description": "Stationery expense updated",
            "amount_in": "0.00",
            "amount_out": "40.00",
        }

        live_response = self._invoke(
            LiveCashbookEntryViewSet,
            "patch",
            "partial_update",
            f"/api/finance/cashbook/{seeded['expense'].id}/",
            data=payload,
            pk=seeded["expense"].id,
        )
        self.assertEqual(live_response.status_code, 200)
        live_list = self._invoke(
            LiveCashbookEntryViewSet,
            "get",
            "list",
            "/api/finance/cashbook/?book_type=cash",
        )
        normalized_live_list = self._normalize_cashbook_list(live_list.data)

        CashbookEntry.objects.all().delete()
        staged_seeded = self._seed_cashbook_entries()

        staged_response = self._invoke(
            StagedCashbookEntryViewSet,
            "patch",
            "partial_update",
            f"/api/finance/cashbook/{staged_seeded['expense'].id}/",
            data=payload,
            pk=staged_seeded["expense"].id,
        )
        self.assertEqual(staged_response.status_code, live_response.status_code)
        staged_list = self._invoke(
            StagedCashbookEntryViewSet,
            "get",
            "list",
            "/api/finance/cashbook/?book_type=cash",
        )

        self.assertEqual(
            self._normalize_cashbook_payload(staged_response.data),
            self._normalize_cashbook_payload(live_response.data),
        )
        self.assertEqual(
            self._normalize_cashbook_list(staged_list.data),
            normalized_live_list,
        )

    def test_staged_cashbook_destroy_matches_live_contract(self):
        seeded = self._seed_cashbook_entries()

        live_response = self._invoke(
            LiveCashbookEntryViewSet,
            "delete",
            "destroy",
            f"/api/finance/cashbook/{seeded['expense'].id}/",
            pk=seeded["expense"].id,
        )
        self.assertEqual(live_response.status_code, 204)
        live_list = self._invoke(
            LiveCashbookEntryViewSet,
            "get",
            "list",
            "/api/finance/cashbook/?book_type=cash",
        )
        normalized_live_list = self._normalize_cashbook_list(live_list.data)

        CashbookEntry.objects.all().delete()
        staged_seeded = self._seed_cashbook_entries()

        staged_response = self._invoke(
            StagedCashbookEntryViewSet,
            "delete",
            "destroy",
            f"/api/finance/cashbook/{staged_seeded['expense'].id}/",
            pk=staged_seeded["expense"].id,
        )
        self.assertEqual(staged_response.status_code, live_response.status_code)
        staged_list = self._invoke(
            StagedCashbookEntryViewSet,
            "get",
            "list",
            "/api/finance/cashbook/?book_type=cash",
        )

        self.assertEqual(
            self._normalize_cashbook_list(staged_list.data),
            normalized_live_list,
        )
