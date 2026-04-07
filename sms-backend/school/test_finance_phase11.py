from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Tenant, Domain
from school.models import (
    Module,
    Payment,
    Role,
    Student,
    UserModuleAssignment,
    UserProfile,
)
from school.views import PaymentReversalRequestViewSet


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="finance_phase11_test",
                name="Finance Phase11 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="finance-phase11.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class FinancePhase11PaymentReversalTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        finance_module = Module.objects.create(key="FINANCE", name="Finance")
        accountant_role = Role.objects.create(name="ACCOUNTANT", description="Finance")
        admin_role = Role.objects.create(name="ADMIN", description="Admin")

        self.requester = User.objects.create_user(username="finance_requester", password="pass1234")
        UserProfile.objects.create(user=self.requester, role=accountant_role)
        UserModuleAssignment.objects.create(user=self.requester, module=finance_module, is_active=True)

        self.reviewer = User.objects.create_user(username="finance_admin", password="pass1234")
        UserProfile.objects.create(user=self.reviewer, role=admin_role)
        UserModuleAssignment.objects.create(user=self.reviewer, module=finance_module, is_active=True)

        student = Student.objects.create(
            admission_number="S-P11-001",
            first_name="Ruth",
            last_name="Mugo",
            date_of_birth="2012-03-15",
            gender="F",
            is_active=True,
        )
        self.payment = Payment.objects.create(
            student=student,
            amount="900.00",
            payment_method="Cash",
            reference_number="REV-P11-001",
            notes="phase11 test",
        )

    def test_request_then_approve_payment_reversal(self):
        create_request = self.factory.post(
            "/api/finance/payment-reversals/",
            {"payment": self.payment.id, "reason": "Duplicate receipt"},
            format="json",
        )
        force_authenticate(create_request, user=self.requester)
        create_response = PaymentReversalRequestViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        reversal_id = create_response.data["id"]

        approve_request = self.factory.post(
            f"/api/finance/payment-reversals/{reversal_id}/approve/",
            {"review_notes": "Verified duplicate collection"},
            format="json",
        )
        force_authenticate(approve_request, user=self.reviewer)
        approve_response = PaymentReversalRequestViewSet.as_view({"post": "approve"})(
            approve_request,
            pk=reversal_id,
        )
        self.assertEqual(approve_response.status_code, 200)

        self.payment.refresh_from_db()
        self.assertFalse(self.payment.is_active)

