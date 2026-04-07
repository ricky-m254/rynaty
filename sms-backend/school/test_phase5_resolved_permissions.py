from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.domain_views import SchoolDomainStatusView
from school.models import Module, Permission, Role, UserProfile
from school.rbac_views import RbacPermissionListView, RbacUserEffectivePermissionsView
from school.views import TenantModuleListView, TenantSettingsView

User = get_user_model()


class TenantPhase5ResolvedPermissionBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="phase5_resolved_permissions_test",
                name="Phase 5 Resolved Permissions Test",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="phase5-resolved.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.factory = APIRequestFactory()
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)

    @staticmethod
    def _create_user(username: str, role_name: str):
        user = User.objects.create_user(username=username, password="pass1234")
        role, _ = Role.objects.get_or_create(name=role_name, defaults={"description": role_name.title()})
        UserProfile.objects.update_or_create(user=user, defaults={"role": role})
        return user

    @staticmethod
    def _attach_resolved_permissions(request, *permission_names: str):
        effective = {name for name in permission_names if name}
        request.effective_permissions = effective
        request.has_permission = lambda permission_name: permission_name in effective
        return request


class Phase5ResolvedPermissionEndpointTests(TenantPhase5ResolvedPermissionBase):
    def test_principal_can_read_rbac_permission_catalog_via_admin_scope(self):
        principal = self._create_user("phase5_principal_rbac", "PRINCIPAL")

        request = self.factory.get("/api/rbac/permissions/")
        force_authenticate(request, user=principal)
        response = RbacPermissionListView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_resolved_rbac_permission_can_open_rbac_catalog_for_non_admin(self):
        teacher = self._create_user("phase5_teacher_rbac_delegate", "TEACHER")

        request = self.factory.get("/api/rbac/permissions/")
        force_authenticate(request, user=teacher)
        self._attach_resolved_permissions(request, "settings.rbac.manage")
        response = RbacPermissionListView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_under_scoped_user_is_denied_rbac_catalog(self):
        teacher = self._create_user("phase5_teacher_rbac_denied", "TEACHER")

        request = self.factory.get("/api/rbac/permissions/")
        force_authenticate(request, user=teacher)
        response = RbacPermissionListView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_principal_permissions_view_returns_admin_catalog(self):
        principal = self._create_user("phase5_principal_effective", "PRINCIPAL")
        Permission.objects.create(
            name="settings.rbac.manage",
            module="settings",
            action="manage",
            description="Manage RBAC",
        )
        Permission.objects.create(
            name="settings.system.manage",
            module="settings",
            action="manage",
            description="Manage system settings",
        )

        request = self.factory.get(f"/api/rbac/users/{principal.id}/permissions/")
        force_authenticate(request, user=principal)
        response = RbacUserEffectivePermissionsView.as_view()(request, user_id=principal.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_admin"])
        self.assertIn("settings.rbac.manage", response.data["permissions"])
        self.assertIn("settings.system.manage", response.data["permissions"])

    def test_teacher_can_view_own_permissions_but_not_another_users(self):
        teacher = self._create_user("phase5_teacher_self_permissions", "TEACHER")
        colleague = self._create_user("phase5_teacher_other_permissions", "TEACHER")

        own_request = self.factory.get(f"/api/rbac/users/{teacher.id}/permissions/")
        force_authenticate(own_request, user=teacher)
        own_response = RbacUserEffectivePermissionsView.as_view()(own_request, user_id=teacher.id)

        other_request = self.factory.get(f"/api/rbac/users/{colleague.id}/permissions/")
        force_authenticate(other_request, user=teacher)
        other_response = RbacUserEffectivePermissionsView.as_view()(other_request, user_id=colleague.id)

        self.assertEqual(own_response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_resolved_system_settings_permission_can_read_tenant_settings(self):
        teacher = self._create_user("phase5_teacher_settings_delegate", "TEACHER")

        request = self.factory.get("/api/settings/")
        force_authenticate(request, user=teacher)
        self._attach_resolved_permissions(request, "settings.system.manage")
        response = TenantSettingsView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_under_scoped_user_is_denied_tenant_settings(self):
        teacher = self._create_user("phase5_teacher_settings_denied", "TEACHER")

        request = self.factory.get("/api/settings/")
        force_authenticate(request, user=teacher)
        response = TenantSettingsView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_resolved_module_settings_permission_can_read_tenant_modules(self):
        teacher = self._create_user("phase5_teacher_module_delegate", "TEACHER")
        Module.objects.create(key="CORE", name="Core", is_active=True)

        request = self.factory.get("/api/tenant/modules")
        force_authenticate(request, user=teacher)
        self._attach_resolved_permissions(request, "settings.modules.manage")
        response = TenantModuleListView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_domain_status_uses_same_system_settings_gate(self):
        teacher = self._create_user("phase5_teacher_domain_denied", "TEACHER")
        principal = self._create_user("phase5_principal_domain_allowed", "PRINCIPAL")

        denied_request = self.factory.get("/api/settings/domain/")
        force_authenticate(denied_request, user=teacher)
        denied_request.tenant = self.tenant
        denied_response = SchoolDomainStatusView.as_view()(denied_request)

        allowed_request = self.factory.get("/api/settings/domain/")
        force_authenticate(allowed_request, user=principal)
        allowed_request.tenant = self.tenant
        allowed_response = SchoolDomainStatusView.as_view()(allowed_request)

        self.assertEqual(denied_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(allowed_response.status_code, status.HTTP_200_OK)
