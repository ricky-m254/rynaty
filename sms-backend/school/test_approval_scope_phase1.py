from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from admissions.views import AdmissionApplicationViewSet
from clients.models import Domain, Tenant
from domains.inventory.presentation.views import StoreOrderReviewView
from finance.presentation.viewsets import PaymentReversalRequestViewSet
from library.models import AcquisitionRequest
from library.views import AcquisitionRequestViewSet
from maintenance.models import MaintenanceCategory, MaintenanceRequest
from maintenance.views import MaintenanceRequestViewSet
from school.models import (
    AdmissionApplication,
    Module,
    Payment,
    Role,
    StoreOrderItem,
    StoreOrderRequest,
    Student,
    UserModuleAssignment,
    UserProfile,
)
from timetable.models import TimetableChangeRequest
from timetable.views import TimetableChangeRequestViewSet

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="approval_scope_phase1",
                name="Approval Scope Phase1 School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="approval-scope.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class ApprovalScopePhase1Tests(TenantTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        for module_key in ("FINANCE", "ADMISSIONS", "LIBRARY", "MAINTENANCE", "STORE", "TIMETABLE"):
            Module.objects.get_or_create(key=module_key, defaults={"name": module_key.title()})

    def _user(self, username: str, role_name: str, modules: list[str] | None = None):
        user = User.objects.create_user(username=username, password="pass1234")
        role, _ = Role.objects.get_or_create(name=role_name, defaults={"description": role_name.title()})
        UserProfile.objects.create(user=user, role=role)
        for module_key in modules or []:
            module = Module.objects.get(key=module_key)
            UserModuleAssignment.objects.create(user=user, module=module, is_active=True)
        return user

    def test_accountant_can_approve_payment_reversal_request(self):
        requester = self._user("approval_fin_requester", "ACCOUNTANT", ["FINANCE"])
        reviewer = self._user("approval_fin_reviewer", "ACCOUNTANT", ["FINANCE"])
        student = Student.objects.create(
            admission_number="APR-001",
            first_name="Asha",
            last_name="Njeri",
            date_of_birth=date(2012, 1, 1),
            gender="F",
            is_active=True,
        )
        payment = Payment.objects.create(
            student=student,
            amount=Decimal("900.00"),
            payment_method="Cash",
            reference_number="APR-REV-001",
            notes="approval scope test",
        )

        create_request = self.factory.post(
            "/api/finance/payment-reversals/",
            {"payment": payment.id, "reason": "Duplicate collection"},
            format="json",
        )
        force_authenticate(create_request, user=requester)
        create_response = PaymentReversalRequestViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)

        approve_request = self.factory.post(
            f"/api/finance/payment-reversals/{create_response.data['id']}/approve/",
            {"review_notes": "Finance office validated duplicate"},
            format="json",
        )
        force_authenticate(approve_request, user=reviewer)
        approve_response = PaymentReversalRequestViewSet.as_view({"post": "approve"})(
            approve_request,
            pk=create_response.data["id"],
        )
        self.assertEqual(approve_response.status_code, 200)

    def test_accountant_can_review_store_order_with_finance_scope(self):
        requester = self._user("approval_store_requester", "STORE_CLERK", ["STORE"])
        reviewer = self._user("approval_store_finance", "ACCOUNTANT", ["FINANCE"])
        order = StoreOrderRequest.objects.create(
            title="Printer Paper",
            description="Term opening stationery",
            requested_by=requester,
            send_to="FINANCE",
        )
        item = StoreOrderItem.objects.create(
            order=order,
            item_name="A4 Paper",
            quantity_requested=Decimal("5.00"),
            unit="ream",
        )

        review_request = self.factory.patch(
            f"/api/store/orders/{order.id}/review/",
            {
                "action": "APPROVE",
                "notes": "Budget confirmed",
                "approved_items": [{"id": item.id, "quantity_approved": "5.00"}],
            },
            format="json",
        )
        force_authenticate(review_request, user=reviewer)
        review_response = StoreOrderReviewView.as_view()(review_request, pk=order.id)
        self.assertEqual(review_response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "APPROVED")

    def test_librarian_can_approve_acquisition_request(self):
        requester = self._user("approval_lib_requester", "TEACHER", ["LIBRARY"])
        reviewer = self._user("approval_lib_reviewer", "LIBRARIAN", ["LIBRARY"])
        acquisition = AcquisitionRequest.objects.create(
            requested_by=requester,
            title="Advanced Chemistry",
            author="J. Doe",
            isbn="9781234567890",
            quantity=2,
            justification="New syllabus coverage",
            estimated_cost=Decimal("1500.00"),
        )

        approve_request = self.factory.post(
            f"/api/library/acquisition/requests/{acquisition.id}/approve/",
            {},
            format="json",
        )
        force_authenticate(approve_request, user=reviewer)
        approve_response = AcquisitionRequestViewSet.as_view({"post": "approve"})(approve_request, pk=acquisition.id)
        self.assertEqual(approve_response.status_code, 200)
        acquisition.refresh_from_db()
        self.assertEqual(acquisition.status, "Approved")

    def test_teacher_cannot_approve_timetable_change_request(self):
        requester = self._user("approval_tt_requester", "TEACHER", ["TIMETABLE"])
        reviewer = self._user("approval_tt_teacher", "TEACHER", ["TIMETABLE"])
        change_request = TimetableChangeRequest.objects.create(
            request_type="CHANGE_TIME",
            requested_by=requester,
            reason="Swap afternoon session",
        )

        approve_request = self.factory.post(
            f"/api/timetable/change-requests/{change_request.id}/approve/",
            {"review_notes": "Teacher should not approve"},
            format="json",
        )
        force_authenticate(approve_request, user=reviewer)
        approve_response = TimetableChangeRequestViewSet.as_view({"post": "approve"})(
            approve_request,
            pk=change_request.id,
        )
        self.assertEqual(approve_response.status_code, 403)

    def test_hod_can_approve_timetable_change_request(self):
        requester = self._user("approval_tt_requester_hod", "TEACHER", ["TIMETABLE"])
        reviewer = self._user("approval_tt_hod", "HOD", [])
        change_request = TimetableChangeRequest.objects.create(
            request_type="CHANGE_TIME",
            requested_by=requester,
            reason="Department timetable balancing",
        )

        approve_request = self.factory.post(
            f"/api/timetable/change-requests/{change_request.id}/approve/",
            {"review_notes": "Approved by department head"},
            format="json",
        )
        force_authenticate(approve_request, user=reviewer)
        approve_response = TimetableChangeRequestViewSet.as_view({"post": "approve"})(
            approve_request,
            pk=change_request.id,
        )
        self.assertEqual(approve_response.status_code, 200)

    def test_teacher_with_module_access_cannot_admit_application(self):
        reviewer = self._user("approval_adm_teacher", "TEACHER", ["ADMISSIONS"])
        application = AdmissionApplication.objects.create(
            student_first_name="Mina",
            student_last_name="Atieno",
            student_dob=date(2014, 5, 1),
            student_gender="Female",
            application_date=date.today(),
            status="Submitted",
        )

        patch_request = self.factory.patch(
            f"/api/admissions/applications/{application.id}/",
            {"status": "Admitted"},
            format="json",
        )
        force_authenticate(patch_request, user=reviewer)
        patch_response = AdmissionApplicationViewSet.as_view({"patch": "partial_update"})(
            patch_request,
            pk=application.id,
        )
        self.assertEqual(patch_response.status_code, 403)

    def test_registrar_can_admit_application(self):
        reviewer = self._user("approval_adm_registrar", "REGISTRAR", [])
        application = AdmissionApplication.objects.create(
            student_first_name="Nia",
            student_last_name="Otieno",
            student_dob=date(2014, 6, 2),
            student_gender="Female",
            application_date=date.today(),
            status="Submitted",
        )

        patch_request = self.factory.patch(
            f"/api/admissions/applications/{application.id}/",
            {"status": "Admitted"},
            format="json",
        )
        force_authenticate(patch_request, user=reviewer)
        patch_response = AdmissionApplicationViewSet.as_view({"patch": "partial_update"})(
            patch_request,
            pk=application.id,
        )
        self.assertEqual(patch_response.status_code, 200)
        application.refresh_from_db()
        self.assertEqual(application.status, "Admitted")

    def test_module_access_without_approval_scope_cannot_approve_maintenance_request(self):
        reporter = self._user("approval_maint_reporter", "ADMIN", [])
        reviewer = self._user("approval_maint_security", "SECURITY", ["MAINTENANCE"])
        category = MaintenanceCategory.objects.create(name="Electrical")
        request_row = MaintenanceRequest.objects.create(
            title="Repair hallway lights",
            category=category,
            description="Two hallway bulbs are out",
            priority="High",
            reported_by=reporter,
        )

        patch_request = self.factory.patch(
            f"/api/maintenance/requests/{request_row.id}/",
            {"status": "Approved", "notes": "Security should not approve"},
            format="json",
        )
        force_authenticate(patch_request, user=reviewer)
        patch_response = MaintenanceRequestViewSet.as_view({"patch": "partial_update"})(
            patch_request,
            pk=request_row.id,
        )
        self.assertEqual(patch_response.status_code, 403)

    def test_admin_can_approve_maintenance_request(self):
        reporter = self._user("approval_maint_reporter_admin", "ADMIN", [])
        reviewer = self._user("approval_maint_admin", "ADMIN", [])
        category = MaintenanceCategory.objects.create(name="Plumbing")
        request_row = MaintenanceRequest.objects.create(
            title="Fix burst pipe",
            category=category,
            description="Pipe leaking near dormitory",
            priority="Urgent",
            reported_by=reporter,
        )

        patch_request = self.factory.patch(
            f"/api/maintenance/requests/{request_row.id}/",
            {"status": "Approved", "notes": "Approved for repair"},
            format="json",
        )
        force_authenticate(patch_request, user=reviewer)
        patch_response = MaintenanceRequestViewSet.as_view({"patch": "partial_update"})(
            patch_request,
            pk=request_row.id,
        )
        self.assertEqual(patch_response.status_code, 200)
        request_row.refresh_from_db()
        self.assertEqual(request_row.status, "Approved")
