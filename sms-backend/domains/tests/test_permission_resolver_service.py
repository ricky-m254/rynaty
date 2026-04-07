"""
Phase 13 — Prompt 54: Unit tests for PermissionResolverService.
Rules: No database. Mock repositories.

Tests:
- User with role only
- User with override (add permission)
- User with override (remove permission)
- User not found → empty list
"""
import unittest
from unittest.mock import MagicMock
from domains.auth.application.permission_resolver_service import PermissionResolverService
from domains.auth.domain.entities import UserAccount, Role, Permission, UserPermissionOverride


def _perm(id, name):
    parts = name.split(".")
    return Permission(id=id, name=name, module=parts[0], action=parts[-1])


def _override(user_id, permission_id, is_allowed):
    return UserPermissionOverride(
        id=None, user_id=user_id, permission_id=permission_id, is_allowed=is_allowed
    )


class TestPermissionResolverService(unittest.TestCase):

    def setUp(self):
        self.user_repo = MagicMock()
        self.perm_repo = MagicMock()
        self.override_repo = MagicMock()
        self.service = PermissionResolverService(
            self.user_repo, self.perm_repo, self.override_repo
        )

    def test_returns_empty_for_unknown_user(self):
        """Unknown user → empty permission list."""
        self.user_repo.get_by_id.return_value = None
        result = self.service.resolve(user_id=999)
        self.assertEqual(result, [])

    def test_returns_role_permissions_only(self):
        """User with role but no overrides → returns role permissions."""
        role = Role(id=1, name="TEACHER", permissions=[
            _perm(1, "academics.attendance.mark"),
            _perm(2, "academics.gradebook.read"),
        ])
        user = UserAccount(id=5, username="teacher1", role=role)
        self.user_repo.get_by_id.return_value = user
        self.override_repo.get_by_user.return_value = []

        result = self.service.resolve(5)
        self.assertIn("academics.attendance.mark", result)
        self.assertIn("academics.gradebook.read", result)
        self.assertEqual(len(result), 2)

    def test_override_grants_extra_permission(self):
        """GRANT override adds a permission not in the role."""
        role = Role(id=1, name="TEACHER", permissions=[
            _perm(1, "academics.attendance.mark"),
        ])
        user = UserAccount(id=5, username="teacher1", role=role)
        self.user_repo.get_by_id.return_value = user

        override = _override(user_id=5, permission_id=10, is_allowed=True)
        self.override_repo.get_by_user.return_value = [override]
        self.perm_repo.get_by_id.return_value = _perm(10, "finance.invoice.read")

        result = self.service.resolve(5)
        self.assertIn("academics.attendance.mark", result)
        self.assertIn("finance.invoice.read", result)

    def test_override_denies_role_permission(self):
        """DENY override removes a permission that the role grants."""
        role = Role(id=2, name="ACCOUNTANT", permissions=[
            _perm(1, "finance.invoice.read"),
            _perm(2, "finance.invoice.create"),
        ])
        user = UserAccount(id=6, username="acc1", role=role)
        self.user_repo.get_by_id.return_value = user

        deny = _override(user_id=6, permission_id=2, is_allowed=False)
        self.override_repo.get_by_user.return_value = [deny]
        self.perm_repo.get_by_id.return_value = _perm(2, "finance.invoice.create")

        result = self.service.resolve(6)
        self.assertIn("finance.invoice.read", result)
        self.assertNotIn("finance.invoice.create", result)

    def test_has_permission_true(self):
        """has_permission returns True when user has the permission."""
        role = Role(id=1, name="ADMIN", permissions=[_perm(1, "students.student.read")])
        user = UserAccount(id=1, username="admin", role=role)
        self.user_repo.get_by_id.return_value = user
        self.override_repo.get_by_user.return_value = []

        self.assertTrue(self.service.has_permission(1, "students.student.read"))

    def test_has_permission_false(self):
        """has_permission returns False when permission is not in effective set."""
        role = Role(id=1, name="STUDENT", permissions=[_perm(5, "academics.gradebook.read")])
        user = UserAccount(id=9, username="stu1", role=role)
        self.user_repo.get_by_id.return_value = user
        self.override_repo.get_by_user.return_value = []

        self.assertFalse(self.service.has_permission(9, "finance.invoice.create"))

    def test_no_role_returns_only_override_grants(self):
        """User with no role but GRANT overrides → only override permissions."""
        user = UserAccount(id=7, username="norole", role=None)
        self.user_repo.get_by_id.return_value = user

        grant = _override(user_id=7, permission_id=3, is_allowed=True)
        self.override_repo.get_by_user.return_value = [grant]
        self.perm_repo.get_by_id.return_value = _perm(3, "communication.announcement.read")

        result = self.service.resolve(7)
        self.assertEqual(result, ["communication.announcement.read"])

    def test_missing_permission_in_repo_is_skipped(self):
        """If override points to a deleted permission → silently skipped."""
        role = Role(id=1, name="TEACHER", permissions=[_perm(1, "academics.attendance.mark")])
        user = UserAccount(id=5, username="teacher1", role=role)
        self.user_repo.get_by_id.return_value = user

        override = _override(user_id=5, permission_id=999, is_allowed=True)
        self.override_repo.get_by_user.return_value = [override]
        self.perm_repo.get_by_id.return_value = None

        result = self.service.resolve(5)
        self.assertEqual(result, ["academics.attendance.mark"])


if __name__ == "__main__":
    unittest.main()
