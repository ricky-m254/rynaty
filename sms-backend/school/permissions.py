import re

from rest_framework import permissions

from .module_focus import is_module_allowed
from .role_scope import (
    ACADEMIC_SCOPE_PROFILES,
    ADMIN_SCOPE_PROFILES,
    FINANCE_SCOPE_PROFILES,
    get_user_role_name,
    get_user_scope_profile,
    user_has_any_scope,
)


def _ensure_request_permission_state(request):
    existing_has_permission = getattr(request, "has_permission", None)
    existing_effective = getattr(request, "effective_permissions", None)
    if callable(existing_has_permission) and isinstance(existing_effective, set):
        return existing_effective

    user = getattr(request, "user", None)
    effective = set()
    if user and user.is_authenticated:
        try:
            from domains.auth.application.permission_resolver_service import PermissionResolverService
            from domains.auth.infrastructure.django_override_repository import (
                DjangoUserPermissionOverrideRepository,
            )
            from domains.auth.infrastructure.django_permission_repository import DjangoPermissionRepository
            from domains.auth.infrastructure.django_user_repository import DjangoUserRepository

            resolver = PermissionResolverService(
                user_repo=DjangoUserRepository(),
                permission_repo=DjangoPermissionRepository(),
                override_repo=DjangoUserPermissionOverrideRepository(),
            )
            effective = set(resolver.resolve(user.pk))
        except Exception:
            effective = set()

    request.effective_permissions = effective
    request.has_permission = lambda permission_name: permission_name in effective
    return effective


def request_has_resolved_permission(request, permission_name: str | None) -> bool:
    if not permission_name:
        return False
    return permission_name in _ensure_request_permission_state(request)


def request_has_any_resolved_permission(request, permission_names) -> bool:
    effective = _ensure_request_permission_state(request)
    return any(permission_name in effective for permission_name in permission_names if permission_name)


def request_has_any_scope(request, allowed_scopes) -> bool:
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user_has_any_scope(user, allowed_scopes))


def request_can_manage_rbac(request) -> bool:
    return request_has_any_scope(request, ADMIN_SCOPE_PROFILES) or request_has_resolved_permission(
        request, "settings.rbac.manage"
    )


def request_can_manage_system_settings(request) -> bool:
    return request_has_any_scope(request, ADMIN_SCOPE_PROFILES) or request_has_resolved_permission(
        request, "settings.system.manage"
    )


def request_can_manage_module_settings(request) -> bool:
    return request_has_any_scope(request, ADMIN_SCOPE_PROFILES) or request_has_resolved_permission(
        request, "settings.modules.manage"
    )


def _configured_permission_type_name(prefix: str, values) -> str:
    suffix = "_".join(str(value) for value in values if value)
    suffix = re.sub(r"[^A-Za-z0-9_]+", "_", suffix).strip("_") or "Configured"
    return f"{prefix}{suffix}"


class IsSchoolAdmin(permissions.BasePermission):
    """
    Allows access only to admin-family school roles.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return user_has_any_scope(request.user, ADMIN_SCOPE_PROFILES)


class IsAccountant(permissions.BasePermission):
    """
    Allows access only to finance-family roles or admin-family roles.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return user_has_any_scope(request.user, FINANCE_SCOPE_PROFILES)


class IsTeacher(permissions.BasePermission):
    """
    Allows access only to academic-family roles or admin-family roles.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return user_has_any_scope(request.user, ACADEMIC_SCOPE_PROFILES)


class HasResolvedPermission(permissions.BasePermission):
    """
    Checks a single resolved permission name using the existing request helper
    or the same underlying resolver service when middleware is not present.
    """

    permission_name = None
    permission_attr = "required_permission"

    @classmethod
    def named(cls, permission_name: str):
        return type(
            _configured_permission_type_name(cls.__name__, [permission_name]),
            (cls,),
            {"permission_name": permission_name},
        )

    def get_permission_name(self, view):
        return getattr(view, self.permission_attr, None) or self.permission_name

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request_has_resolved_permission(request, self.get_permission_name(view))


class HasAnyResolvedPermission(permissions.BasePermission):
    """
    Checks multiple resolved permission names and passes when any one matches.
    """

    permission_names = ()
    permission_attr = "required_permissions"

    @classmethod
    def named(cls, *permission_names: str):
        return type(
            _configured_permission_type_name(cls.__name__, permission_names),
            (cls,),
            {"permission_names": tuple(permission_names)},
        )

    def get_permission_names(self, view):
        return tuple(getattr(view, self.permission_attr, ()) or self.permission_names)

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request_has_any_resolved_permission(request, self.get_permission_names(view))


class HasScopeProfile(permissions.BasePermission):
    """
    Checks whether the current user resolves into one of the allowed scope profiles.
    """

    allowed_scopes = ()

    @classmethod
    def scoped(cls, *allowed_scopes: str):
        return type(
            _configured_permission_type_name(cls.__name__, allowed_scopes),
            (cls,),
            {"allowed_scopes": tuple(allowed_scopes)},
        )

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return user_has_any_scope(request.user, self.allowed_scopes)


CanManageRbac = HasScopeProfile.scoped(*ADMIN_SCOPE_PROFILES) | HasResolvedPermission.named(
    "settings.rbac.manage"
)
CanManageSystemSettings = HasScopeProfile.scoped(
    *ADMIN_SCOPE_PROFILES
) | HasResolvedPermission.named("settings.system.manage")
CanManageModuleSettings = HasScopeProfile.scoped(
    *ADMIN_SCOPE_PROFILES
) | HasResolvedPermission.named("settings.modules.manage")


_PORTAL_ROLE_MODULE_KEYS = {
    "PARENT": {"PARENTS", "PARENT_PORTAL"},
    "STUDENT": {"STUDENT_PORTAL", "STUDENTS_PORTAL"},
}


def _normalize_module_keys(module_keys) -> tuple[str, ...]:
    if module_keys is None:
        return ()
    if isinstance(module_keys, str):
        raw_keys = (module_keys,)
    else:
        try:
            raw_keys = tuple(module_keys)
        except TypeError:
            raw_keys = (module_keys,)

    normalized: list[str] = []
    seen: set[str] = set()
    for key in raw_keys:
        normalized_key = str(key or "").strip().upper()
        if not normalized_key or normalized_key in seen:
            continue
        seen.add(normalized_key)
        normalized.append(normalized_key)
    return tuple(normalized)


def request_has_module_access(request, module_keys) -> bool:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False

    normalized_keys = _normalize_module_keys(module_keys)
    if not normalized_keys:
        return True
    if any(not is_module_allowed(module_key) for module_key in normalized_keys):
        return False

    role_name = get_user_role_name(user)
    scope_profile = get_user_scope_profile(user)
    if scope_profile in ADMIN_SCOPE_PROFILES:
        return True

    allowed_keys = _PORTAL_ROLE_MODULE_KEYS.get(role_name, set())
    if any(module_key in allowed_keys for module_key in normalized_keys):
        return True

    from .models import UserModuleAssignment

    return UserModuleAssignment.objects.filter(
        user=user,
        module__key__in=normalized_keys,
        module__is_active=True,
        is_active=True,
    ).exists()


class HasModuleAccess(permissions.BasePermission):
    """
    Enforces per-module access using UserModuleAssignment.
    ViewSets should define `module_key` (e.g., "FINANCE", "STUDENTS").
    Admin-family roles bypass module checks.
    PARENT role automatically passes PARENTS module.
    STUDENT role automatically passes STUDENT_PORTAL module.
    """

    _PORTAL_ROLE_MAP = _PORTAL_ROLE_MODULE_KEYS

    def get_module_keys(self, view):
        if hasattr(view, "get_module_keys") and callable(view.get_module_keys):
            return view.get_module_keys()
        module_keys = getattr(view, "module_keys", None)
        if module_keys is not None:
            return module_keys
        return getattr(view, "module_key", None)

    def has_permission(self, request, view):
        return request_has_module_access(request, self.get_module_keys(view))


class IsAcademicStaff(permissions.BasePermission):
    """
    Allows access only to teaching/academic authority roles.
    Parents and finance-only users are denied even if module assignment exists.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return user_has_any_scope(request.user, ACADEMIC_SCOPE_PROFILES)
