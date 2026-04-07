from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicYear, Term
from clients.models import Domain, Tenant
from finance.presentation.views import (
    BulkFeeAssignByClassView as StagedBulkFeeAssignByClassView,
    BulkOptionalChargeByClassView as StagedBulkOptionalChargeByClassView,
)
from finance.presentation.viewsets import (
    FeeAssignmentViewSet as StagedFeeAssignmentViewSet,
    FeeStructureViewSet as StagedFeeStructureViewSet,
    OptionalChargeViewSet as StagedOptionalChargeViewSet,
    StudentOptionalChargeViewSet as StagedStudentOptionalChargeViewSet,
)
from school.models import (
    Enrollment,
    FeeAssignment,
    FeeStructure,
    Module,
    OptionalCharge,
    Role,
    SchoolClass,
    Student,
    StudentOptionalCharge,
    UserModuleAssignment,
    UserProfile,
)
from school.views import (
    BulkFeeAssignByClassView as LiveBulkFeeAssignByClassView,
    BulkOptionalChargeByClassView as LiveBulkOptionalChargeByClassView,
    FeeAssignmentViewSet as LiveFeeAssignmentViewSet,
    FeeStructureViewSet as LiveFeeStructureViewSet,
    OptionalChargeViewSet as LiveOptionalChargeViewSet,
    StudentOptionalChargeViewSet as LiveStudentOptionalChargeViewSet,
)


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="finance_phase6_billing_prep_test",
                defaults={
                    "name": "Finance Phase 6 Billing Prep Test School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="finance-phase6-billing-prep.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class FinanceBillingActivationPrepTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="finance_phase6_billing_user", password="pass1234")
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
        self.school_class = SchoolClass.objects.create(
            name="Grade 7",
            stream="A",
            academic_year_id=self.year.id,
            is_active=True,
        )
        self.student_one = Student.objects.create(
            admission_number="BILL-001",
            first_name="Amina",
            last_name="Njeri",
            gender="F",
            date_of_birth="2012-01-01",
            is_active=True,
        )
        self.student_two = Student.objects.create(
            admission_number="BILL-002",
            first_name="Brian",
            last_name="Otieno",
            gender="M",
            date_of_birth="2012-01-02",
            is_active=True,
        )
        Enrollment.objects.create(
            student=self.student_one,
            school_class_id=self.school_class.id,
            term_id=self.term.id,
            status="Active",
            is_active=True,
        )
        Enrollment.objects.create(
            student=self.student_two,
            school_class_id=self.school_class.id,
            term_id=self.term.id,
            status="Active",
            is_active=True,
        )

        self.fee_structure = FeeStructure.objects.create(
            name="Tuition",
            category="Tuition",
            amount=Decimal("15000.00"),
            academic_year_id=self.year.id,
            term_id=self.term.id,
            billing_cycle="TERMLY",
            is_mandatory=True,
            description="Core tuition charge",
            is_active=True,
        )
        self.optional_charge = OptionalCharge.objects.create(
            name="Lunch",
            description="Lunch program",
            category="MEALS",
            amount=Decimal("1200.00"),
            academic_year_id=self.year.id,
            term_id=self.term.id,
            is_active=True,
        )

    def _invoke_viewset(self, viewset_class, method, action, path, data=None, **kwargs):
        request = getattr(self.factory, method.lower())(path, data=data, format="json")
        force_authenticate(request, user=self.user)
        return viewset_class.as_view({method.lower(): action})(request, **kwargs)

    def _invoke_api_view(self, view_class, method, path, data=None):
        request = getattr(self.factory, method.lower())(path, data=data, format="json")
        force_authenticate(request, user=self.user)
        return view_class.as_view()(request)

    def _normalize_fee_structure_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        return normalized

    def _normalize_fee_assignment_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        return normalized

    def _normalize_optional_charge_payload(self, payload):
        normalized = dict(payload)
        normalized.pop("id", None)
        normalized.pop("created_at", None)
        normalized.pop("updated_at", None)
        return normalized

    def test_staged_fee_structure_list_matches_live_contract(self):
        path = "/api/finance/fees/?search=Tuition&is_active=true"
        live_response = self._invoke_viewset(LiveFeeStructureViewSet, "get", "list", path)
        staged_response = self._invoke_viewset(StagedFeeStructureViewSet, "get", "list", path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_fee_structure_create_matches_live_contract(self):
        FeeStructure.objects.all().delete()
        payload = {
            "name": "Transport",
            "category": "Transport",
            "amount": "2500.00",
            "academic_year": self.year.id,
            "term": self.term.id,
            "billing_cycle": "TERMLY",
            "is_mandatory": False,
            "description": "Transport charge",
            "is_active": True,
        }

        live_response = self._invoke_viewset(LiveFeeStructureViewSet, "post", "create", "/api/finance/fees/", data=payload)
        self.assertEqual(live_response.status_code, 201)
        normalized_live = self._normalize_fee_structure_payload(live_response.data)

        FeeStructure.objects.all().delete()

        staged_response = self._invoke_viewset(StagedFeeStructureViewSet, "post", "create", "/api/finance/fees/", data=payload)
        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(self._normalize_fee_structure_payload(staged_response.data), normalized_live)

    def test_staged_fee_assignment_create_matches_live_contract(self):
        payload = {
            "student": self.student_one.id,
            "fee_structure": self.fee_structure.id,
            "discount_amount": "500.00",
            "start_date": "2026-01-01",
            "end_date": "2026-04-30",
            "is_active": True,
        }

        live_response = self._invoke_viewset(
            LiveFeeAssignmentViewSet,
            "post",
            "create",
            "/api/finance/fee-assignments/",
            data=payload,
        )
        self.assertEqual(live_response.status_code, 201)
        normalized_live = self._normalize_fee_assignment_payload(live_response.data)

        FeeAssignment.objects.all().delete()

        staged_response = self._invoke_viewset(
            StagedFeeAssignmentViewSet,
            "post",
            "create",
            "/api/finance/fee-assignments/",
            data=payload,
        )
        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(self._normalize_fee_assignment_payload(staged_response.data), normalized_live)

    def test_staged_fee_assignment_bulk_by_class_matches_live_contract(self):
        payload = {
            "class_id": self.school_class.id,
            "fee_structure_id": self.fee_structure.id,
            "term_id": self.term.id,
            "discount_amount": "200.00",
        }

        live_response = self._invoke_api_view(
            LiveBulkFeeAssignByClassView,
            "post",
            "/api/finance/fee-assignments/by-class/",
            data=payload,
        )
        self.assertEqual(live_response.status_code, 200)
        self.assertEqual(FeeAssignment.objects.count(), 2)
        live_data = dict(live_response.data)

        FeeAssignment.objects.all().delete()

        staged_response = self._invoke_api_view(
            StagedBulkFeeAssignByClassView,
            "post",
            "/api/finance/fee-assignments/by-class/",
            data=payload,
        )
        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_data)
        self.assertEqual(FeeAssignment.objects.count(), 2)

    def test_staged_optional_charge_create_matches_live_contract(self):
        OptionalCharge.objects.all().delete()
        payload = {
            "name": "Swimming",
            "description": "Swimming lessons",
            "category": "TRIP",
            "amount": "1800.00",
            "academic_year": self.year.id,
            "term": self.term.id,
            "is_active": True,
        }

        live_response = self._invoke_viewset(
            LiveOptionalChargeViewSet,
            "post",
            "create",
            "/api/finance/optional-charges/",
            data=payload,
        )
        self.assertEqual(live_response.status_code, 201)
        normalized_live = self._normalize_optional_charge_payload(live_response.data)

        OptionalCharge.objects.all().delete()

        staged_response = self._invoke_viewset(
            StagedOptionalChargeViewSet,
            "post",
            "create",
            "/api/finance/optional-charges/",
            data=payload,
        )
        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(self._normalize_optional_charge_payload(staged_response.data), normalized_live)

    def test_staged_student_optional_charge_list_and_bulk_matches_live_contract(self):
        StudentOptionalCharge.objects.create(student=self.student_one, optional_charge=self.optional_charge)

        list_path = f"/api/finance/student-optional-charges/?optional_charge={self.optional_charge.id}"
        live_list = self._invoke_viewset(LiveStudentOptionalChargeViewSet, "get", "list", list_path)
        staged_list = self._invoke_viewset(StagedStudentOptionalChargeViewSet, "get", "list", list_path)

        self.assertEqual(staged_list.status_code, live_list.status_code)
        self.assertEqual(staged_list.data, live_list.data)

        StudentOptionalCharge.objects.all().delete()
        payload = {
            "class_id": self.school_class.id,
            "optional_charge_id": self.optional_charge.id,
            "term_id": self.term.id,
        }

        live_bulk = self._invoke_api_view(
            LiveBulkOptionalChargeByClassView,
            "post",
            "/api/finance/optional-charges/by-class/",
            data=payload,
        )
        self.assertEqual(live_bulk.status_code, 200)
        live_data = dict(live_bulk.data)

        StudentOptionalCharge.objects.all().delete()

        staged_bulk = self._invoke_api_view(
            StagedBulkOptionalChargeByClassView,
            "post",
            "/api/finance/optional-charges/by-class/",
            data=payload,
        )
        self.assertEqual(staged_bulk.status_code, live_bulk.status_code)
        self.assertEqual(staged_bulk.data, live_data)
        self.assertEqual(StudentOptionalCharge.objects.count(), 2)
