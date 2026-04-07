"""
AssignRoleService — Phase 11, Prompt 27.

Responsibilities:
- Assign role to a user
- Ensure role exists
- Prevent duplicate assignments
"""
from __future__ import annotations
from domains.auth.domain.interfaces.repositories import UserRepository, RoleRepository


class AssignRoleService:
    """Use case: Assign a Role to a UserAccount."""

    def __init__(
        self,
        user_repository: UserRepository,
        role_repository: RoleRepository,
    ) -> None:
        self._users = user_repository
        self._roles = role_repository

    def execute(self, user_id: int, role_name: str) -> None:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise ValueError(f"User with id={user_id} does not exist.")

        role = self._roles.get_by_name(role_name)
        if role is None:
            raise ValueError(f"Role '{role_name}' does not exist.")

        if user.role and user.role.name == role_name:
            return

        self._users.assign_role_to_user(user_id, role.id)
