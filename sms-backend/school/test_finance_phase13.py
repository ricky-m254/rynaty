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
    ScholarshipAward,
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
                schema_name="finance_phase13_test",
                name="Finance Phase13 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="finance-phase13.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class FinancePhase13ScholarshipInvoiceGenerationTests(TenantTestBase):
    def test_batch_invoice_applies_active_scholarships(self):
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
        grade = GradeLevel.objects.create(name="Grade 5", order=5, is_active=True)
        school_class = SchoolClass.objects.create(
            name="G5",
            stream="A",
            academic_year=academic_year,
            grade_level=grade,
            section_name="A",
            is_active=True,
        )
        student = Student.objects.create(
            admission_number="S-P13-001",
            first_name="Asha",
            last_name="Kariuki",
            date_of_birth=date(2014, 5, 20),
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

        tuition = FeeStructure.objects.create(
            name="Tuition",
            category="Tuition",
            amount=Decimal("1000.00"),
            academic_year=academic_year,
            term=term,
            grade_level=grade,
            billing_cycle="TERMLY",
            is_mandatory=True,
            is_active=True,
        )
        transport = FeeStructure.objects.create(
            name="Transport",
            category="Transport",
            amount=Decimal("500.00"),
            academic_year=academic_year,
            term=term,
            grade_level=grade,
            billing_cycle="TERMLY",
            is_mandatory=False,
            is_active=True,
        )
        FeeAssignment.objects.create(
            student=student,
            fee_structure=tuition,
            discount_amount=Decimal("100.00"),
            is_active=True,
        )
        FeeAssignment.objects.create(
            student=student,
            fee_structure=transport,
            discount_amount=Decimal("0.00"),
            is_active=True,
        )

        ScholarshipAward.objects.create(
            student=student,
            program_name="Merit 10%",
            award_type="PERCENT",
            percentage=Decimal("10.00"),
            status="ACTIVE",
            is_active=True,
        )
        ScholarshipAward.objects.create(
            student=student,
            program_name="Support Grant",
            award_type="FIXED",
            amount=Decimal("200.00"),
            status="ACTIVE",
            is_active=True,
        )

        result = FinanceService.generate_invoices_from_assignments(
            term=term,
            due_date=date(2026, 2, 20),
            issue_immediately=True,
        )

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["scholarships_applied"], 1)

        invoice = Invoice.objects.get(id=result["invoice_ids"][0])
        self.assertEqual(invoice.total_amount, Decimal("1060.00"))

