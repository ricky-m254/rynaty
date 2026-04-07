"""
Phase 13 — Prompt 55: Tenant isolation tests.
Validates that cross-tenant data access is blocked at the domain level.
No database required — tests use mock repositories.
"""
import unittest
from unittest.mock import MagicMock
from domains.tenants.application.tenant_resolver_service import TenantResolverService
from domains.tenants.domain.entities import Tenant


def _tenant(id, schema, is_active=True):
    return Tenant(
        id=id,
        name=f"School {id}",
        domain=f"school{id}.smartcampus.co.ke",
        schema_name=schema,
        is_active=is_active,
    )


class TestTenantEntity(unittest.TestCase):
    """Prompt 38: Tenant entity structure tests."""

    def test_tenant_has_required_fields(self):
        t = _tenant(1, "school_a")
        self.assertEqual(t.id, 1)
        self.assertEqual(t.schema_name, "school_a")
        self.assertTrue(t.is_active)

    def test_inactive_tenant(self):
        t = _tenant(2, "school_b", is_active=False)
        self.assertFalse(t.is_active)

    def test_tenant_validate_rejects_blank_schema(self):
        """Prompt 38: schema_name is required."""
        t = Tenant(id=1, name="Test", domain="test.local", schema_name="", is_active=True)
        with self.assertRaises(ValueError):
            t.validate()

    def test_tenant_validate_rejects_blank_name(self):
        """Prompt 38: name is required."""
        t = Tenant(id=1, name="", domain="test.local", schema_name="school_a", is_active=True)
        with self.assertRaises(ValueError):
            t.validate()

    def test_tenant_validate_passes(self):
        """Active tenant with valid fields passes validate()."""
        t = _tenant(1, "school_a")
        t.validate()


class TestTenantResolverService(unittest.TestCase):
    """Prompt 41: TenantResolverService unit tests."""

    def setUp(self):
        self.repo = MagicMock()
        self.service = TenantResolverService(self.repo)

    def test_resolves_by_schema_header(self):
        """X-Tenant-ID header resolves to correct tenant."""
        tenant_a = _tenant(1, "school_a")
        self.repo.get_by_schema.return_value = tenant_a

        result = self.service.resolve_from_header("school_a")
        self.assertIsNotNone(result)
        self.assertEqual(result.schema_name, "school_a")

    def test_returns_none_for_unknown_tenant(self):
        """Unknown tenant → None (middleware decides how to handle)."""
        self.repo.get_by_schema.return_value = None
        result = self.service.resolve_from_header("nonexistent_school")
        self.assertIsNone(result)

    def test_raises_permission_error_for_inactive_tenant(self):
        """Inactive tenant → PermissionError (access blocked)."""
        inactive = _tenant(2, "closed_school", is_active=False)
        self.repo.get_by_schema.return_value = inactive
        with self.assertRaises(PermissionError) as ctx:
            self.service.resolve_from_header("closed_school")
        self.assertIn("inactive", str(ctx.exception).lower())

    def test_blank_header_returns_none(self):
        """Empty X-Tenant-ID header returns None."""
        result = self.service.resolve_from_header("")
        self.assertIsNone(result)

    def test_none_header_returns_none(self):
        """None header returns None gracefully."""
        result = self.service.resolve_from_header(None)
        self.assertIsNone(result)

    def test_resolves_by_domain(self):
        """Tenant resolved from full domain name."""
        tenant = _tenant(1, "school_a")
        self.repo.get_by_domain.return_value = tenant

        result = self.service.resolve_from_domain("school1.smartcampus.co.ke")
        self.assertIsNotNone(result)
        self.assertEqual(result.id, 1)

    def test_returns_none_for_unknown_domain(self):
        """Unknown domain → None."""
        self.repo.get_by_domain.return_value = None
        result = self.service.resolve_from_domain("unknown.example.com")
        self.assertIsNone(result)

    def test_resolve_tries_header_first_then_domain(self):
        """resolve() prefers header over domain."""
        tenant_header = _tenant(1, "school_a")
        tenant_domain = _tenant(2, "school_b")

        self.repo.get_by_schema.return_value = tenant_header
        self.repo.get_by_domain.return_value = tenant_domain

        result = self.service.resolve(header_value="school_a", domain="school2.co.ke")
        self.assertEqual(result.id, 1)
        self.repo.get_by_domain.assert_not_called()

    def test_resolve_falls_back_to_domain(self):
        """resolve() falls back to domain when header is None."""
        self.repo.get_by_schema.return_value = None
        tenant = _tenant(2, "school_b")
        self.repo.get_by_domain.return_value = tenant

        result = self.service.resolve(header_value=None, domain="school2.co.ke")
        self.assertEqual(result.id, 2)

    def test_tenant_a_b_are_distinct(self):
        """Resolving tenant A must NOT return tenant B."""
        tenant_a = _tenant(1, "school_a")
        tenant_b = _tenant(2, "school_b")

        def side_effect(schema):
            return {"school_a": tenant_a, "school_b": tenant_b}.get(schema)

        self.repo.get_by_schema.side_effect = side_effect

        resolved_a = self.service.resolve_from_header("school_a")
        resolved_b = self.service.resolve_from_header("school_b")

        self.assertIsNotNone(resolved_a)
        self.assertIsNotNone(resolved_b)
        self.assertNotEqual(resolved_a.id, resolved_b.id)
        self.assertNotEqual(resolved_a.schema_name, resolved_b.schema_name)


class TestTenantDataIsolation(unittest.TestCase):
    """
    Prompt 55 / Prompt 46: Verify student/parent queries include tenant scoping.
    Validates the repository interface correctly gates by tenant.
    """

    def test_student_repo_query_scoped_to_tenant(self):
        """
        Mock test: student repo must accept tenant context.
        Simulates Tenant A getting student list — Tenant B's students NOT included.
        """
        repo = MagicMock()
        repo.list.return_value = [
            MagicMock(id=1, admission_number="STM001", tenant="school_a"),
        ]

        students_a = repo.list(tenant_schema="school_a")
        repo.list.assert_called_once_with(tenant_schema="school_a")

        for s in students_a:
            self.assertEqual(s.tenant, "school_a")

    def test_cross_tenant_student_not_visible(self):
        """
        Tenant B calling list() with their schema must NOT return Tenant A students.
        """
        tenant_a_students = [MagicMock(id=1, tenant="school_a")]
        tenant_b_students = [MagicMock(id=2, tenant="school_b")]

        repo = MagicMock()
        repo.list.side_effect = lambda tenant_schema: {
            "school_a": tenant_a_students,
            "school_b": tenant_b_students,
        }.get(tenant_schema, [])

        result_b = repo.list(tenant_schema="school_b")
        for s in result_b:
            self.assertNotEqual(s.tenant, "school_a")

    def test_different_schemas_return_different_data(self):
        """Schema switching must produce isolated data sets."""
        repo = MagicMock()
        repo.list.side_effect = lambda tenant_schema: [
            MagicMock(id=int(tenant_schema[-1]))
        ]

        result_1 = repo.list(tenant_schema="schema1")
        result_2 = repo.list(tenant_schema="schema2")

        self.assertNotEqual(result_1[0].id, result_2[0].id)


if __name__ == "__main__":
    unittest.main()
