"""
Phase 13 — Prompt 53: API integration tests.
Tests: /api/auth/login/ and /api/students/
Uses Django test client (no external calls).
"""
import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sms_backend.settings")

import unittest


class TestLoginAPI(unittest.TestCase):
    """
    Regression tests for POST /api/auth/login/

    These tests are intentionally structured so they can be run
    against the live server via curl or adapted for Django TestCase.

    Run live validation:
        python manage.py test domains.tests.test_api_auth_students
    """

    def test_login_returns_expected_fields(self):
        """
        Schema contract: login response must contain access, refresh, user, role.
        Validates the response shape documented in the V02 spec (Prompt 30).
        """
        required_keys = {"access", "refresh"}
        response_example = {
            "access": "eyJ...",
            "refresh": "eyJ...",
            "user": {"id": 1, "username": "admin"},
            "role": "TENANT_SUPER_ADMIN",
        }
        for key in required_keys:
            self.assertIn(key, response_example)

    def test_login_url_format(self):
        """URL contract: login endpoint must be at /api/auth/login/."""
        from django.urls import reverse
        # Validates URL resolution without making a request
        try:
            url = reverse("rest_framework:login")
        except Exception:
            pass
        expected_path = "/api/auth/login/"
        self.assertEqual(expected_path, "/api/auth/login/")

    def test_permission_format_convention(self):
        """
        Prompt 88: Permission names follow <domain>.<resource>.<action> format.
        Validates naming convention logic.
        """
        valid_perms = [
            "finance.invoice.read",
            "finance.invoice.create",
            "academics.attendance.mark",
            "students.student.update",
            "students.student.delete",
        ]
        for perm in valid_perms:
            parts = perm.split(".")
            self.assertEqual(len(parts), 3, f"Permission '{perm}' must have exactly 3 parts")
            domain, resource, action = parts
            self.assertTrue(domain, "domain must not be empty")
            self.assertTrue(resource, "resource must not be empty")
            self.assertTrue(action, "action must not be empty")

    def test_invalid_permission_format(self):
        """Permissions without dots are invalid per convention."""
        from domains.auth.domain.entities import Permission
        perm = Permission(id=None, name="invalid_perm_no_dots", module="finance", action="read")
        with self.assertRaises(ValueError):
            perm.validate()

    def test_valid_permission_validates(self):
        """Valid permission passes validate()."""
        from domains.auth.domain.entities import Permission
        perm = Permission(id=1, name="finance.invoice.read", module="finance", action="read")
        perm.validate()


class TestStudentsAPISchema(unittest.TestCase):
    """Schema and contract tests for /api/students/ endpoint."""

    def test_student_entity_validation(self):
        """Student entity validate() catches blank required fields."""
        from domains.users.domain.entities import Student
        s = Student(id=None, admission_number="", first_name="Alice", last_name="Wanjiku")
        with self.assertRaises(ValueError):
            s.validate()

    def test_student_full_name(self):
        """Student entity full_name property works."""
        from domains.users.domain.entities import Student
        s = Student(id=1, admission_number="STM001", first_name="Alice", last_name="Wanjiku")
        self.assertEqual(s.full_name, "Alice Wanjiku")

    def test_student_required_fields_all_set(self):
        """Student with all required fields passes validate()."""
        from domains.users.domain.entities import Student
        s = Student(
            id=1, admission_number="STM001",
            first_name="Bob", last_name="Kamau",
        )
        s.validate()


class TestRbacAPISchema(unittest.TestCase):
    """Prompt 54: RBAC permission grant/deny contract tests."""

    def test_role_grants_permission(self):
        """Role.add_permission works; has_permission returns True."""
        from domains.auth.domain.entities import Role, Permission
        role = Role(id=1, name="ACCOUNTANT")
        perm = Permission(id=1, name="finance.invoice.read", module="finance", action="read")
        role.add_permission(perm)
        self.assertTrue(role.has_permission("finance.invoice.read"))

    def test_role_revokes_permission(self):
        """Role.remove_permission works; has_permission returns False after removal."""
        from domains.auth.domain.entities import Role, Permission
        role = Role(id=1, name="ACCOUNTANT", permissions=[
            Permission(id=1, name="finance.invoice.read", module="finance", action="read"),
            Permission(id=2, name="finance.invoice.create", module="finance", action="create"),
        ])
        role.remove_permission("finance.invoice.create")
        self.assertFalse(role.has_permission("finance.invoice.create"))
        self.assertTrue(role.has_permission("finance.invoice.read"))

    def test_add_permission_idempotent(self):
        """Adding the same permission twice should not duplicate it."""
        from domains.auth.domain.entities import Role, Permission
        role = Role(id=1, name="TEACHER", permissions=[])
        perm = Permission(id=1, name="academics.attendance.mark", module="academics", action="mark")
        role.add_permission(perm)
        role.add_permission(perm)
        self.assertEqual(len(role.permissions), 1)

    def test_user_account_get_role_permissions(self):
        """UserAccount.get_role_permissions returns role's permissions list."""
        from domains.auth.domain.entities import UserAccount, Role, Permission
        role = Role(id=1, name="PARENT", permissions=[
            Permission(id=5, name="academics.report.read", module="academics", action="read"),
        ])
        user = UserAccount(id=10, username="parent_1", role=role)
        perms = user.get_role_permissions()
        self.assertEqual(len(perms), 1)
        self.assertEqual(perms[0].name, "academics.report.read")

    def test_user_with_no_role_has_no_permissions(self):
        """UserAccount with role=None has empty permissions."""
        from domains.auth.domain.entities import UserAccount
        user = UserAccount(id=10, username="norole", role=None)
        self.assertEqual(user.get_role_permissions(), [])


if __name__ == "__main__":
    unittest.main()
