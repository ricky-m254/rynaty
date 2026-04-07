from __future__ import annotations

from typing import Iterable, Sequence

ROLE_SEED_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("TENANT_SUPER_ADMIN", "Tenant Super Admin"),
    ("ADMIN", "School Administrator"),
    ("PRINCIPAL", "School Principal"),
    ("DEPUTY_PRINCIPAL", "Deputy Principal"),
    ("HOD", "Head of Department"),
    ("ACCOUNTANT", "Finance Manager"),
    ("BURSAR", "School Bursar"),
    ("HR_OFFICER", "HR Officer"),
    ("REGISTRAR", "Registrar"),
    ("TEACHER", "Teaching Staff"),
    ("LIBRARIAN", "School Librarian"),
    ("NURSE", "School Nurse"),
    ("SECURITY", "Security Staff"),
    ("SECURITY_GUARD", "Security Guard"),
    ("COOK", "Kitchen / Cook"),
    ("STORE_CLERK", "Store Clerk"),
    ("PARENT", "Parent / Guardian"),
    ("STUDENT", "Student"),
    ("ALUMNI", "Alumni"),
)
ROLE_SEED_DESCRIPTION_MAP = dict(ROLE_SEED_DEFINITIONS)

SCOPE_FULL_TENANT_ADMIN = "FULL_TENANT_ADMIN"
SCOPE_SCHOOL_ADMIN = "SCHOOL_ADMIN"
SCOPE_FINANCE_MANAGER = "FINANCE_MANAGER"
SCOPE_ACADEMIC_STAFF = "ACADEMIC_STAFF"
SCOPE_ACADEMIC_LEAD = "ACADEMIC_LEAD"
SCOPE_HR_MANAGER = "HR_MANAGER"
SCOPE_REGISTRAR_OPERATIONS = "REGISTRAR_OPERATIONS"
SCOPE_LIBRARY_OPERATIONS = "LIBRARY_OPERATIONS"
SCOPE_HEALTH_OPERATIONS = "HEALTH_OPERATIONS"
SCOPE_SECURITY_OPERATIONS = "SECURITY_OPERATIONS"
SCOPE_CATERING_OPERATIONS = "CATERING_OPERATIONS"
SCOPE_STORE_OPERATIONS = "STORE_OPERATIONS"
SCOPE_PARENT_PORTAL = "PARENT_PORTAL"
SCOPE_STUDENT_PORTAL = "STUDENT_PORTAL"
SCOPE_ALUMNI_PORTAL = "ALUMNI_PORTAL"
ALL_ENABLED_MODULES = "__ALL_ENABLED_MODULES__"

# Canonical Session 5 role names.
ROLE_SCOPE_PROFILE = {
    "PRINCIPAL": SCOPE_SCHOOL_ADMIN,
    "DEPUTY_PRINCIPAL": SCOPE_SCHOOL_ADMIN,
    "HOD": SCOPE_ACADEMIC_LEAD,
    "BURSAR": SCOPE_FINANCE_MANAGER,
    "HR_OFFICER": SCOPE_HR_MANAGER,
    "REGISTRAR": SCOPE_REGISTRAR_OPERATIONS,
    "LIBRARIAN": SCOPE_LIBRARY_OPERATIONS,
    "NURSE": SCOPE_HEALTH_OPERATIONS,
    "SECURITY_GUARD": SCOPE_SECURITY_OPERATIONS,
    "COOK": SCOPE_CATERING_OPERATIONS,
    "STORE_CLERK": SCOPE_STORE_OPERATIONS,
    "PARENT": SCOPE_PARENT_PORTAL,
    "STUDENT": SCOPE_STUDENT_PORTAL,
    "ALUMNI": SCOPE_ALUMNI_PORTAL,
}

# Transitional bridge for legacy/current role names already present in tenants.
LEGACY_ROLE_BRIDGE = {
    "TENANT_SUPER_ADMIN": SCOPE_FULL_TENANT_ADMIN,
    "ADMIN": SCOPE_SCHOOL_ADMIN,
    "ACCOUNTANT": SCOPE_FINANCE_MANAGER,
    "TEACHER": SCOPE_ACADEMIC_STAFF,
    "SECURITY": SCOPE_SECURITY_OPERATIONS,
}

ADMIN_SCOPE_PROFILES = {SCOPE_FULL_TENANT_ADMIN, SCOPE_SCHOOL_ADMIN}
FINANCE_SCOPE_PROFILES = ADMIN_SCOPE_PROFILES | {SCOPE_FINANCE_MANAGER}
ACADEMIC_SCOPE_PROFILES = ADMIN_SCOPE_PROFILES | {
    SCOPE_ACADEMIC_STAFF,
    SCOPE_ACADEMIC_LEAD,
}

SCOPE_MODULE_BASELINES = {
    SCOPE_FULL_TENANT_ADMIN: ALL_ENABLED_MODULES,
    SCOPE_SCHOOL_ADMIN: ALL_ENABLED_MODULES,
    SCOPE_FINANCE_MANAGER: (
        "FINANCE",
        "STUDENTS",
        "REPORTING",
        "COMMUNICATION",
    ),
    SCOPE_ACADEMIC_STAFF: (
        "ACADEMICS",
        "STUDENTS",
        "TIMETABLE",
        "EXAMINATIONS",
        "CURRICULUM",
        "ELEARNING",
        "COMMUNICATION",
    ),
    SCOPE_ACADEMIC_LEAD: (
        "ACADEMICS",
        "STUDENTS",
        "TIMETABLE",
        "EXAMINATIONS",
        "CURRICULUM",
        "ELEARNING",
        "COMMUNICATION",
        "REPORTING",
    ),
    SCOPE_HR_MANAGER: (
        "HR",
        "STAFF",
        "CLOCKIN",
        "REPORTING",
        "COMMUNICATION",
    ),
    SCOPE_REGISTRAR_OPERATIONS: (
        "ADMISSIONS",
        "STUDENTS",
        "ACADEMICS",
        "PARENTS",
        "COMMUNICATION",
        "REPORTING",
    ),
    SCOPE_LIBRARY_OPERATIONS: (
        "LIBRARY",
        "STUDENTS",
        "PARENTS",
        "COMMUNICATION",
    ),
    SCOPE_HEALTH_OPERATIONS: (
        "DISPENSARY",
        "STUDENTS",
        "COMMUNICATION",
    ),
    SCOPE_SECURITY_OPERATIONS: (
        "VISITOR_MGMT",
        "CLOCKIN",
        "COMMUNICATION",
    ),
    SCOPE_CATERING_OPERATIONS: (
        "CAFETERIA",
        "STUDENTS",
        "COMMUNICATION",
    ),
    SCOPE_STORE_OPERATIONS: (
        "STORE",
        "ASSETS",
        "COMMUNICATION",
    ),
    # Parent and student portal access stays inherent in HasModuleAccess.
    SCOPE_PARENT_PORTAL: (),
    SCOPE_STUDENT_PORTAL: (),
    SCOPE_ALUMNI_PORTAL: ("ALUMNI",),
}


def normalize_role_name(role_name: str | None) -> str | None:
    if role_name is None:
        return None
    normalized = str(role_name).strip().upper()
    return normalized or None


def resolve_scope_profile(role_name: str | None) -> str | None:
    normalized = normalize_role_name(role_name)
    if normalized is None:
        return None
    return ROLE_SCOPE_PROFILE.get(normalized) or LEGACY_ROLE_BRIDGE.get(normalized)


def get_user_role_name(user) -> str | None:
    profile = getattr(user, "userprofile", None)
    role = getattr(profile, "role", None)
    return normalize_role_name(getattr(role, "name", None))


def get_user_scope_profile(user) -> str | None:
    return resolve_scope_profile(get_user_role_name(user))


def scope_in(scope_profile: str | None, allowed_scopes: Iterable[str]) -> bool:
    return bool(scope_profile and scope_profile in set(allowed_scopes))


def user_has_any_scope(user, allowed_scopes: Iterable[str]) -> bool:
    return scope_in(get_user_scope_profile(user), allowed_scopes)


def is_admin_scope(scope_profile: str | None) -> bool:
    return scope_in(scope_profile, ADMIN_SCOPE_PROFILES)


def is_finance_scope(scope_profile: str | None) -> bool:
    return scope_in(scope_profile, FINANCE_SCOPE_PROFILES)


def is_academic_scope(scope_profile: str | None) -> bool:
    return scope_in(scope_profile, ACADEMIC_SCOPE_PROFILES)


def iter_seed_role_names() -> tuple[str, ...]:
    return tuple(role_name for role_name, _ in ROLE_SEED_DEFINITIONS)


def iter_seed_role_definitions() -> tuple[tuple[str, str], ...]:
    return ROLE_SEED_DEFINITIONS


def get_scope_module_baseline(
    scope_profile: str | None,
    *,
    available_module_keys: Sequence[str] | None = None,
) -> tuple[str, ...]:
    baseline = SCOPE_MODULE_BASELINES.get(scope_profile, ())
    available_ordered = None
    available_set = None
    if available_module_keys is not None:
        available_ordered = []
        available_set = set()
        for key in available_module_keys:
            normalized = normalize_role_name(key)
            if not normalized or normalized in available_set:
                continue
            available_ordered.append(normalized)
            available_set.add(normalized)

    if baseline == ALL_ENABLED_MODULES:
        raw_keys = tuple(available_ordered or ())
    else:
        raw_keys = tuple(baseline)

    resolved: list[str] = []
    seen: set[str] = set()
    for key in raw_keys:
        normalized = normalize_role_name(key)
        if not normalized or normalized in seen:
            continue
        if available_set is not None and normalized not in available_set:
            continue
        seen.add(normalized)
        resolved.append(normalized)
    return tuple(resolved)


def get_role_module_baseline(
    role_name: str | None,
    *,
    available_module_keys: Sequence[str] | None = None,
) -> tuple[str, ...]:
    return get_scope_module_baseline(
        resolve_scope_profile(role_name),
        available_module_keys=available_module_keys,
    )


def materialize_role_module_baseline(user, role_name: str | None, *, assigned_by=None) -> dict:
    from .models import Module, UserModuleAssignment

    modules = {
        module.key.upper(): module
        for module in Module.objects.filter(is_active=True).order_by("key")
    }
    available_module_keys = tuple(modules.keys())
    desired_keys = get_role_module_baseline(
        role_name,
        available_module_keys=available_module_keys,
    )
    missing_module_keys = tuple(
        module_key
        for module_key in get_role_module_baseline(role_name)
        if module_key not in modules
    )

    existing_by_key = {
        assignment.module.key.upper(): assignment
        for assignment in UserModuleAssignment.objects.filter(
            user=user,
            module__is_active=True,
        ).select_related("module")
    }

    created: list[str] = []
    reactivated: list[str] = []
    unchanged: list[str] = []

    for module_key in desired_keys:
        existing = existing_by_key.get(module_key)
        if existing is None:
            UserModuleAssignment.objects.create(
                user=user,
                module=modules[module_key],
                assigned_by=assigned_by,
                is_active=True,
            )
            created.append(module_key)
            continue

        if not existing.is_active:
            existing.is_active = True
            if assigned_by and existing.assigned_by_id != getattr(assigned_by, "id", None):
                existing.assigned_by = assigned_by
                existing.save(update_fields=["is_active", "assigned_by"])
            else:
                existing.save(update_fields=["is_active"])
            reactivated.append(module_key)
            continue

        unchanged.append(module_key)

    return {
        "scope_profile": resolve_scope_profile(role_name),
        "assigned_module_keys": desired_keys,
        "missing_module_keys": missing_module_keys,
        "created_module_keys": tuple(created),
        "reactivated_module_keys": tuple(reactivated),
        "unchanged_module_keys": tuple(unchanged),
    }
