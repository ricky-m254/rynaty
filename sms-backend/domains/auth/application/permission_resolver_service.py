"""
PermissionResolverService — Phase 16 Advanced RBAC, Prompt 91.

Final Permission Resolution Logic:
  Final Permission = Role Permissions + User Overrides

Rules:
- If a UserPermissionOverride exists for a user + permission → it takes priority
- Otherwise → use role default
"""
from __future__ import annotations
from typing import List, Set
from domains.auth.domain.interfaces.repositories import (
    UserRepository,
    PermissionRepository,
    UserPermissionOverrideRepository,
)
from domains.auth.domain.entities import Permission


class PermissionResolverService:
    """
    Resolves the effective permission set for a user.
    Phase 16 Advanced RBAC — Prompt 91.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        permission_repo: PermissionRepository,
        override_repo: UserPermissionOverrideRepository,
    ) -> None:
        self._users = user_repo
        self._permissions = permission_repo
        self._overrides = override_repo

    def resolve(self, user_id: int) -> List[str]:
        """
        Return the list of permission name-strings the user is effectively allowed.
        """
        user = self._users.get_by_id(user_id)
        if user is None:
            return []

        role_perm_names: Set[str] = set()
        if user.role:
            role_perm_names = {p.name for p in user.role.permissions}

        overrides = self._overrides.get_by_user(user_id)

        explicitly_allowed: Set[str] = set()
        explicitly_denied: Set[str] = set()

        for override in overrides:
            perm = self._permissions.get_by_id(override.permission_id)
            if perm is None:
                continue
            if override.is_allowed:
                explicitly_allowed.add(perm.name)
            else:
                explicitly_denied.add(perm.name)

        effective = (role_perm_names | explicitly_allowed) - explicitly_denied
        return sorted(effective)

    def has_permission(self, user_id: int, permission_name: str) -> bool:
        return permission_name in self.resolve(user_id)
