from datetime import date
from decimal import Decimal

from django.test import TestCase
from django_tenants.utils import schema_context

from clients.models import Domain, Tenant
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
                schema_name="finance_phase15_test",
                name="Finance Phase15 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="finance-phase15.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class FinancePhase15InstallmentTargetAllocationTests(TenantTestBase):
    def test_targeted_installment_allocation_updates_collected_amount(self):
        year = AcademicYear.objects.create(
            name="2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        term = Term.objects.create(
            academic_year=year,
            name="Term 2",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 8, 1),
            is_active=True,
        )
        grade = GradeLevel.objects.create(name="Grade 7", order=7, is_active=True)
        school_class = SchoolClass.objects.create(
            name="G7",
            stream="B",
            academic_year=year,
            grade_level=grade,
            section_name="B",
            is_active=True,
        )
        student = Student.objects.create(
            admission_number="S-P15-001",
            first_name="Mary",
            last_name="Njeri",
            date_of_birth=date(2012, 7, 7),
            gender="F",
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
            amount=Decimal("900.00"),
            academic_year=year,
            term=term,
            grade_level=grade,
            billing_cycle="TERMLY",
            is_mandatory=True,
            is_active=True,
        )
        FeeAssignment.objects.create(student=student, fee_structure=fee, discount_amount=Decimal("0.00"), is_active=True)

        generated = FinanceService.generate_invoices_from_assignments(
            term=term,
            due_date=date(2026, 6, 10),
            issue_immediately=True,
        )
        invoice = Invoice.objects.get(id=generated["invoice_ids"][0])
        plan = FinanceService.create_installment_plan(
            invoice=invoice,
            installment_count=3,
            due_dates=[date(2026, 6, 1), date(2026, 7, 1), date(2026, 8, 1)],
            created_by=None,
        )
        second = plan.installments.get(sequence=2)

        payment = Payment.objects.create(
            student=student,
            amount=Decimal("300.00"),
            payment_method="Cash",
            reference_number="TARGET-INST-001",
            notes="phase15",
        )
        FinanceService.allocate_payment_to_installment(payment=payment, installment=second, amount_to_allocate=Decimal("300.00"))

        second.refresh_from_db()
        self.assertEqual(second.collected_amount, Decimal("300.00"))
        self.assertEqual(second.status, "PAID")

