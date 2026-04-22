from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from finance.presentation.views import FinanceVoteHeadBudgetReportView
from school.models import (
    AcademicYear,
    BalanceCarryForward,
    Enrollment,
    FeeAssignment,
    FeeStructure,
    GradeLevel,
    Invoice,
    JournalEntry,
    Module,
    Role,
    SchoolClass,
    Student,
    Term,
    UserModuleAssignment,
    UserProfile,
)
from school.rbac_views import RbacPermissionListView
from school.services import FinanceService
from school.views import (
    CashbookEntryViewSet,
    InvoiceViewSet,
    RoleListView,
    UserManagementListCreateView,
    VoteHeadViewSet,
)

User = get_user_model()


class TenantPhase3Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="phase3_core_business_test",
                name="Phase 3 Core Business Test",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="phase3-core.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.factory = APIRequestFactory()
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)

    @staticmethod
    def _create_user(username: str, role_name: str, modules: list[str]):
        user = User.objects.create_user(username=username, password="pass1234")
        role, _ = Role.objects.get_or_create(name=role_name, defaults={"description": role_name.title()})
        UserProfile.objects.update_or_create(user=user, defaults={"role": role})
        for key in modules:
            module, _ = Module.objects.get_or_create(key=key, defaults={"name": key.title(), "is_active": True})
            UserModuleAssignment.objects.update_or_create(
                user=user,
                module=module,
                defaults={"is_active": True},
            )
        return user

    @staticmethod
    def _seed_current_term_student(admission_number: str):
        year = AcademicYear.objects.create(
            name=f"Year {admission_number}",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        from_term = Term.objects.create(
            academic_year=year,
            name="Term 1",
            start_date=date(2026, 1, 10),
            end_date=date(2026, 4, 10),
            is_active=True,
        )
        to_term = Term.objects.create(
            academic_year=year,
            name="Term 2",
            start_date=date(2026, 5, 10),
            end_date=date(2026, 8, 10),
            is_active=True,
        )
        grade = GradeLevel.objects.create(name=f"Grade {admission_number}", order=7, is_active=True)
        school_class = SchoolClass.objects.create(
            name="G7",
            stream=admission_number[-1],
            academic_year=year,
            grade_level=grade,
            section_name=admission_number[-1],
            is_active=True,
        )
        student = Student.objects.create(
            admission_number=admission_number,
            first_name="Phase",
            last_name="Three",
            date_of_birth=date(2012, 7, 7),
            gender="F",
            is_active=True,
        )
        Enrollment.objects.create(
            student=student,
            school_class=school_class,
            term=to_term,
            status="Active",
            is_active=True,
        )
        return year, from_term, to_term, grade, student


class Phase3ApiHardeningTests(TenantPhase3Base):
    def test_teacher_is_denied_legacy_admin_endpoints(self):
        teacher = self._create_user("phase3_teacher_admin", "TEACHER", ["STUDENTS", "ACADEMICS"])

        roles_request = self.factory.get("/api/users/roles/")
        force_authenticate(roles_request, user=teacher)
        roles_response = RoleListView.as_view()(roles_request)
        self.assertEqual(roles_response.status_code, status.HTTP_403_FORBIDDEN)

        create_request = self.factory.post(
            "/api/users/",
            {"username": "new-user", "password": "pass1234"},
            format="json",
        )
        force_authenticate(create_request, user=teacher)
        create_response = UserManagementListCreateView.as_view()(create_request)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_is_denied_rbac_catalog_reads(self):
        teacher = self._create_user("phase3_teacher_rbac", "TEACHER", ["ACADEMICS"])

        request = self.factory.get("/api/rbac/permissions/")
        force_authenticate(request, user=teacher)
        response = RbacPermissionListView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_still_access_legacy_admin_roles_endpoint(self):
        admin = self._create_user("phase3_admin_roles", "ADMIN", ["CORE"])

        request = self.factory.get("/api/users/roles/")
        force_authenticate(request, user=admin)
        response = RoleListView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(row["name"] == "ADMIN" for row in response.data))

    def test_core_role_catalog_includes_narrow_staff_roles(self):
        choices = dict(Role._meta.get_field("name").choices)

        self.assertEqual(choices["SECRETARY"], "School Secretary")
        self.assertEqual(choices["LIBRARIAN"], "School Librarian")
        self.assertEqual(choices["NURSE"], "School Nurse")
        self.assertEqual(choices["SECURITY"], "Security Staff")
        self.assertEqual(choices["COOK"], "Kitchen / Cook")

    def test_admin_role_list_exposes_security_secretary_and_cook_roles(self):
        admin = self._create_user("phase3_admin_role_catalog", "ADMIN", ["CORE"])
        Role.objects.get_or_create(name="SECRETARY", defaults={"description": "School Secretary"})
        Role.objects.get_or_create(name="SECURITY", defaults={"description": "Security Staff"})
        Role.objects.get_or_create(name="COOK", defaults={"description": "Kitchen / Cook"})

        request = self.factory.get("/api/users/roles/")
        force_authenticate(request, user=admin)
        response = RoleListView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        role_names = {row["name"] for row in response.data}
        self.assertIn("SECRETARY", role_names)
        self.assertIn("SECURITY", role_names)
        self.assertIn("COOK", role_names)

    def test_teacher_is_denied_finance_master_data_endpoints(self):
        teacher = self._create_user("phase3_teacher_finance", "TEACHER", ["FINANCE"])

        vote_head_request = self.factory.get("/api/finance/vote-heads/")
        force_authenticate(vote_head_request, user=teacher)
        vote_head_response = VoteHeadViewSet.as_view({"get": "list"})(vote_head_request)
        self.assertEqual(vote_head_response.status_code, status.HTTP_403_FORBIDDEN)

        cashbook_request = self.factory.post(
            "/api/finance/cashbook/",
            {
                "book_type": "CASH",
                "entry_date": "2026-06-01",
                "entry_type": "MANUAL",
                "amount_in": "100.00",
            },
            format="json",
        )
        force_authenticate(cashbook_request, user=teacher)
        cashbook_response = CashbookEntryViewSet.as_view({"post": "create"})(cashbook_request)
        self.assertEqual(cashbook_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_accountant_can_access_finance_master_data_endpoints(self):
        accountant = self._create_user("phase3_accountant_finance", "ACCOUNTANT", ["FINANCE"])

        request = self.factory.get("/api/finance/vote-heads/")
        force_authenticate(request, user=accountant)
        response = VoteHeadViewSet.as_view({"get": "list"})(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_teacher_is_denied_finance_vote_head_budget_report(self):
        teacher = self._create_user("phase3_teacher_vote_head_budget", "TEACHER", ["FINANCE"])

        request = self.factory.get("/api/finance/reports/vote-head-budget/")
        force_authenticate(request, user=teacher)
        response = FinanceVoteHeadBudgetReportView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_accountant_can_access_finance_vote_head_budget_report(self):
        accountant = self._create_user("phase3_accountant_vote_head_budget", "ACCOUNTANT", ["FINANCE"])

        request = self.factory.get("/api/finance/reports/vote-head-budget/")
        force_authenticate(request, user=accountant)
        response = FinanceVoteHeadBudgetReportView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class Phase3ArrearsCarryForwardTests(TenantPhase3Base):
    def test_invoice_generation_includes_carry_forward_without_double_revenue(self):
        year, from_term, to_term, grade, student = self._seed_current_term_student("S-P3-001")
        tuition = FeeStructure.objects.create(
            name="Tuition",
            category="Tuition",
            amount=Decimal("800.00"),
            academic_year=year,
            term=to_term,
            grade_level=grade,
            billing_cycle="TERMLY",
            is_mandatory=True,
            is_active=True,
        )
        FeeAssignment.objects.create(student=student, fee_structure=tuition, discount_amount=Decimal("0.00"), is_active=True)
        BalanceCarryForward.objects.create(
            student=student,
            from_term=from_term,
            to_term=to_term,
            amount=Decimal("250.00"),
        )

        result = FinanceService.generate_invoices_from_assignments(
            term=to_term,
            due_date=date(2026, 6, 10),
            issue_immediately=True,
        )

        self.assertEqual(result["created"], 1)
        invoice = Invoice.objects.get(id=result["invoice_ids"][0])
        self.assertEqual(invoice.total_amount, Decimal("1050.00"))
        descriptions = list(invoice.line_items.order_by("id").values_list("description", flat=True))
        self.assertIn("Tuition", descriptions)
        self.assertIn("Arrears carry-forward from Term 1", descriptions)

        journal = JournalEntry.objects.get(entry_key=f"invoice:{invoice.id}")
        revenue_credit = sum(
            Decimal(str(line.credit))
            for line in journal.lines.filter(account__code="4000")
        )
        carry_forward_credit = sum(
            Decimal(str(line.credit))
            for line in journal.lines.filter(account__code="2100")
        )
        receivable_debit = sum(
            Decimal(str(line.debit))
            for line in journal.lines.filter(account__code="1100")
        )
        self.assertEqual(revenue_credit, Decimal("800.00"))
        self.assertEqual(carry_forward_credit, Decimal("250.00"))
        self.assertEqual(receivable_debit, Decimal("1050.00"))

    def test_invoice_generation_creates_invoice_for_carry_forward_only_student(self):
        _, from_term, to_term, _, student = self._seed_current_term_student("S-P3-002")
        BalanceCarryForward.objects.create(
            student=student,
            from_term=from_term,
            to_term=to_term,
            amount=Decimal("300.00"),
        )

        result = FinanceService.generate_invoices_from_assignments(
            term=to_term,
            due_date=date(2026, 6, 15),
            issue_immediately=True,
        )

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["skipped"], 0)
        invoice = Invoice.objects.get(id=result["invoice_ids"][0])
        self.assertEqual(invoice.total_amount, Decimal("300.00"))
        self.assertEqual(invoice.line_items.count(), 1)
        line_item = invoice.line_items.get()
        self.assertEqual(line_item.description, "Arrears carry-forward from Term 1")
        self.assertEqual(line_item.fee_structure.name, "Arrears Carry Forward")

    def test_generate_batch_endpoint_accepts_finance_term_ids_for_carry_forward(self):
        admin = self._create_user("phase3_admin_generate_batch", "ADMIN", ["FINANCE"])
        _, from_term, to_term, _, student = self._seed_current_term_student("S-P3-003")
        BalanceCarryForward.objects.create(
            student=student,
            from_term=from_term,
            to_term=to_term,
            amount=Decimal("432.10"),
        )

        request = self.factory.post(
            "/api/finance/invoices/generate-batch/",
            {
                "term": to_term.id,
                "due_date": "2026-06-20",
                "issue_immediately": True,
            },
            format="json",
        )
        force_authenticate(request, user=admin)

        response = InvoiceViewSet.as_view({"post": "generate_batch"})(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], 1)
        invoice = Invoice.objects.get(id=response.data["invoice_ids"][0])
        self.assertEqual(invoice.total_amount, Decimal("432.10"))
        self.assertEqual(invoice.line_items.count(), 1)
        self.assertEqual(
            invoice.line_items.get().description,
            "Arrears carry-forward from Term 1",
        )
