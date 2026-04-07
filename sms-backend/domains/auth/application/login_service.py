"""
LoginService — Phase 11, Prompt 26.

Responsibilities:
- Validate username / password (delegates to repository)
- Check if user is active
- Return user + role + permissions
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List
from domains.auth.domain.entities import UserAccount, Permission
from domains.auth.domain.interfaces.repositories import UserRepository


@dataclass
class LoginResult:
    user: UserAccount
    role_name: str | None
    permissions: List[str]


class LoginService:
    """Use case: Authenticate a user and return their identity + permissions."""

    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    def execute(self, username: str, password: str) -> LoginResult:
        if not username or not password:
            raise ValueError("username and password are required")

        user = self._users.get_by_username(username)
        if user is None:
            raise PermissionError("Invalid credentials.")

        if not user.is_active:
            raise PermissionError("This account is inactive.")

        permissions = self._users.get_user_permissions(user.id)
        role_name = user.role.name if user.role else None
        perm_names = [p.name for p in permissions]

        return LoginResult(user=user, role_name=role_name, permissions=perm_names)
