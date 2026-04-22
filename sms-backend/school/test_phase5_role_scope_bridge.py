from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from school.models import Role
from school.permissions import (
    HasModuleAccess,
    IsAcademicStaff,
    IsAccountant,
    IsSchoolAdmin,
    IsTeacher,
)
from school.role_scope import (
    LEGACY_ROLE_BRIDGE,
    ROLE_SCOPE_PROFILE,
    SCOPE_ACADEMIC_LEAD,
    SCOPE_FINANCE_MANAGER,
    SCOPE_SCHOOL_ADMIN,
    SCOPE_SECRETARY_SUPPORT,
    resolve_scope_profile,
)


def _mock_user(role_name: str | None = None, *, authenticated: bool = True):
    attrs = {"is_authenticated": authenticated}
    if role_name is not None:
        attrs["userprofile"] = SimpleNamespace(role=SimpleNamespace(name=role_name))
    return SimpleNamespace(**attrs)


class Phase5RoleScopeBridgeTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _request(self, user):
        request = self.factory.get("/api/test/")
        request.user = user
        return request

    def test_role_choices_include_session5_roles(self):
        choices = dict(Role._meta.get_field("name").choices)

        self.assertEqual(choices["PRINCIPAL"], "School Principal")
        self.assertEqual(choices["DEPUTY_PRINCIPAL"], "Deputy Principal")
        self.assertEqual(choices["HOD"], "Head of Department")
        self.assertEqual(choices["BURSAR"], "School Bursar")
        self.assertEqual(choices["HR_OFFICER"], "HR Officer")
        self.assertEqual(choices["REGISTRAR"], "Registrar")
        self.assertEqual(choices["SECRETARY"], "School Secretary")
        self.assertEqual(choices["SECURITY_GUARD"], "Security Guard")
        self.assertEqual(choices["STORE_CLERK"], "Store Clerk")
        self.assertEqual(choices["ALUMNI"], "Alumni")

    def test_scope_maps_cover_legacy_and_new_role_families(self):
        self.assertEqual(ROLE_SCOPE_PROFILE["PRINCIPAL"], SCOPE_SCHOOL_ADMIN)
        self.assertEqual(ROLE_SCOPE_PROFILE["HOD"], SCOPE_ACADEMIC_LEAD)
        self.assertEqual(ROLE_SCOPE_PROFILE["SECRETARY"], SCOPE_SECRETARY_SUPPORT)
        self.assertEqual(LEGACY_ROLE_BRIDGE["ACCOUNTANT"], SCOPE_FINANCE_MANAGER)
        self.assertEqual(resolve_scope_profile("BURSAR"), SCOPE_FINANCE_MANAGER)
        self.assertEqual(resolve_scope_profile("SECRETARY"), SCOPE_SECRETARY_SUPPORT)
        self.assertEqual(resolve_scope_profile("ADMIN"), SCOPE_SCHOOL_ADMIN)

    def test_principal_is_allowed_school_admin_guard(self):
        user = _mock_user("PRINCIPAL")

        allowed = IsSchoolAdmin().has_permission(self._request(user), SimpleNamespace())

        self.assertTrue(allowed)

    def test_bursar_is_allowed_finance_guard(self):
        user = _mock_user("BURSAR")

        allowed = IsAccountant().has_permission(self._request(user), SimpleNamespace())

        self.assertTrue(allowed)

    def test_hod_is_allowed_teacher_and_academic_staff_guards(self):
        user = _mock_user("HOD")
        request = self._request(user)

        self.assertTrue(IsTeacher().has_permission(request, SimpleNamespace()))
        self.assertTrue(IsAcademicStaff().has_permission(request, SimpleNamespace()))

    def test_bursar_is_not_treated_as_school_admin(self):
        user = _mock_user("BURSAR")

        allowed = IsSchoolAdmin().has_permission(self._request(user), SimpleNamespace())

        self.assertFalse(allowed)

    def test_principal_bypasses_module_gate_as_admin_scope(self):
        user = _mock_user("PRINCIPAL")
        request = self._request(user)
        view = SimpleNamespace(module_key="FINANCE")

        allowed = HasModuleAccess().has_permission(request, view)

        self.assertTrue(allowed)

    def test_parent_and_student_portal_inherent_access_still_work(self):
        parent_request = self._request(_mock_user("PARENT"))
        student_request = self._request(_mock_user("STUDENT"))

        self.assertTrue(
            HasModuleAccess().has_permission(parent_request, SimpleNamespace(module_key="PARENT_PORTAL"))
        )
        self.assertTrue(
            HasModuleAccess().has_permission(student_request, SimpleNamespace(module_key="STUDENT_PORTAL"))
        )

    def test_unauthenticated_request_is_denied(self):
        request = self._request(_mock_user("PRINCIPAL", authenticated=False))

        self.assertFalse(IsSchoolAdmin().has_permission(request, SimpleNamespace()))
        self.assertFalse(HasModuleAccess().has_permission(request, SimpleNamespace(module_key="FINANCE")))
