from datetime import date
from decimal import Decimal

from django.test import TestCase
from django_tenants.utils import schema_context

from clients.models import Tenant, Domain
from school.models import (
    AcademicYear,
    Enrollment,
    FeeAssignment,
    FeeStructure,
    GradeLevel,
    Invoice,
    Payment,
    SchoolClass,
    Student,
    Term,
)
from school.services import FinanceService


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="finance_phase14_test",
                name="Finance Phase14 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="finance-phase14.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class FinancePhase14InstallmentAllocationTests(TenantTestBase):
    def test_auto_allocate_updates_installment_statuses(self):
        academic_year = AcademicYear.objects.create(
            name="2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        term = Term.objects.create(
            academic_year=academic_year,
            name="Term 1",
            start_date=date(2026, 1, 10),
            end_date=date(2026, 4, 10),
            is_active=True,
        )
        grade = GradeLevel.objects.create(name="Grade 6", order=6, is_active=True)
        school_class = SchoolClass.objects.create(
            name="G6",
            stream="A",
            academic_year=academic_year,
            grade_level=grade,
            section_name="A",
            is_active=True,
        )
        student = Student.objects.create(
            admission_number="S-P14-001",
            first_name="Brian",
            last_name="Otieno",
            date_of_birth=date(2013, 2, 14),
            gender="M",
            is_active=True,
        )
        Enrollment.objects.create(
            student=student,
            school_class=school_class,
            term=term,
            status="Active",
            is_active=True,
        )
        fee = FeeStructure.objects.create(
            name="Tuition",
            category="Tuition",
            amount=Decimal("1200.00"),
            academic_year=academic_year,
            term=term,
            grade_level=grade,
            billing_cycle="TERMLY",
            is_mandatory=True,
            is_active=True,
        )
        FeeAssignment.objects.create(student=student, fee_structure=fee, discount_amount=Decimal("0.00"), is_active=True)

        batch = FinanceService.generate_invoices_from_assignments(
            term=term,
            due_date=date(2026, 2, 20),
            issue_immediately=True,
        )
        invoice = Invoice.objects.get(id=batch["invoice_ids"][0])
        plan = FinanceService.create_installment_plan(
            invoice=invoice,
            installment_count=3,
            due_dates=[date(2026, 2, 10), date(2026, 3, 10), date(2026, 4, 10)],
            created_by=None,
        )

        payment = Payment.objects.create(
            student=student,
            amount=Decimal("500.00"),
            payment_method="Cash",
            reference_number="AUTO-ALLOC-P14",
            notes="phase14",
        )
        result = FinanceService.auto_allocate_payment(payment)
        self.assertEqual(result["allocations"], 1)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "PARTIALLY_PAID")

        installments = list(plan.installments.all().order_by("sequence"))
        self.assertEqual(installments[0].status, "PAID")
        self.assertEqual(installments[1].status, "PENDING")
        self.assertEqual(installments[2].status, "PENDING")

