"""
DjangoUserPermissionOverrideRepository — Phase 16, Prompt 91.
Concrete implementation of UserPermissionOverrideRepository using Django ORM.
"""
from __future__ import annotations
from typing import List, Optional

from school.models import UserPermissionOverride as OverrideModel
from domains.auth.domain.entities import UserPermissionOverride
from domains.auth.domain.interfaces.repositories import UserPermissionOverrideRepository


def _override_from_orm(o) -> UserPermissionOverride:
    return UserPermissionOverride(
        id=o.pk,
        user_id=o.user_id,
        permission_id=o.permission_id,
        is_allowed=o.is_allowed,
        reason=o.reason,
    )


class DjangoUserPermissionOverrideRepository(UserPermissionOverrideRepository):
    def get_by_user(self, user_id: int) -> List[UserPermissionOverride]:
        return [
            _override_from_orm(o)
            for o in OverrideModel.objects.filter(user_id=user_id).select_related('permission')
        ]

    def get_by_user_and_permission(
        self, user_id: int, permission_id: int
    ) -> Optional[UserPermissionOverride]:
        try:
            return _override_from_orm(
                OverrideModel.objects.get(user_id=user_id, permission_id=permission_id)
            )
        except OverrideModel.DoesNotExist:
            return None

    def save(self, override: UserPermissionOverride) -> UserPermissionOverride:
        obj, _ = OverrideModel.objects.update_or_create(
            user_id=override.user_id,
            permission_id=override.permission_id,
            defaults={
                'is_allowed': override.is_allowed,
                'reason': override.reason or '',
            }
        )
        return _override_from_orm(obj)

    def delete(self, user_id: int, permission_id: int) -> None:
        OverrideModel.objects.filter(user_id=user_id, permission_id=permission_id).delete()
