from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework_simplejwt.authentication import JWTAuthentication

from academics.views import AssessmentViewSet, TeacherAssignmentViewSet
from admissions.models import AdmissionInquiry
from admissions.models import AdmissionDecision
from admissions.views import AdmissionApplicationViewSet, AdmissionInquiryViewSet
from clients.models import Domain, GlobalSuperAdmin, Tenant
from school.models import (
    AcademicYear,
    AccountingPeriod,
    AdmissionApplication,
    FeeStructure,
    GradeLevel,
    Invoice,
    Module,
    Role,
    SchoolClass,
    SchoolProfile,
    Staff,
    Student,
    Subject,
    TeacherAssignment,
    Term,
    UserModuleAssignment,
    UserProfile,
)
from school.services import FinanceService
from school.views import FinancialSummaryView, InvoiceViewSet, PaymentReversalRequestViewSet, StudentViewSet

User = get_user_model()


class UatFailClosureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant_a = Tenant.objects.create(schema_name="uat_fail_a", name="UAT A", paid_until="2030-01-01")
            cls.tenant_b = Tenant.objects.create(schema_name="uat_fail_b", name="UAT B", paid_until="2030-01-01")
            Domain.objects.create(domain="uat-fail-a.localhost", tenant=cls.tenant_a, is_primary=True)
            Domain.objects.create(domain="uat-fail-b.localhost", tenant=cls.tenant_b, is_primary=True)

    def setUp(self):
        self.factory = APIRequestFactory()
        self.ctx = schema_context(self.tenant_a.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)

    @staticmethod
    def _user(username: str, role_name: str, modules: list[str]):
        user = User.objects.create_user(username=username, password="pass1234")
        role, _ = Role.objects.get_or_create(name=role_name, defaults={"description": role_name.title()})
        UserProfile.objects.update_or_create(user=user, defaults={"role": role})
        for key in modules:
            module, _ = Module.objects.get_or_create(key=key, defaults={"name": key.title()})
            UserModuleAssignment.objects.update_or_create(user=user, module=module, defaults={"is_active": True})
        return user

    def _seed_academic_minimum(self):
        SchoolProfile.objects.create(school_name="UAT School", is_active=True)
        year = AcademicYear.objects.create(name="UAT 2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), is_active=True)
        term = Term.objects.create(academic_year=year, name="Term 1", start_date=date(2026, 1, 1), end_date=date(2026, 4, 30), is_active=True)
        grade = GradeLevel.objects.create(name="Grade 7 UAT", order=7, is_active=True)
        school_class = SchoolClass.objects.create(
            name="G7", stream="A", section_name="A", academic_year=year, grade_level=grade, is_active=True
        )
        subject = Subject.objects.create(name="Math", code="MTH-UAT", is_active=True)
        Staff.objects.create(first_name="Jane", last_name="Doe", employee_id="UAT-EMP-01", role="Teacher", phone="070000")
        return year, term, grade, school_class, subject

    def test_authentication_required_for_finance_summary(self):
        request = self.factory.get("/api/finance/summary/")
        response = FinancialSummaryView.as_view()(request)
        self.assertIn(response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

    def test_invalid_jwt_rejected(self):
        drf_request = Request(self.factory.get("/api/finance/summary/", HTTP_AUTHORIZATION="Bearer bad.token.value"))
        with self.assertRaises(AuthenticationFailed):
            JWTAuthentication().authenticate(drf_request)

    def test_cross_tenant_write_isolation(self):
        admin_a = self._user("uat_admin_a", "ADMIN", ["STUDENTS"])
        student = Student.objects.create(
            first_name="TenantA", last_name="Only", date_of_birth=date(2012, 1, 1), admission_number="UAT-A-001", gender="M"
        )
        with schema_context(self.tenant_b.schema_name):
            admin_b = self._user("uat_admin_b", "ADMIN", ["STUDENTS"])
            request = self.factory.patch(f"/api/students/{student.id}/", {"first_name": "CrossWrite"}, format="json")
            force_authenticate(request, user=admin_b)
            response = StudentViewSet.as_view({"patch": "partial_update"})(request, pk=student.id)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        student.refresh_from_db()
        self.assertEqual(student.first_name, "TenantA")
        self.assertTrue(admin_a.is_active)

    def test_teacher_only_assigned_class_scope_for_assessments(self):
        _, term, _, class_a, subject = self._seed_academic_minimum()
        year = term.academic_year
        class_b = SchoolClass.objects.create(name="G7", stream="B", section_name="B", academic_year=year, grade_level=class_a.grade_level, is_active=True)
        teacher = self._user("uat_teacher_scope", "TEACHER", ["ACADEMICS"])
        admin = self._user("uat_admin_scope", "ADMIN", ["ACADEMICS"])

        assign_request = self.factory.post(
            "/api/academics/teacher-assignments/",
            {
                "teacher": teacher.id,
                "subject": subject.id,
                "class_section": class_a.id,
                "academic_year": year.id,
                "term": term.id,
                "is_primary": True,
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(assign_request, user=admin)
        assign_response = TeacherAssignmentViewSet.as_view({"post": "create"})(assign_request)
        self.assertEqual(assign_response.status_code, 201)

        assessment_allowed = self.factory.post(
            "/api/academics/assessments/",
            {
                "name": "Quiz A",
                "assessment_type": "Quiz",
                "subject": subject.id,
                "class_section": class_a.id,
                "term": term.id,
                "max_score": "100.00",
                "weight_percent": "20.00",
                "date": "2026-02-10",
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(assessment_allowed, user=teacher)
        allowed_response = AssessmentViewSet.as_view({"post": "create"})(assessment_allowed)
        self.assertEqual(allowed_response.status_code, 201)

        assessment_denied = self.factory.post(
            "/api/academics/assessments/",
            {
                "name": "Quiz B",
                "assessment_type": "Quiz",
                "subject": subject.id,
                "class_section": class_b.id,
                "term": term.id,
                "max_score": "100.00",
                "weight_percent": "20.00",
                "date": "2026-02-11",
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(assessment_denied, user=teacher)
        denied_response = AssessmentViewSet.as_view({"post": "create"})(assessment_denied)
        self.assertEqual(denied_response.status_code, 403)

    def test_parent_role_cannot_modify_academics(self):
        _, term, _, school_class, subject = self._seed_academic_minimum()
        parent = self._user("uat_parent_role", "PARENT", ["ACADEMICS"])
        request = self.factory.post(
            "/api/academics/assessments/",
            {
                "name": "Parent Attempt",
                "assessment_type": "Quiz",
                "subject": subject.id,
                "class_section": school_class.id,
                "term": term.id,
                "max_score": "10.00",
                "weight_percent": "10.00",
                "date": "2026-02-15",
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(request, user=parent)
        response = AssessmentViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 403)

    def test_setup_order_enforced_before_enrollment(self):
        admin = self._user("uat_admin_setup", "ADMIN", ["ADMISSIONS"])
        inquiry = AdmissionInquiry.objects.create(
            parent_name="Setup Parent",
            parent_email="setup.parent@example.com",
            child_name="Setup Child",
            inquiry_date=date(2026, 1, 5),
            inquiry_source="Website",
            status="New",
        )
        convert = self.factory.post(f"/api/admissions/inquiries/{inquiry.id}/convert/", {"student_gender": "Male"}, format="json")
        force_authenticate(convert, user=admin)
        convert_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(convert, pk=inquiry.id)
        self.assertEqual(convert_response.status_code, 201)

        app_id = convert_response.data["application_id"]
        application = AdmissionApplication.objects.get(id=app_id)
        AdmissionDecision.objects.create(
            application=application,
            decision="Accept",
            decision_date=date(2026, 1, 10),
            offer_deadline=date(2026, 12, 31),
            response_status="Accepted",
        )

        enroll = self.factory.post(f"/api/admissions/applications/{app_id}/enrollment-complete/", {}, format="json")
        force_authenticate(enroll, user=admin)
        enroll_response = AdmissionApplicationViewSet.as_view({"post": "enrollment_complete"})(enroll, pk=app_id)
        self.assertEqual(enroll_response.status_code, 400)
        self.assertIn("before enrollment", str(enroll_response.data).lower())

    def test_graduated_student_becomes_inactive_and_read_only(self):
        admin = self._user("uat_admin_grad", "ADMIN", ["STUDENTS"])
        student = Student.objects.create(
            first_name="Grad",
            last_name="Student",
            date_of_birth=date(2010, 1, 1),
            admission_number="UAT-GRAD-001",
            gender="F",
            is_active=True,
        )
        graduate_req = self.factory.post(f"/api/students/{student.id}/graduate/", {}, format="json")
        force_authenticate(graduate_req, user=admin)
        grad_response = StudentViewSet.as_view({"post": "graduate"})(graduate_req, pk=student.id)
        self.assertEqual(grad_response.status_code, 200)
        student.refresh_from_db()
        self.assertFalse(student.is_active)

        patch_req = self.factory.patch(f"/api/students/{student.id}/", {"first_name": "Changed"}, format="json")
        force_authenticate(patch_req, user=admin)
        patch_response = StudentViewSet.as_view({"patch": "partial_update"})(patch_req, pk=student.id)
        self.assertEqual(patch_response.status_code, 400)

    def test_auto_allocate_oldest_outstanding_invoice_first(self):
        accountant = self._user("uat_acc_auto_alloc", "ACCOUNTANT", ["FINANCE"])
        year = AcademicYear.objects.create(name="UAT 2027", start_date=date(2027, 1, 1), end_date=date(2027, 12, 31), is_active=True)
        term = Term.objects.create(academic_year=year, name="Term", start_date=date(2027, 1, 1), end_date=date(2027, 4, 30), is_active=True)
        student = Student.objects.create(first_name="Alloc", last_name="Order", date_of_birth=date(2011, 1, 1), admission_number="UAT-ALLOC-001", gender="M")
        fee = FeeStructure.objects.create(name="Tuition", amount=Decimal("100.00"), academic_year=year, term=term, is_active=True)
        old_invoice = FinanceService.create_invoice(
            student=student,
            term=term,
            line_items_data=[{"fee_structure": fee, "amount": Decimal("100.00"), "description": "Old"}],
            due_date=date(2027, 1, 15),
        )
        new_invoice = FinanceService.create_invoice(
            student=student,
            term=term,
            line_items_data=[{"fee_structure": fee, "amount": Decimal("100.00"), "description": "New"}],
            due_date=date(2027, 2, 15),
        )
        payment = FinanceService.record_payment(student=student, amount=Decimal("100.00"), payment_method="Cash", reference_number="ALLOC-001")
        request = self.factory.post(f"/api/finance/payments/{payment.id}/auto-allocate/", {}, format="json")
        force_authenticate(request, user=accountant)
        from school.views import PaymentViewSet
        response = PaymentViewSet.as_view({"post": "auto_allocate"})(request, pk=payment.id)
        self.assertEqual(response.status_code, 200)
        old_invoice.refresh_from_db()
        new_invoice.refresh_from_db()
        self.assertEqual(str(old_invoice.balance_due), "0.00")
        self.assertEqual(str(new_invoice.balance_due), "100.00")

    def test_invoice_immutability_update_denied(self):
        accountant = self._user("uat_acc_immutable", "ACCOUNTANT", ["FINANCE"])
        year = AcademicYear.objects.create(name="UAT 2028", start_date=date(2028, 1, 1), end_date=date(2028, 12, 31), is_active=True)
        term = Term.objects.create(academic_year=year, name="T1", start_date=date(2028, 1, 1), end_date=date(2028, 4, 30), is_active=True)
        student = Student.objects.create(first_name="Invoice", last_name="Immutable", date_of_birth=date(2012, 2, 2), admission_number="UAT-INV-IMM", gender="M")
        fee = FeeStructure.objects.create(name="Fee", amount=Decimal("50.00"), academic_year=year, term=term, is_active=True)
        invoice = FinanceService.create_invoice(
            student=student,
            term=term,
            line_items_data=[{"fee_structure": fee, "amount": Decimal("50.00"), "description": "Fee"}],
            due_date=date(2028, 1, 31),
        )
        patch_req = self.factory.patch(f"/api/finance/invoices/{invoice.id}/", {"status": "VOID"}, format="json")
        force_authenticate(patch_req, user=accountant)
        patch_resp = InvoiceViewSet.as_view({"patch": "partial_update"})(patch_req, pk=invoice.id)
        self.assertEqual(patch_resp.status_code, 405)

    def test_platform_admin_without_tenant_role_cannot_access_tenant_data(self):
        with schema_context("public"):
            public_user = User.objects.create_user(username="platform_super", password="pass1234")
            GlobalSuperAdmin.objects.create(user=public_user)
        tenant_user = User.objects.create_user(username="platform_super", password="pass1234")
        request = self.factory.get("/api/finance/summary/")
        force_authenticate(request, user=tenant_user)
        response = FinancialSummaryView.as_view()(request)
        self.assertEqual(response.status_code, 403)

    def test_tenant_super_admin_can_approve_payment_reversal(self):
        tsa = self._user("uat_tsa", "TENANT_SUPER_ADMIN", ["FINANCE"])
        year = AcademicYear.objects.create(name="UAT 2029", start_date=date(2029, 1, 1), end_date=date(2029, 12, 31), is_active=True)
        term = Term.objects.create(academic_year=year, name="T1", start_date=date(2029, 1, 1), end_date=date(2029, 4, 30), is_active=True)
        student = Student.objects.create(first_name="Tenant", last_name="Admin", date_of_birth=date(2012, 2, 2), admission_number="UAT-TSA-001", gender="F")
        fee = FeeStructure.objects.create(name="Tuition", amount=Decimal("80.00"), academic_year=year, term=term, is_active=True)
        invoice = FinanceService.create_invoice(
            student=student,
            term=term,
            line_items_data=[{"fee_structure": fee, "amount": Decimal("80.00"), "description": "Tuition"}],
            due_date=timezone.now().date() + timedelta(days=30),
        )
        payment = FinanceService.record_payment(student=student, amount=Decimal("80.00"), payment_method="Cash", reference_number="UAT-TSA-PAY")
        FinanceService.allocate_payment(payment, invoice, Decimal("80.00"))
        reversal = FinanceService.request_payment_reversal(payment=payment, reason="UAT reversal", requested_by=tsa)
        approve_req = self.factory.post(
            f"/api/finance/payment-reversals/{reversal.id}/approve/",
            {"review_notes": "Approved by tenant super admin"},
            format="json",
        )
        force_authenticate(approve_req, user=tsa)
        approve_resp = PaymentReversalRequestViewSet.as_view({"post": "approve"})(approve_req, pk=reversal.id)
        self.assertEqual(approve_resp.status_code, 200)

    def test_admin_and_tenant_super_admin_finance_access_allowed(self):
        admin = self._user("uat_admin_fin_ok", "ADMIN", ["FINANCE"])
        tsa = self._user("uat_tsa_fin_ok", "TENANT_SUPER_ADMIN", ["FINANCE"])
        req_admin = self.factory.get("/api/finance/summary/")
        force_authenticate(req_admin, user=admin)
        res_admin = FinancialSummaryView.as_view()(req_admin)
        self.assertEqual(res_admin.status_code, 200)

        req_tsa = self.factory.get("/api/finance/summary/")
        force_authenticate(req_tsa, user=tsa)
        res_tsa = FinancialSummaryView.as_view()(req_tsa)
        self.assertEqual(res_tsa.status_code, 200)

    def test_accountant_denied_academics_write(self):
        _, term, _, school_class, subject = self._seed_academic_minimum()
        accountant = self._user("uat_acc_no_acad_write", "ACCOUNTANT", ["FINANCE"])
        request = self.factory.post(
            "/api/academics/assessments/",
            {
                "name": "Accountant Attempt",
                "assessment_type": "Quiz",
                "subject": subject.id,
                "class_section": school_class.id,
                "term": term.id,
                "max_score": "10.00",
                "weight_percent": "10.00",
                "date": "2026-02-15",
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(request, user=accountant)
        response = AssessmentViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 403)

    def test_closed_period_denies_payment_posting(self):
        accountant = self._user("uat_acc_closed_payment", "ACCOUNTANT", ["FINANCE"])
        year = AcademicYear.objects.create(name="UAT 2030", start_date=date(2030, 1, 1), end_date=date(2030, 12, 31), is_active=True)
        term = Term.objects.create(academic_year=year, name="T1", start_date=date(2030, 1, 1), end_date=date(2030, 4, 30), is_active=True)
        student = Student.objects.create(first_name="Closed", last_name="Payment", date_of_birth=date(2012, 1, 1), admission_number="UAT-CP-001", gender="M")
        today = timezone.now().date()
        AccountingPeriod.objects.create(
            name="Closed Payment Period",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
            is_closed=True,
        )
        pay_request = self.factory.post(
            "/api/finance/payments/",
            {
                "student": student.id,
                "amount": "50.00",
                "payment_method": "Cash",
                "reference_number": "UAT-CP-REF-1",
            },
            format="json",
        )
        force_authenticate(pay_request, user=accountant)
        from school.views import PaymentViewSet

        pay_response = PaymentViewSet.as_view({"post": "create"})(pay_request)
        self.assertEqual(pay_response.status_code, 400)
        self.assertIn("closed", str(pay_response.data).lower())

    def test_closed_period_denies_adjustment_approval(self):
        admin = self._user("uat_admin_closed_adj", "ADMIN", ["FINANCE"])
        year = AcademicYear.objects.create(name="UAT 2031", start_date=date(2031, 1, 1), end_date=date(2031, 12, 31), is_active=True)
        term = Term.objects.create(academic_year=year, name="T1", start_date=date(2031, 1, 1), end_date=date(2031, 4, 30), is_active=True)
        student = Student.objects.create(first_name="Closed", last_name="Adjust", date_of_birth=date(2012, 1, 1), admission_number="UAT-CA-001", gender="F")
        fee = FeeStructure.objects.create(name="Adj Fee", amount=Decimal("100.00"), academic_year=year, term=term, is_active=True)
        invoice = FinanceService.create_invoice(
            student=student,
            term=term,
            line_items_data=[{"fee_structure": fee, "amount": Decimal("100.00"), "description": "Fee"}],
            due_date=timezone.now().date() + timedelta(days=14),
        )
        adjustment = FinanceService.create_adjustment(
            invoice=invoice,
            amount=Decimal("10.00"),
            reason="Pending test",
            user=admin,
            auto_approve=False,
        )
        today = timezone.now().date()
        AccountingPeriod.objects.create(
            name="Closed Adjustment Period",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
            is_closed=True,
        )
        approve_request = self.factory.post(
            f"/api/finance/invoice-adjustments/{adjustment.id}/approve/",
            {"review_notes": "approve"},
            format="json",
        )
        force_authenticate(approve_request, user=admin)
        from school.views import InvoiceAdjustmentViewSet

        approve_response = InvoiceAdjustmentViewSet.as_view({"post": "approve"})(approve_request, pk=adjustment.id)
        self.assertEqual(approve_response.status_code, 400)
        self.assertIn("closed", str(approve_response.data).lower())
