"""
DjangoRoleRepository — Phase 11, Prompt 30.
Concrete implementation of RoleRepository using Django ORM.
"""
from __future__ import annotations
from typing import List, Optional

from school.models import Role as RoleModel, RolePermissionGrant
from domains.auth.domain.entities import Role, Permission
from domains.auth.domain.interfaces.repositories import RoleRepository


def _perm_from_orm(perm_orm) -> Permission:
    return Permission(
        id=perm_orm.pk,
        name=perm_orm.name,
        module=perm_orm.module,
        action=perm_orm.action,
        description=perm_orm.description,
    )


def _role_from_orm(role_orm) -> Role:
    grants = RolePermissionGrant.objects.filter(role=role_orm).select_related('permission')
    permissions = [_perm_from_orm(g.permission) for g in grants]
    return Role(
        id=role_orm.pk,
        name=role_orm.name,
        description=role_orm.description or "",
        permissions=permissions,
    )


class DjangoRoleRepository(RoleRepository):
    def get_by_id(self, id: int) -> Optional[Role]:
        try:
            return _role_from_orm(RoleModel.objects.get(pk=id))
        except RoleModel.DoesNotExist:
            return None

    def get_by_name(self, name: str) -> Optional[Role]:
        try:
            return _role_from_orm(RoleModel.objects.get(name=name))
        except RoleModel.DoesNotExist:
            return None

    def save(self, role: Role) -> Role:
        if role.id:
            role_orm = RoleModel.objects.get(pk=role.id)
            role_orm.description = role.description or ""
            role_orm.save(update_fields=['description'])
        else:
            role_orm = RoleModel.objects.create(name=role.name, description=role.description or "")
        return _role_from_orm(role_orm)

    def list(self) -> List[Role]:
        return [_role_from_orm(r) for r in RoleModel.objects.all()]
