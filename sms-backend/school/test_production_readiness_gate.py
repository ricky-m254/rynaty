from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.views import AcademicEnrollmentViewSet
from admissions.views import AdmissionApplicationViewSet, AdmissionDecisionViewSet, AdmissionInquiryViewSet
from clients.models import Domain, Tenant
from parent_portal.models import ParentStudentLink
from parent_portal.views import _children_for_parent
from school.models import (
    AcademicYear,
    AccountingPeriod,
    Enrollment,
    FeeStructure,
    GradeLevel,
    Invoice,
    Module,
    Payment,
    Role,
    SchoolProfile,
    SchoolClass,
    Staff,
    Student,
    Subject,
    TeacherAssignment,
    Term,
    UserModuleAssignment,
    UserProfile,
)
from school.services import FinanceService
from school.views import BehaviorIncidentViewSet, FinancialSummaryView, InvoiceViewSet, StudentViewSet

User = get_user_model()


class ProductionGateTenantBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant_a = Tenant.objects.create(
                schema_name="gate_tenant_a",
                name="Gate Tenant A",
                paid_until="2030-01-01",
            )
            cls.tenant_b = Tenant.objects.create(
                schema_name="gate_tenant_b",
                name="Gate Tenant B",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="gate-a.localhost", tenant=cls.tenant_a, is_primary=True)
            Domain.objects.create(domain="gate-b.localhost", tenant=cls.tenant_b, is_primary=True)

    def setUp(self):
        self.factory = APIRequestFactory()
        self.schema_context = schema_context(self.tenant_a.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)

    @staticmethod
    def _create_user_with_role(username: str, role_name: str, modules: list[str]):
        user = User.objects.create_user(username=username, password="pass1234")
        role, _ = Role.objects.get_or_create(name=role_name, defaults={"description": role_name.title()})
        UserProfile.objects.update_or_create(user=user, defaults={"role": role})
        for key in modules:
            module, _ = Module.objects.get_or_create(key=key, defaults={"name": key.title()})
            UserModuleAssignment.objects.update_or_create(
                user=user,
                module=module,
                defaults={"is_active": True},
            )
        return user

    @staticmethod
    def _normalize_list_response(data):
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data


class ProductionReadinessGateTests(ProductionGateTenantBase):
    def test_setup_order_enforcement_invoice_requires_complete_dependencies(self):
        accountant = self._create_user_with_role("gate_acc_missing", "ACCOUNTANT", ["FINANCE"])
        request = self.factory.post(
            "/api/finance/invoices/",
            {
                "student": 1,
                # term intentionally omitted
                "due_date": (timezone.now().date() + timedelta(days=15)).isoformat(),
                # line_items intentionally omitted
            },
            format="json",
        )
        force_authenticate(request, user=accountant)
        response = InvoiceViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("term", response.data)
        self.assertIn("line_items", response.data)

    def test_role_boundary_teacher_cannot_access_finance(self):
        teacher = self._create_user_with_role("gate_teacher", "TEACHER", ["STUDENTS", "ACADEMICS"])
        request = self.factory.get("/api/finance/summary/")
        force_authenticate(request, user=teacher)
        response = FinancialSummaryView.as_view()(request)
        self.assertEqual(response.status_code, 403)

    def test_role_boundary_accountant_cannot_access_behavior(self):
        accountant = self._create_user_with_role("gate_acc_behavior", "ACCOUNTANT", ["FINANCE"])
        request = self.factory.get("/api/behavior/incidents/")
        force_authenticate(request, user=accountant)
        response = BehaviorIncidentViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 403)

    def test_parent_scope_children_access_is_explicit_child_only(self):
        parent = User.objects.create_user(username="gate_parent", email="gate.parent@example.com", password="pass1234")
        student_linked = Student.objects.create(
            first_name="Linked",
            last_name="Child",
            date_of_birth=date(2015, 1, 1),
            admission_number="GATE-LINK-001",
            gender="M",
            is_active=True,
        )
        student_unlinked = Student.objects.create(
            first_name="Other",
            last_name="Child",
            date_of_birth=date(2015, 1, 2),
            admission_number="GATE-OTHER-001",
            gender="F",
            is_active=True,
        )
        ParentStudentLink.objects.create(parent_user=parent, student=student_linked, relationship="Parent", is_active=True)
        children = _children_for_parent(parent)
        self.assertEqual(children.count(), 1)
        self.assertEqual(children.first().id, student_linked.id)
        self.assertNotEqual(children.first().id, student_unlinked.id)

    def test_closed_accounting_period_denies_invoice_posting(self):
        accountant = self._create_user_with_role("gate_acc_period", "ACCOUNTANT", ["FINANCE"])
        year = AcademicYear.objects.create(name="Gate 2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), is_active=True)
        term = Term.objects.create(
            academic_year=year,
            name="Gate Term 1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            is_active=True,
        )
        student = Student.objects.create(
            first_name="Finance",
            last_name="Student",
            date_of_birth=date(2012, 1, 1),
            admission_number="GATE-FIN-001",
            gender="M",
            is_active=True,
        )
        fee = FeeStructure.objects.create(
            name="Gate Tuition",
            amount=Decimal("1000.00"),
            academic_year=year,
            term=term,
            is_active=True,
        )
        today = timezone.now().date()
        AccountingPeriod.objects.create(
            name="Gate Closed Period",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
            is_closed=True,
        )

        request = self.factory.post(
            "/api/finance/invoices/",
            {
                "student": student.id,
                "term": term.id,
                "due_date": (today + timedelta(days=30)).isoformat(),
                "line_items": [{"fee_structure": fee.id, "amount": "1000.00", "description": "Tuition"}],
            },
            format="json",
        )
        force_authenticate(request, user=accountant)
        response = InvoiceViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("closed", str(response.data).lower())

    def test_payment_reversal_approval_rolls_back_allocations(self):
        admin = self._create_user_with_role("gate_admin_fin", "ADMIN", ["FINANCE"])
        year = AcademicYear.objects.create(name="Gate 2027", start_date=date(2027, 1, 1), end_date=date(2027, 12, 31), is_active=True)
        term = Term.objects.create(
            academic_year=year,
            name="Gate Term 2",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 4, 30),
            is_active=True,
        )
        student = Student.objects.create(
            first_name="Rollback",
            last_name="Student",
            date_of_birth=date(2012, 2, 2),
            admission_number="GATE-RBK-001",
            gender="F",
            is_active=True,
        )
        fee = FeeStructure.objects.create(
            name="Gate Rollback Fee",
            amount=Decimal("600.00"),
            academic_year=year,
            term=term,
            is_active=True,
        )
        invoice = FinanceService.create_invoice(
            student=student,
            term=term,
            line_items_data=[{"fee_structure": fee, "amount": Decimal("600.00"), "description": "Tuition"}],
            due_date=timezone.now().date() + timedelta(days=14),
        )
        payment = FinanceService.record_payment(
            student=student,
            amount=Decimal("600.00"),
            payment_method="Cash",
            reference_number="GATE-RBK-PAY-001",
        )
        FinanceService.allocate_payment(payment, invoice, Decimal("600.00"))
        self.assertEqual(str(invoice.balance_due), "0.00")

        reversal = FinanceService.request_payment_reversal(payment=payment, reason="Audit reversal", requested_by=admin)
        FinanceService.approve_payment_reversal(reversal_request=reversal, reviewed_by=admin, review_notes="Approved in gate test")
        invoice.refresh_from_db()
        payment.refresh_from_db()
        self.assertFalse(payment.is_active)
        self.assertEqual(payment.allocations.count(), 0)
        self.assertEqual(str(invoice.balance_due), "600.00")

    def test_promotion_constraints_no_grade_skip(self):
        admin = self._create_user_with_role("gate_admin_acad", "ADMIN", ["ACADEMICS"])
        from_year = AcademicYear.objects.create(name="Gate 2028", start_date=date(2028, 1, 1), end_date=date(2028, 12, 31), is_active=True)
        to_year = AcademicYear.objects.create(name="Gate 2029", start_date=date(2029, 1, 1), end_date=date(2029, 12, 31), is_active=True)
        from_term = Term.objects.create(
            academic_year=from_year,
            name="Gate T1 2028",
            start_date=date(2028, 1, 1),
            end_date=date(2028, 4, 30),
            is_active=True,
        )
        to_term = Term.objects.create(
            academic_year=to_year,
            name="Gate T1 2029",
            start_date=date(2029, 1, 1),
            end_date=date(2029, 4, 30),
            is_active=True,
        )
        grade7 = GradeLevel.objects.create(name="Gate Grade 7", order=7, is_active=True)
        grade8 = GradeLevel.objects.create(name="Gate Grade 8", order=8, is_active=True)
        grade9 = GradeLevel.objects.create(name="Gate Grade 9", order=9, is_active=True)
        class7 = SchoolClass.objects.create(name="G7", stream="A", academic_year=from_year, grade_level=grade7, section_name="A", is_active=True)
        # Intentionally create only grade 9 class first to test skip protection.
        SchoolClass.objects.create(name="G9", stream="A", academic_year=to_year, grade_level=grade9, section_name="A", is_active=True)
        student = Student.objects.create(
            first_name="Promote",
            last_name="Safe",
            date_of_birth=date(2013, 3, 3),
            admission_number="GATE-PRM-001",
            gender="M",
            is_active=True,
        )
        Enrollment.objects.create(student=student, school_class=class7, term=from_term, status="Active", is_active=True)

        promote_request = self.factory.post(
            "/api/academics/enrollments/bulk-promote/",
            {
                "from_academic_year": from_year.id,
                "to_academic_year": to_year.id,
                "from_term": from_term.id,
                "to_term": to_term.id,
            },
            format="json",
        )
        force_authenticate(promote_request, user=admin)
        promote_response = AcademicEnrollmentViewSet.as_view({"post": "bulk_promote"})(promote_request)
        self.assertEqual(promote_response.status_code, 200)
        self.assertEqual(promote_response.data["promoted"], 0)
        self.assertGreaterEqual(promote_response.data["skipped"], 1)

        class8 = SchoolClass.objects.create(name="G8", stream="A", academic_year=to_year, grade_level=grade8, section_name="A", is_active=True)
        rerun_request = self.factory.post(
            "/api/academics/enrollments/bulk-promote/",
            {
                "from_academic_year": from_year.id,
                "to_academic_year": to_year.id,
                "from_term": from_term.id,
                "to_term": to_term.id,
            },
            format="json",
        )
        force_authenticate(rerun_request, user=admin)
        rerun_response = AcademicEnrollmentViewSet.as_view({"post": "bulk_promote"})(rerun_request)
        self.assertEqual(rerun_response.status_code, 200)
        self.assertEqual(rerun_response.data["promoted"], 1)
        self.assertTrue(
            Enrollment.objects.filter(student=student, school_class=class8, term=to_term, is_active=True).exists()
        )

    def test_multi_tenant_isolation_same_identifier_no_cross_leakage(self):
        with schema_context(self.tenant_a.schema_name):
            admin_a = self._create_user_with_role("iso_admin_a", "ADMIN", ["STUDENTS"])
            Student.objects.create(
                first_name="TenantA",
                last_name="Student",
                date_of_birth=date(2011, 1, 1),
                admission_number="SAME-ADM-001",
                gender="M",
                is_active=True,
            )

        with schema_context(self.tenant_b.schema_name):
            admin_b = self._create_user_with_role("iso_admin_b", "ADMIN", ["STUDENTS"])
            Student.objects.create(
                first_name="TenantB",
                last_name="Student",
                date_of_birth=date(2011, 1, 1),
                admission_number="SAME-ADM-001",
                gender="F",
                is_active=True,
            )

        with schema_context(self.tenant_a.schema_name):
            req_a = self.factory.get("/api/students/")
            force_authenticate(req_a, user=admin_a)
            res_a = StudentViewSet.as_view({"get": "list"})(req_a)
            self.assertEqual(res_a.status_code, 200)
            rows_a = self._normalize_list_response(res_a.data)
            self.assertEqual(len(rows_a), 1)
            self.assertEqual(rows_a[0]["first_name"], "TenantA")

        with schema_context(self.tenant_b.schema_name):
            req_b = self.factory.get("/api/students/")
            force_authenticate(req_b, user=admin_b)
            res_b = StudentViewSet.as_view({"get": "list"})(req_b)
            self.assertEqual(res_b.status_code, 200)
            rows_b = self._normalize_list_response(res_b.data)
            self.assertEqual(len(rows_b), 1)
            self.assertEqual(rows_b[0]["first_name"], "TenantB")

    def test_integrated_lifecycle_admissions_to_finance_to_promotion(self):
        admin = self._create_user_with_role("gate_admin_full", "ADMIN", ["ADMISSIONS", "ACADEMICS", "FINANCE", "STUDENTS"])
        year = AcademicYear.objects.create(name="Gate 2026 Full", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), is_active=True)
        next_year = AcademicYear.objects.create(name="Gate 2027 Full", start_date=date(2027, 1, 1), end_date=date(2027, 12, 31), is_active=True)
        term = Term.objects.create(academic_year=year, name="Gate Term A", start_date=date(2026, 1, 1), end_date=date(2026, 4, 30), is_active=True)
        next_term = Term.objects.create(academic_year=next_year, name="Gate Term B", start_date=date(2027, 1, 1), end_date=date(2027, 4, 30), is_active=True)
        grade7 = GradeLevel.objects.create(name="Gate Grade 7B", order=7, is_active=True)
        grade8 = GradeLevel.objects.create(name="Gate Grade 8B", order=8, is_active=True)
        class7 = SchoolClass.objects.create(name="G7B", stream="A", academic_year=year, grade_level=grade7, section_name="A", is_active=True)
        class8 = SchoolClass.objects.create(name="G8B", stream="A", academic_year=next_year, grade_level=grade8, section_name="A", is_active=True)
        SchoolProfile.objects.create(school_name="Gate Full Lifecycle", is_active=True)
        subject = Subject.objects.create(name="Mathematics", code="GATE-MATH", is_active=True)
        Staff.objects.create(
            first_name="Lifecycle",
            last_name="Teacher",
            employee_id="GATE-EMP-001",
            role="Teacher",
            phone="0700000001",
            is_active=True,
        )
        TeacherAssignment.objects.create(
            teacher=admin,
            subject=subject,
            class_section=class7,
            academic_year=year,
            term=term,
            is_primary=True,
            is_active=True,
        )
        fee = FeeStructure.objects.create(
            name="Lifecycle Tuition",
            amount=Decimal("1200.00"),
            academic_year=year,
            term=term,
            is_active=True,
        )

        create_inquiry = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Lifecycle Parent",
                "parent_email": "lifecycle.parent@example.com",
                "child_name": "Lifecycle Child",
                "inquiry_date": "2026-01-10",
                "inquiry_source": "Website",
                "grade_level_interest": class7.id,
                "preferred_start": term.id,
            },
            format="json",
        )
        force_authenticate(create_inquiry, user=admin)
        inquiry_response = AdmissionInquiryViewSet.as_view({"post": "create"})(create_inquiry)
        self.assertEqual(inquiry_response.status_code, 201)

        convert = self.factory.post(
            f"/api/admissions/inquiries/{inquiry_response.data['id']}/convert/",
            {"student_gender": "Male"},
            format="json",
        )
        force_authenticate(convert, user=admin)
        convert_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(convert, pk=inquiry_response.data["id"])
        self.assertEqual(convert_response.status_code, 201)
        application_id = convert_response.data["application_id"]

        decision = self.factory.post(
            "/api/admissions/decisions/",
            {
                "application": application_id,
                "decision": "Accept",
                "decision_date": "2026-01-20",
                "offer_deadline": "2026-12-31",
            },
            format="json",
        )
        force_authenticate(decision, user=admin)
        decision_response = AdmissionDecisionViewSet.as_view({"post": "create"})(decision)
        self.assertEqual(decision_response.status_code, 201)

        respond = self.factory.post(
            f"/api/admissions/decisions/{decision_response.data['id']}/respond/",
            {"response_status": "Accepted"},
            format="json",
        )
        force_authenticate(respond, user=admin)
        respond_response = AdmissionDecisionViewSet.as_view({"post": "respond"})(respond, pk=decision_response.data["id"])
        self.assertEqual(respond_response.status_code, 200)

        enroll = self.factory.post(
            f"/api/admissions/applications/{application_id}/enrollment-complete/",
            {"school_class": class7.id, "term": term.id, "assign_admission_number": True},
            format="json",
        )
        force_authenticate(enroll, user=admin)
        enroll_response = AdmissionApplicationViewSet.as_view({"post": "enrollment_complete"})(enroll, pk=application_id)
        self.assertEqual(enroll_response.status_code, 200)

        student = Student.objects.get(id=enroll_response.data["student_id"])
        invoice = FinanceService.create_invoice(
            student=student,
            term=term,
            line_items_data=[{"fee_structure": fee, "amount": Decimal("1200.00"), "description": "Tuition"}],
            due_date=timezone.now().date() + timedelta(days=30),
        )
        payment = FinanceService.record_payment(
            student=student,
            amount=Decimal("1200.00"),
            payment_method="Cash",
            reference_number="LIFE-001",
        )
        FinanceService.allocate_payment(payment, invoice, Decimal("1200.00"))
        invoice.refresh_from_db()
        self.assertEqual(str(invoice.balance_due), "0.00")

        promote = self.factory.post(
            "/api/academics/enrollments/bulk-promote/",
            {
                "from_academic_year": year.id,
                "to_academic_year": next_year.id,
                "from_term": term.id,
                "to_term": next_term.id,
            },
            format="json",
        )
        force_authenticate(promote, user=admin)
        promote_response = AcademicEnrollmentViewSet.as_view({"post": "bulk_promote"})(promote)
        self.assertEqual(promote_response.status_code, 200)
        self.assertGreaterEqual(promote_response.data["promoted"], 1)
        self.assertTrue(
            Enrollment.objects.filter(student=student, school_class=class8, term=next_term, is_active=True).exists()
        )
