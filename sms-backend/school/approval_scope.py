from __future__ import annotations

from typing import Iterable

from .role_scope import (
    ADMIN_SCOPE_PROFILES,
    SCOPE_ACADEMIC_LEAD,
    SCOPE_FINANCE_MANAGER,
    SCOPE_HR_MANAGER,
    SCOPE_LIBRARY_OPERATIONS,
    SCOPE_REGISTRAR_OPERATIONS,
    get_user_role_name,
    get_user_scope_profile,
    normalize_role_name,
)

APPROVAL_CATEGORY_WRITEOFFS = "writeoffs"
APPROVAL_CATEGORY_REVERSALS = "reversals"
APPROVAL_CATEGORY_ADJUSTMENTS = "adjustments"
APPROVAL_CATEGORY_STORE_ORDERS = "store_orders"
APPROVAL_CATEGORY_LEAVE = "leave"
APPROVAL_CATEGORY_ACQUISITIONS = "acquisitions"
APPROVAL_CATEGORY_TIMETABLE = "timetable"
APPROVAL_CATEGORY_ADMISSIONS = "admissions"
APPROVAL_CATEGORY_MAINTENANCE = "maintenance"

ALL_APPROVAL_CATEGORIES = (
    APPROVAL_CATEGORY_WRITEOFFS,
    APPROVAL_CATEGORY_REVERSALS,
    APPROVAL_CATEGORY_ADJUSTMENTS,
    APPROVAL_CATEGORY_STORE_ORDERS,
    APPROVAL_CATEGORY_LEAVE,
    APPROVAL_CATEGORY_ACQUISITIONS,
    APPROVAL_CATEGORY_TIMETABLE,
    APPROVAL_CATEGORY_ADMISSIONS,
    APPROVAL_CATEGORY_MAINTENANCE,
)

_APPROVAL_CATEGORIES_BY_SCOPE = {
    SCOPE_FINANCE_MANAGER: (
        APPROVAL_CATEGORY_WRITEOFFS,
        APPROVAL_CATEGORY_REVERSALS,
        APPROVAL_CATEGORY_ADJUSTMENTS,
        APPROVAL_CATEGORY_STORE_ORDERS,
    ),
    SCOPE_HR_MANAGER: (APPROVAL_CATEGORY_LEAVE,),
    SCOPE_LIBRARY_OPERATIONS: (APPROVAL_CATEGORY_ACQUISITIONS,),
    SCOPE_ACADEMIC_LEAD: (APPROVAL_CATEGORY_TIMETABLE,),
    SCOPE_REGISTRAR_OPERATIONS: (APPROVAL_CATEGORY_ADMISSIONS,),
}

_APPROVAL_CATEGORIES_BY_LEGACY_ROLE = {
    "OWNER": ALL_APPROVAL_CATEGORIES,
    "FINANCE": _APPROVAL_CATEGORIES_BY_SCOPE[SCOPE_FINANCE_MANAGER],
    "HR": _APPROVAL_CATEGORIES_BY_SCOPE[SCOPE_HR_MANAGER],
    "HR_STAFF": _APPROVAL_CATEGORIES_BY_SCOPE[SCOPE_HR_MANAGER],
    "LIBRARY_STAFF": _APPROVAL_CATEGORIES_BY_SCOPE[SCOPE_LIBRARY_OPERATIONS],
    "ADMISSIONS": _APPROVAL_CATEGORIES_BY_SCOPE[SCOPE_REGISTRAR_OPERATIONS],
    "ADMISSIONS_OFFICER": _APPROVAL_CATEGORIES_BY_SCOPE[SCOPE_REGISTRAR_OPERATIONS],
    "TIMETABLE_OFFICER": _APPROVAL_CATEGORIES_BY_SCOPE[SCOPE_ACADEMIC_LEAD],
    "MAINTENANCE_STAFF": (APPROVAL_CATEGORY_MAINTENANCE,),
}


def normalize_approval_category(category_key: str | None) -> str | None:
    normalized = normalize_role_name(category_key)
    return normalized.lower() if normalized else None


def get_approval_categories_for_scope(scope_profile: str | None) -> tuple[str, ...]:
    if scope_profile in ADMIN_SCOPE_PROFILES:
        return ALL_APPROVAL_CATEGORIES
    return _APPROVAL_CATEGORIES_BY_SCOPE.get(scope_profile, ())


def get_approval_categories_for_role_name(role_name: str | None) -> tuple[str, ...]:
    normalized_role = normalize_role_name(role_name)
    if normalized_role is None:
        return ()

    scope_categories = get_approval_categories_for_scope(get_user_scope_profile_from_role_name(normalized_role))
    if scope_categories:
        return scope_categories
    return _APPROVAL_CATEGORIES_BY_LEGACY_ROLE.get(normalized_role, ())


def get_user_approval_categories(user) -> tuple[str, ...]:
    scope_categories = get_approval_categories_for_scope(get_user_scope_profile(user))
    if scope_categories:
        return scope_categories
    return _APPROVAL_CATEGORIES_BY_LEGACY_ROLE.get(get_user_role_name(user) or "", ())


def user_can_access_approval_category(user, category_key: str | None) -> bool:
    normalized_category = normalize_approval_category(category_key)
    if normalized_category is None:
        return False
    return normalized_category in set(get_user_approval_categories(user))


def any_approval_categories(category_keys: Iterable[str]) -> tuple[str, ...]:
    resolved: list[str] = []
    seen: set[str] = set()
    for category_key in category_keys:
        normalized_category = normalize_approval_category(category_key)
        if not normalized_category or normalized_category in seen:
            continue
        seen.add(normalized_category)
        resolved.append(normalized_category)
    return tuple(resolved)


def get_user_scope_profile_from_role_name(role_name: str | None) -> str | None:
    from .role_scope import resolve_scope_profile

    return resolve_scope_profile(role_name)
