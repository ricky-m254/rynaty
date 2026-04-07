from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory

from clients.models import Domain, Tenant
from school.models import Role, Student, UserProfile
from school.views import SmartCampusTokenObtainPairView

User = get_user_model()


class IdentityAuthBridgeTenantBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="identity_auth_bridge_test",
                name="Identity Auth Bridge Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(
                domain="identity-auth-bridge.localhost",
                tenant=cls.tenant,
                is_primary=True,
            )

    def setUp(self):
        self.factory = APIRequestFactory()
        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()
        self.parent_role, _ = Role.objects.get_or_create(name="PARENT", defaults={"description": "Parent"})
        self.student_role, _ = Role.objects.get_or_create(name="STUDENT", defaults={"description": "Student"})

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)

    def _login(self, identifier: str, password: str):
        request = self.factory.post(
            "/api/auth/login/",
            {"username": identifier, "password": password},
            format="json",
        )
        response = SmartCampusTokenObtainPairView.as_view()(request)
        response.render()
        return response


class IdentityAuthBridgeTests(IdentityAuthBridgeTenantBase):
    def test_parent_can_log_in_with_email_lookup(self):
        parent = User.objects.create_user(
            username="parent_one",
            email="parent.one@example.com",
            password="pass1234",
        )
        UserProfile.objects.create(
            user=parent,
            role=self.parent_role,
            phone="0700 000 001",
            admission_number="LEGACY-PARENT-ADM-001",
            force_password_change=True,
        )

        response = self._login("parent.one@example.com", "pass1234")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "PARENT")
        self.assertTrue(response.data["force_password_change"])
        self.assertIn("force_password_change=1", response.data["redirect_to"])
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_parent_can_log_in_with_phone_lookup(self):
        parent = User.objects.create_user(
            username="parent_phone",
            email="parent.phone@example.com",
            password="pass1234",
        )
        UserProfile.objects.create(
            user=parent,
            role=self.parent_role,
            phone="0700 000 002",
        )

        response = self._login("0700000002", "pass1234")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "PARENT")

    def test_parent_cannot_log_in_with_legacy_admission_number(self):
        parent = User.objects.create_user(
            username="parent_legacy",
            email="parent.legacy@example.com",
            password="pass1234",
        )
        UserProfile.objects.create(
            user=parent,
            role=self.parent_role,
            admission_number="LEGACY-PARENT-ADM-002",
        )

        response = self._login("LEGACY-PARENT-ADM-002", "pass1234")

        self.assertNotEqual(response.status_code, 200)
        self.assertIn("detail", response.data)
        self.assertNotIn("access", response.data)

    def test_student_can_log_in_with_student_admission_bridge(self):
        Student.objects.create(
            first_name="Bridge",
            last_name="Student",
            date_of_birth=date(2014, 1, 1),
            admission_number="STU-BRIDGE-001",
            gender="F",
            is_active=True,
        )
        student_user = User.objects.create_user(
            username="student.bridge",
            password="pass1234",
        )
        UserProfile.objects.create(
            user=student_user,
            role=self.student_role,
            admission_number="STU-BRIDGE-001",
        )

        response = self._login("STU-BRIDGE-001", "pass1234")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "STUDENT")
        self.assertEqual(response.data["redirect_to"], "/student-portal")
        self.assertFalse(response.data["force_password_change"])
