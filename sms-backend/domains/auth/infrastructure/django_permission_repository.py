"""
DjangoPermissionRepository — Phase 11 + Phase 16, Prompt 30.
Concrete implementation of PermissionRepository using Django ORM.
"""
from __future__ import annotations
from typing import List, Optional

from school.models import Permission as PermModel
from domains.auth.domain.entities import Permission
from domains.auth.domain.interfaces.repositories import PermissionRepository


def _perm_from_orm(p) -> Permission:
    return Permission(id=p.pk, name=p.name, module=p.module, action=p.action, description=p.description)


class DjangoPermissionRepository(PermissionRepository):
    def get_by_id(self, id: int) -> Optional[Permission]:
        try:
            return _perm_from_orm(PermModel.objects.get(pk=id))
        except PermModel.DoesNotExist:
            return None

    def get_by_name(self, name: str) -> Optional[Permission]:
        try:
            return _perm_from_orm(PermModel.objects.get(name=name))
        except PermModel.DoesNotExist:
            return None

    def save(self, permission: Permission) -> Permission:
        obj, _ = PermModel.objects.update_or_create(
            name=permission.name,
            defaults={
                'module': permission.module,
                'action': permission.action,
                'description': permission.description or '',
            }
        )
        return _perm_from_orm(obj)

    def list(self, module: str | None = None) -> List[Permission]:
        qs = PermModel.objects.all()
        if module:
            qs = qs.filter(module=module)
        return [_perm_from_orm(p) for p in qs]
