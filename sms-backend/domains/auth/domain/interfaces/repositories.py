"""
Auth Domain — Repository Interfaces (Phase 11, Prompts 25 + Phase 16)
Abstract contracts only. Do NOT implement database logic here.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from domains.auth.domain.entities import (
    UserAccount, Role, Permission, UserPermissionOverride
)


class UserRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[UserAccount]: ...

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[UserAccount]: ...

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[UserAccount]: ...

    @abstractmethod
    def get_user_permissions(self, user_id: int) -> List[Permission]: ...

    @abstractmethod
    def assign_role_to_user(self, user_id: int, role_id: int) -> None: ...

    @abstractmethod
    def save(self, user: UserAccount) -> UserAccount: ...


class RoleRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Role]: ...

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Role]: ...

    @abstractmethod
    def save(self, role: Role) -> Role: ...

    @abstractmethod
    def list(self) -> List[Role]: ...


class PermissionRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Permission]: ...

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Permission]: ...

    @abstractmethod
    def save(self, permission: Permission) -> Permission: ...

    @abstractmethod
    def list(self, module: str | None = None) -> List[Permission]: ...


class UserPermissionOverrideRepository(ABC):
    """Phase 16 Advanced RBAC — override storage."""

    @abstractmethod
    def get_by_user(self, user_id: int) -> List[UserPermissionOverride]: ...

    @abstractmethod
    def get_by_user_and_permission(
        self, user_id: int, permission_id: int
    ) -> Optional[UserPermissionOverride]: ...

    @abstractmethod
    def save(self, override: UserPermissionOverride) -> UserPermissionOverride: ...

    @abstractmethod
    def delete(self, user_id: int, permission_id: int) -> None: ...
