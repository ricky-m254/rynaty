from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import (
    AcademicYear,
    Guardian,
    Invoice,
    Payment,
    PaymentGatewayTransaction,
    Role,
    Student,
    Term,
    UserProfile,
)
from .models import ParentStudentLink
from .student_portal_views import MyInvoicesView, MyPaymentsView, _student_from_request
from .views import (
    ParentChangePasswordView,
    ParentDashboardView,
    ParentFinancePayView,
    ParentFinanceSummaryView,
    ParentProfileView,
    ParentTimetableView,
    _children_for_parent,
)

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="parent_portal_test",
                name="Parent Portal Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="parent-portal.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class ParentPortalTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.parent_role, _ = Role.objects.get_or_create(name="PARENT", defaults={"description": "Parent"})
        self.student_role, _ = Role.objects.get_or_create(name="STUDENT", defaults={"description": "Student"})
        self.parent = User.objects.create_user(username="parent1", email="parent1@example.com", password="pass1234")
        UserProfile.objects.create(user=self.parent, role=self.parent_role)
        self.student = Student.objects.create(
            first_name="Child",
            last_name="One",
            date_of_birth=date(2015, 1, 1),
            admission_number="ADM-001",
            gender="M",
            is_active=True,
        )
        Guardian.objects.create(
            student=self.student,
            name="Parent One",
            relationship="Parent",
            phone="0700000000",
            email="parent1@example.com",
            is_active=True,
        )

    def create_orphan_parent(self):
        orphan_parent = User.objects.create_user(
            username="orphan_parent",
            email="orphan@example.com",
            password="pass1234",
            first_name="Orphan",
            last_name="Parent",
        )
        UserProfile.objects.create(user=orphan_parent, role=self.parent_role)
        return orphan_parent

    def test_children_fallback_match(self):
        children = _children_for_parent(self.parent)
        self.assertEqual(children.count(), 1)
        self.assertEqual(children.first().id, self.student.id)

    def test_children_explicit_link_priority(self):
        other = Student.objects.create(
            first_name="Child",
            last_name="Two",
            date_of_birth=date(2016, 2, 2),
            admission_number="ADM-002",
            gender="M",
            is_active=True,
        )
        ParentStudentLink.objects.create(parent_user=self.parent, student=other, relationship="Parent", is_active=True)
        children = _children_for_parent(self.parent)
        self.assertEqual(children.count(), 1)
        self.assertEqual(children.first().id, other.id)

    def test_children_do_not_fall_back_to_parent_username_matching_admission_number(self):
        parent_with_legacy_username = User.objects.create_user(
            username=self.student.admission_number,
            email="no-link@example.com",
            password="pass1234",
        )
        UserProfile.objects.create(user=parent_with_legacy_username, role=self.parent_role)

        children = _children_for_parent(parent_with_legacy_username)

        self.assertEqual(children.count(), 0)

    def test_force_password_change_blocks_dashboard_but_allows_profile(self):
        profile = self.parent.userprofile
        profile.force_password_change = True
        profile.save(update_fields=["force_password_change"])
        ParentStudentLink.objects.create(parent_user=self.parent, student=self.student, relationship="Parent", is_active=True)

        dashboard_request = self.factory.get("/api/parent-portal/dashboard/")
        force_authenticate(dashboard_request, user=self.parent)
        dashboard_response = ParentDashboardView.as_view()(dashboard_request)
        self.assertEqual(dashboard_response.status_code, 403)

        profile_request = self.factory.get("/api/parent-portal/profile/")
        force_authenticate(profile_request, user=self.parent)
        profile_response = ParentProfileView.as_view()(profile_request)
        self.assertEqual(profile_response.status_code, 200)
        self.assertTrue(profile_response.data["force_password_change"])

    def test_change_password_clears_force_password_change(self):
        profile = self.parent.userprofile
        profile.force_password_change = True
        profile.save(update_fields=["force_password_change"])

        request = self.factory.post(
            "/api/parent-portal/profile/change-password/",
            {"current_password": "pass1234", "new_password": "newpass123"},
            format="json",
        )
        force_authenticate(request, user=self.parent)

        response = ParentChangePasswordView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertFalse(profile.force_password_change)

    def test_student_portal_does_not_resolve_parent_linked_accounts(self):
        ParentStudentLink.objects.create(parent_user=self.parent, student=self.student, relationship="Parent", is_active=True)

        resolved = _student_from_request(self.parent)

        self.assertIsNone(resolved)

    def test_student_portal_prefers_student_profile_bridge(self):
        student_user = User.objects.create_user(username="student_login", password="pass1234")
        UserProfile.objects.create(
            user=student_user,
            role=self.student_role,
            admission_number=self.student.admission_number,
        )

        resolved = _student_from_request(student_user)

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, self.student.id)

    def test_parent_finance_pay_creates_payment_for_linked_child(self):
        ParentStudentLink.objects.create(parent_user=self.parent, student=self.student, relationship="Parent", is_active=True)
        year = AcademicYear.objects.create(
            name="2026-2027",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        term = Term.objects.create(
            academic_year=year,
            name="Term 1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            is_active=True,
        )
        Invoice.objects.create(
            student=self.student,
            term=term,
            due_date=date(2026, 2, 1),
            total_amount=Decimal("2000.00"),
            status="ISSUED",
            is_active=True,
        )

        request = self.factory.post(
            "/api/parent-portal/finance/pay/",
            {"amount": "1500.50", "payment_method": "M-Pesa"},
            format="json",
        )
        force_authenticate(request, user=self.parent)

        response = ParentFinancePayView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        tx = PaymentGatewayTransaction.objects.get(id=response.data["payment_id"])
        self.assertEqual(tx.student_id, self.student.id)
        self.assertEqual(tx.amount, Decimal("1500.50"))
        self.assertEqual(tx.provider, "parent_portal")
        self.assertEqual(tx.status, "INITIATED")
        self.assertTrue(tx.external_id.startswith("PPORT-"))
        self.assertEqual(response.data["reference_number"], tx.external_id)
        self.assertEqual(Payment.objects.count(), 0)

        summary_request = self.factory.get("/api/parent-portal/finance/summary/")
        force_authenticate(summary_request, user=self.parent)
        summary_response = ParentFinanceSummaryView.as_view()(summary_request)
        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.data["total_billed"], Decimal("2000.00"))
        self.assertEqual(summary_response.data["total_paid"], Decimal("0.00"))
        self.assertEqual(summary_response.data["outstanding_balance"], Decimal("2000.00"))

    def test_parent_finance_pay_rejects_non_positive_amount(self):
        ParentStudentLink.objects.create(parent_user=self.parent, student=self.student, relationship="Parent", is_active=True)

        request = self.factory.post(
            "/api/parent-portal/finance/pay/",
            {"amount": "0", "payment_method": "Online"},
            format="json",
        )
        force_authenticate(request, user=self.parent)

        response = ParentFinancePayView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Amount must be greater than zero.")
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(PaymentGatewayTransaction.objects.count(), 0)

    def test_parent_dashboard_remains_available_without_linked_child(self):
        orphan_parent = self.create_orphan_parent()

        request = self.factory.get("/api/parent-portal/dashboard/")
        force_authenticate(request, user=orphan_parent)

        response = ParentDashboardView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["children"], [])
        self.assertIsNone(response.data["selected_child"])
        self.assertEqual(response.data["kpis"], {})

    def test_parent_child_scoped_views_return_404_without_linked_child(self):
        orphan_parent = self.create_orphan_parent()

        request = self.factory.get("/api/parent-portal/finance/summary/")
        force_authenticate(request, user=orphan_parent)

        response = ParentFinanceSummaryView.as_view()(request)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"], "No linked child found.")

    def test_parent_child_or_enrollment_views_return_404_without_linked_child(self):
        orphan_parent = self.create_orphan_parent()

        request = self.factory.get("/api/parent-portal/timetable/")
        force_authenticate(request, user=orphan_parent)

        response = ParentTimetableView.as_view()(request)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"], "No linked child or active enrollment.")

    def test_student_finance_routes_resolve_under_canonical_and_legacy_prefixes(self):
        canonical_invoices = resolve("/api/student-portal/my-invoices/")
        canonical_payments = resolve("/api/student-portal/my-payments/")
        legacy_invoices = resolve("/api/portal/my-invoices/")
        legacy_payments = resolve("/api/portal/my-payments/")

        self.assertIs(canonical_invoices.func.view_class, MyInvoicesView)
        self.assertIs(canonical_payments.func.view_class, MyPaymentsView)
        self.assertIs(legacy_invoices.func.view_class, MyInvoicesView)
        self.assertIs(legacy_payments.func.view_class, MyPaymentsView)
