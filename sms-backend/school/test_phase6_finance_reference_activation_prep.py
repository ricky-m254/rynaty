from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicYear, SchoolClass, Term
from clients.models import Domain, Tenant
from finance.presentation.views import (
    FinanceClassRefView as StagedFinanceClassRefView,
    FinanceEnrollmentRefView as StagedFinanceEnrollmentRefView,
    FinanceStudentDetailView as StagedFinanceStudentDetailView,
    FinanceStudentRefView as StagedFinanceStudentRefView,
)
from school.models import Enrollment, Module, Role, Student, UserModuleAssignment, UserProfile
from school.views import (
    FinanceClassRefView as LiveFinanceClassRefView,
    FinanceEnrollmentRefView as LiveFinanceEnrollmentRefView,
    FinanceStudentDetailView as LiveFinanceStudentDetailView,
    FinanceStudentRefView as LiveFinanceStudentRefView,
)


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="finance_phase6_prep_test",
                defaults={
                    "name": "Finance Phase 6 Prep Test School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="finance-phase6-prep.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class FinanceReferenceActivationPrepTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="finance_phase6_user", password="pass1234")
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
        self.other_term = Term.objects.create(
            academic_year=self.year,
            name="Term 2",
            start_date="2026-05-01",
            end_date="2026-08-31",
            is_active=True,
        )
        self.school_class = SchoolClass.objects.create(
            name="Grade 7",
            stream="A",
            academic_year=self.year,
            is_active=True,
        )
        self.other_class = SchoolClass.objects.create(
            name="Grade 8",
            stream="B",
            academic_year=self.year,
            is_active=True,
        )

        self.student_one = Student.objects.create(
            admission_number="FIN-001",
            first_name="Alice",
            last_name="Zephyr",
            gender="F",
            date_of_birth="2011-01-01",
            is_active=True,
        )
        self.student_two = Student.objects.create(
            admission_number="FIN-002",
            first_name="Bob",
            last_name="Yellow",
            gender="M",
            date_of_birth="2011-01-02",
            is_active=True,
        )
        self.student_inactive = Student.objects.create(
            admission_number="FIN-003",
            first_name="Cara",
            last_name="Xeno",
            gender="F",
            date_of_birth="2011-01-03",
            is_active=False,
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
        Enrollment.objects.create(
            student=self.student_inactive,
            school_class_id=self.other_class.id,
            term_id=self.other_term.id,
            status="Active",
            is_active=False,
        )

    def _invoke(self, view_class, path, **kwargs):
        request = self.factory.get(path)
        force_authenticate(request, user=self.user)
        return view_class.as_view()(request, **kwargs)

    def test_staged_finance_student_ref_matches_live_contract(self):
        path = "/api/finance/ref/students/?limit=1&offset=0&order_by=last_name&order_dir=desc"
        live_response = self._invoke(LiveFinanceStudentRefView, path)
        staged_response = self._invoke(StagedFinanceStudentRefView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_student_ref_matches_live_error_contract(self):
        path = "/api/finance/ref/students/?limit=oops&offset=0"
        live_response = self._invoke(LiveFinanceStudentRefView, path)
        staged_response = self._invoke(StagedFinanceStudentRefView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_enrollment_ref_matches_live_contract(self):
        path = f"/api/finance/ref/enrollments/?class_id={self.school_class.id}&term_id={self.term.id}"
        live_response = self._invoke(LiveFinanceEnrollmentRefView, path)
        staged_response = self._invoke(StagedFinanceEnrollmentRefView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_class_ref_matches_live_contract(self):
        path = f"/api/finance/ref/classes/?term_id={self.term.id}"
        live_response = self._invoke(LiveFinanceClassRefView, path)
        staged_response = self._invoke(StagedFinanceClassRefView, path)

        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)

    def test_staged_finance_student_detail_matches_live_contract(self):
        path = f"/api/finance/students/{self.student_one.id}/"
        live_response = self._invoke(LiveFinanceStudentDetailView, path, student_id=self.student_one.id)
        staged_response = self._invoke(StagedFinanceStudentDetailView, path, student_id=self.student_one.id)

        self.assertEqual(live_response.status_code, 200)
        self.assertEqual(staged_response.status_code, live_response.status_code)
        self.assertEqual(staged_response.data, live_response.data)
