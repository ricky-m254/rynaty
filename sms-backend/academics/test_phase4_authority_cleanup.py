from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, UserProfile

from .models import AcademicYear, Term
from .views import TermViewSet, TermsRefView

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="academics_phase4_cleanup",
                name="Academics Phase 4 Cleanup School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="academics-phase4.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class AcademicsAuthorityCleanupTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="phase4_admin", password="pass1234")
        role, _ = Role.objects.get_or_create(
            name="ADMIN",
            defaults={"description": "School Administrator"},
        )
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.get_or_create(key="ACADEMICS", defaults={"name": "Academics"})

        self.year = AcademicYear.objects.create(
            name="2026-2027",
            start_date="2026-01-01",
            end_date="2026-12-31",
            is_active=True,
            is_current=True,
        )
        self.current_term = Term.objects.create(
            academic_year=self.year,
            name="Term 1",
            start_date="2026-01-01",
            end_date="2026-04-30",
            billing_date="2026-01-10",
            is_active=True,
            is_current=True,
        )
        self.active_term = Term.objects.create(
            academic_year=self.year,
            name="Term 2",
            start_date="2026-05-01",
            end_date="2026-08-31",
            billing_date="2026-05-10",
            is_active=True,
            is_current=False,
        )
        self.archived_term = Term.objects.create(
            academic_year=self.year,
            name="Archived Term",
            start_date="2025-09-01",
            end_date="2025-12-15",
            billing_date="2025-09-10",
            is_active=False,
            is_current=False,
        )

    def test_terms_ref_supports_active_filter_for_selector_consumers(self):
        request = self.factory.get("/api/academics/ref/terms/?is_active=true")
        force_authenticate(request, user=self.user)

        response = TermsRefView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        returned_ids = {row["id"] for row in response.data}
        self.assertIn(self.current_term.id, returned_ids)
        self.assertIn(self.active_term.id, returned_ids)
        self.assertNotIn(self.archived_term.id, returned_ids)

    def test_terms_viewset_supports_inactive_filter_for_authority_audits(self):
        request = self.factory.get("/api/academics/terms/?is_active=false")
        force_authenticate(request, user=self.user)

        response = TermViewSet.as_view({"get": "list"})(request)

        self.assertEqual(response.status_code, 200)
        returned_ids = [row["id"] for row in response.data]
        self.assertEqual(returned_ids, [self.archived_term.id])
