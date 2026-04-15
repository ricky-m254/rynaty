"""
DjangoUserRepository — Phase 11, Prompt 30.
Concrete implementation of UserRepository using Django ORM.
Bridges domain entities <-> Django models.
"""
from __future__ import annotations
from typing import List, Optional

from django.contrib.auth.models import User as DjangoUser

from domains.auth.domain.entities import UserAccount, Role, Permission
from domains.auth.domain.interfaces.repositories import UserRepository

import logging

logger = logging.getLogger(__name__)



def _permission_from_grant(grant) -> Permission:
    perm = grant.permission
    return Permission(
        id=perm.pk,
        name=perm.name,
        module=perm.module,
        action=perm.action,
        description=perm.description,
    )


def _role_from_orm(role_orm) -> Role:
    from school.models import RolePermissionGrant
    grants = RolePermissionGrant.objects.filter(role=role_orm).select_related('permission')
    permissions = [_permission_from_grant(g) for g in grants]
    return Role(
        id=role_orm.pk,
        name=role_orm.name,
        description=role_orm.description or "",
        permissions=permissions,
    )


def _user_from_orm(django_user: DjangoUser) -> UserAccount:
    role_entity = None
    try:
        profile = django_user.userprofile
        if profile.role:
            role_entity = _role_from_orm(profile.role)
    except Exception:
        logger.warning("Caught and logged", exc_info=True)

    return UserAccount(
        id=django_user.pk,
        username=django_user.username,
        email=django_user.email or None,
        password_hash=django_user.password,
        is_active=django_user.is_active,
        role=role_entity,
    )


class DjangoUserRepository(UserRepository):
    """Django ORM implementation of UserRepository."""

    def get_by_id(self, id: int) -> Optional[UserAccount]:
        try:
            return _user_from_orm(DjangoUser.objects.select_related('userprofile__role').get(pk=id))
        except DjangoUser.DoesNotExist:
            return None

    def get_by_username(self, username: str) -> Optional[UserAccount]:
        try:
            return _user_from_orm(
                DjangoUser.objects.select_related('userprofile__role').get(username=username)
            )
        except DjangoUser.DoesNotExist:
            return None

    def get_by_email(self, email: str) -> Optional[UserAccount]:
        try:
            return _user_from_orm(
                DjangoUser.objects.select_related('userprofile__role').get(email=email)
            )
        except DjangoUser.DoesNotExist:
            return None

    def get_user_permissions(self, user_id: int) -> List[Permission]:
        """
        Returns the effective resolved permissions for the user.
        Phase 16: Role defaults + UserPermissionOverrides.
        """
        from school.models import RolePermissionGrant, UserPermissionOverride, Permission as PermModel

        try:
            user = DjangoUser.objects.select_related('userprofile__role').get(pk=user_id)
        except DjangoUser.DoesNotExist:
            return []

        role_perm_names: set[str] = set()
        try:
            if user.userprofile.role:
                grants = RolePermissionGrant.objects.filter(
                    role=user.userprofile.role
                ).select_related('permission')
                role_perm_names = {g.permission.name for g in grants}
        except Exception:
            logger.warning("Caught and logged", exc_info=True)

        overrides = UserPermissionOverride.objects.filter(user_id=user_id).select_related('permission')
        explicitly_allowed = {o.permission.name for o in overrides if o.is_allowed}
        explicitly_denied = {o.permission.name for o in overrides if not o.is_allowed}

        effective_names = (role_perm_names | explicitly_allowed) - explicitly_denied

        perms_qs = PermModel.objects.filter(name__in=effective_names)
        return [
            Permission(id=p.pk, name=p.name, module=p.module, action=p.action, description=p.description)
            for p in perms_qs
        ]

    def assign_role_to_user(self, user_id: int, role_id: int) -> None:
        from school.models import Role as RoleModel, UserProfile
        role_orm = RoleModel.objects.get(pk=role_id)
        profile, _ = UserProfile.objects.get_or_create(
            user_id=user_id,
            defaults={'role': role_orm}
        )
        if profile.role_id != role_id:
            profile.role = role_orm
            profile.save(update_fields=['role'])

    def save(self, user: UserAccount) -> UserAccount:
        if user.id:
            django_user = DjangoUser.objects.get(pk=user.id)
            django_user.username = user.username
            django_user.email = user.email or ""
            django_user.is_active = user.is_active
            django_user.save(update_fields=['username', 'email', 'is_active'])
        else:
            django_user = DjangoUser.objects.create_user(username=user.username, email=user.email or "")
        return _user_from_orm(django_user)
