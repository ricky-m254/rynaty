from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, UserProfile

from .models import StaffDepartment, StaffMember, StaffRole
from .views import (
    StaffAnalyticsSummaryView,
    StaffAssignmentViewSet,
    StaffDepartmentViewSet,
    StaffMemberViewSet,
    StaffRoleViewSet,
)

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="staff_mgmt_test",
                name="Staff Module Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="staff.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class StaffManagementTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="staff_admin", password="pass1234")
        role = Role.objects.create(name="ADMIN", description="School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.create(key="STAFF", name="Staff Management")

    def test_staff_directory_departments_roles_and_analytics(self):
        create_request = self.factory.post(
            "/api/staff/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "staff_type": "Teaching",
                "employment_type": "Full-time",
                "status": "Active",
                "join_date": "2026-01-10",
                "email_work": "jane.doe@school.local",
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = StaffMemberViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        staff_id = create_response.data["id"]
        self.assertTrue(create_response.data["staff_id"].startswith("STF-"))

        dep_request = self.factory.post(
            "/api/staff/departments/",
            {"name": "Sciences", "code": "SCI", "department_type": "Academic"},
            format="json",
        )
        force_authenticate(dep_request, user=self.user)
        dep_response = StaffDepartmentViewSet.as_view({"post": "create"})(dep_request)
        self.assertEqual(dep_response.status_code, 201)
        dep_id = dep_response.data["id"]

        role_request = self.factory.post(
            "/api/staff/roles/",
            {"name": "Teacher", "code": "TEACHER", "level": 3},
            format="json",
        )
        force_authenticate(role_request, user=self.user)
        role_response = StaffRoleViewSet.as_view({"post": "create"})(role_request)
        self.assertEqual(role_response.status_code, 201)
        role_id = role_response.data["id"]

        assignment_request = self.factory.post(
            "/api/staff/assignments/",
            {
                "staff": staff_id,
                "department": dep_id,
                "role": role_id,
                "is_primary": True,
                "effective_from": "2026-01-10",
            },
            format="json",
        )
        force_authenticate(assignment_request, user=self.user)
        assignment_response = StaffAssignmentViewSet.as_view({"post": "create"})(assignment_request)
        self.assertEqual(assignment_response.status_code, 201)

        analytics_request = self.factory.get("/api/staff/analytics/summary/")
        force_authenticate(analytics_request, user=self.user)
        analytics_response = StaffAnalyticsSummaryView.as_view()(analytics_request)
        self.assertEqual(analytics_response.status_code, 200)
        self.assertEqual(analytics_response.data["total_staff"], 1)

        self.assertTrue(StaffMember.objects.filter(id=staff_id, is_active=True).exists())
        self.assertTrue(StaffDepartment.objects.filter(id=dep_id, is_active=True).exists())
        self.assertTrue(StaffRole.objects.filter(id=role_id, is_active=True).exists())
