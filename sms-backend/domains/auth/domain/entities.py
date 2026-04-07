"""
Auth Domain Entities — Phase 11 (Prompts 22-24) + Phase 16 Advanced RBAC (Prompts 87-91)
Pure Python dataclasses. No Django. No ORM.

Permission naming convention (Prompt 88):
  Format: <domain>.<resource>.<action>
  Examples:
    finance.invoice.read
    finance.invoice.create
    academics.attendance.mark
    students.student.update
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Permission:
    """
    Granular permission — Phase 16 (Prompt 88).
    Format: <domain>.<resource>.<action>
    """
    id: Optional[int]
    name: str
    module: str
    action: str
    description: Optional[str] = None

    @property
    def key(self) -> str:
        return self.name

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Permission name is required")
        if "." not in self.name:
            raise ValueError("Permission name must follow <domain>.<resource>.<action> format")


@dataclass
class Role:
    """
    Role entity — Phase 11 (Prompt 23) + Phase 16 (Prompt 89).
    A Role has many Permissions (templates / defaults).
    """
    id: Optional[int]
    name: str
    description: Optional[str] = None
    is_active: bool = True
    permissions: List[Permission] = field(default_factory=list)

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Role name is required")

    def has_permission(self, permission_name: str) -> bool:
        return any(p.name == permission_name for p in self.permissions)

    def add_permission(self, permission: Permission) -> None:
        if not self.has_permission(permission.name):
            self.permissions.append(permission)

    def remove_permission(self, permission_name: str) -> None:
        self.permissions = [p for p in self.permissions if p.name != permission_name]


@dataclass
class UserAccount:
    """
    User account entity — Phase 11 (Prompt 23).
    Maps to existing Django User via infrastructure layer.
    """
    id: Optional[int]
    username: str
    email: Optional[str] = None
    password_hash: Optional[str] = None
    is_active: bool = True
    role: Optional[Role] = None

    def validate(self) -> None:
        if not self.username:
            raise ValueError("username is required")

    def get_role_permissions(self) -> List[Permission]:
        if self.role is None:
            return []
        return list(self.role.permissions)


@dataclass
class RolePermission:
    """Mapping table between Role and Permission — Phase 11 (Prompt 24)."""
    role_id: int
    permission_id: int


@dataclass
class UserRoleAssignment:
    """Links a UserAccount to a Role — Phase 11 (Prompt 24)."""
    user_id: int
    role_id: int
    assigned_at: Optional[str] = None
    assigned_by: Optional[int] = None


@dataclass
class UserPermissionOverride:
    """
    Per-user permission override — Phase 16 Advanced RBAC (Prompt 90).
    Final Permission = Role Permissions + Overrides (overrides take priority).
    """
    id: Optional[int]
    user_id: int
    permission_id: int
    is_allowed: bool
    reason: Optional[str] = None

    def validate(self) -> None:
        if not self.user_id:
            raise ValueError("user_id is required")
        if not self.permission_id:
            raise ValueError("permission_id is required")
