from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from communication.models import Notification
from school.models import Student
from school.models import Module, Role, UserModuleAssignment, UserProfile
from hr.models import Employee
from .models import CirculationRule, CirculationTransaction, LibraryMember, LibraryResource, ResourceCopy
from .views import (
    AcquisitionRequestViewSet,
    CirculationReminderView,
    CirculationRuleView,
    IssueResourceView,
    InventoryAuditViewSet,
    LibraryMemberViewSet,
    LibraryReportsCirculationView,
    LibraryReportsFinesView,
    LibraryReportsMemberActivityView,
    LibraryReportsOverdueView,
    LibraryReportsPopularView,
    ReservationViewSet,
    ReturnResourceView,
    FineViewSet,
)

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="library_test",
                name="Library Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="library.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class LibraryCoreTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser(username="libadmin", password="pass1234", email="libadmin@example.com")
        self.user2 = User.objects.create_user(username="member_user", password="pass1234")
        self.factory = APIRequestFactory()
        role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "Library Admin"})
        UserProfile.objects.create(user=self.user, role=role)
        module, _ = Module.objects.get_or_create(key="LIBRARY", defaults={"name": "Library"})
        UserModuleAssignment.objects.create(user=self.user, module=module, is_active=True)
        UserModuleAssignment.objects.create(user=self.user2, module=module, is_active=True)
        self.member = LibraryMember.objects.create(member_id="LIB-001", member_type="Student")
        self.resource = LibraryResource.objects.create(resource_type="Book", title="Algebra Basics")
        self.copy = ResourceCopy.objects.create(resource=self.resource, accession_number="ACC-001", status="Available")
        CirculationRule.objects.create(member_type="Student", resource_type="Book", max_items=3, loan_period_days=14, max_renewals=2, fine_per_day="5.00")

    def test_issue_and_return_flow(self):
        issue_req = self.factory.post("/api/library/circulation/issue/", {"member": self.member.id, "copy": self.copy.id}, format="json")
        force_authenticate(issue_req, user=self.user)
        issue = IssueResourceView.as_view()(issue_req)
        self.assertEqual(issue.status_code, 201)
        tx_id = issue.data["id"]

        return_req = self.factory.post(
            "/api/library/circulation/return/",
            {"transaction": tx_id, "condition_at_return": "Good"},
            format="json",
        )
        force_authenticate(return_req, user=self.user)
        returned = ReturnResourceView.as_view()(return_req)
        self.assertEqual(returned.status_code, 200)
        if Decimal(str(returned.data.get("fine_amount") or "0")) > 0:
            list_req = self.factory.get("/api/library/fines/")
            force_authenticate(list_req, user=self.user)
            fine_list = FineViewSet.as_view({"get": "list"})(list_req)
            fine_id = fine_list.data[0]["id"]

            pay_req = self.factory.post(f"/api/library/fines/{fine_id}/pay/", {"amount": "1.00"}, format="json")
            force_authenticate(pay_req, user=self.user)
            pay = FineViewSet.as_view({"post": "pay"})(pay_req, pk=fine_id)
            self.assertEqual(pay.status_code, 200)

            postings_req = self.factory.get(f"/api/library/fines/{fine_id}/finance-postings/")
            force_authenticate(postings_req, user=self.user)
            postings = FineViewSet.as_view({"get": "finance_postings"})(postings_req, pk=fine_id)
            self.assertEqual(postings.status_code, 200)
            self.assertIsInstance(postings.data, list)

    def test_reservation_queue(self):
        create_req = self.factory.post("/api/library/reservations/", {"resource": self.resource.id, "member": self.member.id}, format="json")
        force_authenticate(create_req, user=self.user)
        first = ReservationViewSet.as_view({"post": "create"})(create_req)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["queue_position"], 1)

    def test_reports_endpoints(self):
        issue_req = self.factory.post("/api/library/circulation/issue/", {"member": self.member.id, "copy": self.copy.id}, format="json")
        force_authenticate(issue_req, user=self.user)
        issue = IssueResourceView.as_view()(issue_req)
        self.assertEqual(issue.status_code, 201)

        circulation_req = self.factory.get("/api/library/reports/circulation/")
        force_authenticate(circulation_req, user=self.user)
        circulation = LibraryReportsCirculationView.as_view()(circulation_req)
        self.assertEqual(circulation.status_code, 200)
        self.assertIn("active_borrowings", circulation.data)

        popular_req = self.factory.get("/api/library/reports/popular/")
        force_authenticate(popular_req, user=self.user)
        popular = LibraryReportsPopularView.as_view()(popular_req)
        self.assertEqual(popular.status_code, 200)
        self.assertIsInstance(popular.data, list)

        overdue_req = self.factory.get("/api/library/reports/overdue/")
        force_authenticate(overdue_req, user=self.user)
        overdue = LibraryReportsOverdueView.as_view()(overdue_req)
        self.assertEqual(overdue.status_code, 200)
        self.assertIsInstance(overdue.data, list)

        fines_req = self.factory.get("/api/library/reports/fines/")
        force_authenticate(fines_req, user=self.user)
        fines = LibraryReportsFinesView.as_view()(fines_req)
        self.assertEqual(fines.status_code, 200)
        self.assertIn("total_fines", fines.data)

        members_req = self.factory.get("/api/library/reports/member-activity/")
        force_authenticate(members_req, user=self.user)
        members = LibraryReportsMemberActivityView.as_view()(members_req)
        self.assertEqual(members.status_code, 200)
        self.assertIsInstance(members.data, list)

    def test_member_sync_and_notification_on_reservation_ready(self):
        student = Student.objects.create(
            first_name="Ada",
            last_name="Lovelace",
            date_of_birth=date(2012, 1, 1),
            admission_number="ADM-001",
            gender="F",
        )
        employee_user = User.objects.create_user(username="hrstaff", password="pass1234")
        Employee.objects.create(
            user=employee_user,
            employee_id="EMP-001",
            first_name="Grace",
            last_name="Hopper",
            date_of_birth=date(1985, 1, 1),
            gender="Female",
            join_date=date(2020, 1, 1),
            status="Active",
            is_active=True,
        )

        sync_req = self.factory.post("/api/library/members/sync/", {}, format="json")
        force_authenticate(sync_req, user=self.user)
        sync = LibraryMemberViewSet.as_view({"post": "sync"})(sync_req)
        self.assertEqual(sync.status_code, 200)
        self.assertGreaterEqual(sync.data["created"], 1)
        self.assertTrue(LibraryMember.objects.filter(student=student, is_active=True).exists())

        waiting_member = LibraryMember.objects.create(member_id="LIB-002", member_type="Student", user=self.user2)
        waiting_res_req = self.factory.post(
            "/api/library/reservations/",
            {"resource": self.resource.id, "member": waiting_member.id},
            format="json",
        )
        force_authenticate(waiting_res_req, user=self.user)
        waiting_res = ReservationViewSet.as_view({"post": "create"})(waiting_res_req)
        self.assertEqual(waiting_res.status_code, 201)

        issue_req = self.factory.post("/api/library/circulation/issue/", {"member": self.member.id, "copy": self.copy.id}, format="json")
        force_authenticate(issue_req, user=self.user)
        issue = IssueResourceView.as_view()(issue_req)
        self.assertEqual(issue.status_code, 201)
        tx_id = issue.data["id"]

        return_req = self.factory.post("/api/library/circulation/return/", {"transaction": tx_id}, format="json")
        force_authenticate(return_req, user=self.user)
        returned = ReturnResourceView.as_view()(return_req)
        self.assertEqual(returned.status_code, 200)
        self.assertTrue(Notification.objects.filter(recipient=self.user2, title="Library reservation ready").exists())

    def test_overdue_reminder_creates_notification(self):
        overdue_member = LibraryMember.objects.create(member_id="LIB-003", member_type="Student", user=self.user2)
        transaction = CirculationTransaction.objects.create(
            copy=self.copy,
            member=overdue_member,
            transaction_type="Issue",
            due_date=date.today() - timedelta(days=5),
            issued_by=self.user,
            is_active=True,
        )

        reminder_req = self.factory.post(f"/api/library/circulation/{transaction.id}/send_reminder/", {}, format="json")
        force_authenticate(reminder_req, user=self.user)
        reminder = CirculationReminderView.as_view()(reminder_req, transaction_id=transaction.id)

        self.assertEqual(reminder.status_code, 200)
        self.assertIn("notification", reminder.data["channels"])
        self.assertTrue(Notification.objects.filter(recipient=self.user2, title="Library overdue reminder").exists())

    def test_inventory_and_acquisition_baseline_endpoints(self):
        audit_create_req = self.factory.post("/api/library/inventory/audits/", {"total_found": 1, "notes": "Cycle count"}, format="json")
        force_authenticate(audit_create_req, user=self.user)
        audit_create = InventoryAuditViewSet.as_view({"post": "create"})(audit_create_req)
        self.assertEqual(audit_create.status_code, 201)
        audit_id = audit_create.data["id"]

        audit_complete_req = self.factory.post(
            f"/api/library/inventory/audits/{audit_id}/complete/",
            {"total_found": 1, "notes": "Completed count"},
            format="json",
        )
        force_authenticate(audit_complete_req, user=self.user)
        audit_complete = InventoryAuditViewSet.as_view({"post": "complete"})(audit_complete_req, pk=audit_id)
        self.assertEqual(audit_complete.status_code, 200)
        self.assertEqual(audit_complete.data["status"], "Completed")

        request_create_req = self.factory.post(
            "/api/library/acquisition/requests/",
            {
                "title": "Advanced Chemistry",
                "author": "J. Doe",
                "isbn": "9781234567890",
                "quantity": 2,
                "justification": "New lab syllabus coverage",
                "estimated_cost": "1500.00",
            },
            format="json",
        )
        force_authenticate(request_create_req, user=self.user)
        request_create = AcquisitionRequestViewSet.as_view({"post": "create"})(request_create_req)
        self.assertEqual(request_create.status_code, 201)
        request_id = request_create.data["id"]

        request_approve_req = self.factory.post(f"/api/library/acquisition/requests/{request_id}/approve/", {}, format="json")
        force_authenticate(request_approve_req, user=self.user)
        request_approve = AcquisitionRequestViewSet.as_view({"post": "approve"})(request_approve_req, pk=request_id)
        self.assertEqual(request_approve.status_code, 200)
        self.assertEqual(request_approve.data["status"], "Approved")

        request_ordered_req = self.factory.post(f"/api/library/acquisition/requests/{request_id}/mark-ordered/", {}, format="json")
        force_authenticate(request_ordered_req, user=self.user)
        request_ordered = AcquisitionRequestViewSet.as_view({"post": "mark_ordered"})(request_ordered_req, pk=request_id)
        self.assertEqual(request_ordered.status_code, 200)
        self.assertEqual(request_ordered.data["status"], "Ordered")
