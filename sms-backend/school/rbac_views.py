"""
Phase 11 + Phase 16 Advanced RBAC API views.

Session 5 keeps this surface on the existing resolver path while allowing
admin-family compatibility through the shared scope bridge.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import CanManageRbac, request_can_manage_rbac
from .role_scope import get_user_scope_profile, is_admin_scope

User = get_user_model()


def _all_active_permission_names() -> list[str]:
    from school.models import Permission as PermModel

    permissions = list(PermModel.objects.order_by("name").values_list("name", flat=True))
    return permissions or ["*"]


class RbacPermissionListView(APIView):
    """List all permissions, optionally filtered by module."""

    permission_classes = [CanManageRbac]

    def get(self, request):
        from school.models import Permission as PermModel

        module = request.query_params.get("module")
        queryset = PermModel.objects.all().order_by("module", "name")
        if module:
            queryset = queryset.filter(module=module)
        data = [
            {
                "id": permission.id,
                "name": permission.name,
                "module": permission.module,
                "action": permission.action,
                "description": permission.description,
            }
            for permission in queryset
        ]
        return Response(data)


DEFAULT_PERMISSIONS = [
    ("students.student.read", "students", "read", "View student list and profiles"),
    ("students.student.create", "students", "create", "Enroll new students"),
    ("students.student.update", "students", "update", "Edit student information"),
    ("students.student.delete", "students", "delete", "Deactivate or delete students"),
    ("finance.invoice.read", "finance", "read", "View invoices and statements"),
    ("finance.invoice.create", "finance", "create", "Generate invoices"),
    ("finance.invoice.update", "finance", "update", "Edit invoice details"),
    ("finance.payment.record", "finance", "record", "Record payments"),
    ("finance.report.view", "finance", "view", "View financial reports"),
    ("academics.enrollment.read", "academics", "read", "View class enrollments"),
    ("academics.enrollment.manage", "academics", "manage", "Manage enrollments"),
    ("academics.attendance.mark", "academics", "mark", "Mark attendance"),
    ("academics.attendance.view", "academics", "view", "View attendance records"),
    ("academics.timetable.read", "academics", "read", "View timetables"),
    ("academics.timetable.manage", "academics", "manage", "Create/edit timetables"),
    ("hr.staff.read", "hr", "read", "View staff directory"),
    ("hr.staff.create", "hr", "create", "Add new staff members"),
    ("hr.staff.update", "hr", "update", "Edit staff information"),
    ("hr.staff.delete", "hr", "delete", "Deactivate staff"),
    ("hr.leave.approve", "hr", "approve", "Approve leave requests"),
    ("transport.vehicle.read", "transport", "read", "View vehicles and routes"),
    ("transport.vehicle.manage", "transport", "manage", "Add/edit vehicles and routes"),
    ("library.book.read", "library", "read", "Browse book catalog"),
    ("library.book.manage", "library", "manage", "Manage book catalog"),
    ("library.circulation.manage", "library", "manage", "Issue and return books"),
    ("hostel.allocation.read", "hostel", "read", "View bed allocations"),
    ("hostel.allocation.manage", "hostel", "manage", "Assign/remove bed allocations"),
    ("admissions.application.read", "admissions", "read", "View admission applications"),
    ("admissions.application.manage", "admissions", "manage", "Process admissions"),
    ("communication.message.send", "communication", "send", "Send messages/announcements"),
    ("communication.message.read", "communication", "read", "Read messages"),
    ("analytics.report.view", "analytics", "view", "View analytics reports"),
    ("settings.system.manage", "settings", "manage", "Manage system settings"),
    ("settings.rbac.manage", "settings", "manage", "Manage roles and permissions"),
]


class RbacPermissionSeedView(APIView):
    """Seed the default RBAC permission catalog."""

    permission_classes = [CanManageRbac]

    def post(self, request):
        from school.models import Permission as PermModel

        created = 0
        skipped = 0
        for name, module, action, description in DEFAULT_PERMISSIONS:
            _, is_new = PermModel.objects.get_or_create(
                name=name,
                defaults={"module": module, "action": action, "description": description},
            )
            if is_new:
                created += 1
            else:
                skipped += 1
        return Response(
            {
                "status": "ok",
                "created": created,
                "skipped": skipped,
                "total": created + skipped,
            },
            status=status.HTTP_201_CREATED,
        )


class RbacRoleListView(APIView):
    permission_classes = [CanManageRbac]

    def get(self, request):
        from school.models import Role as RoleModel

        roles = RoleModel.objects.prefetch_related("permission_grants__permission").all()
        data = []
        for role in roles:
            permissions = [
                {"id": grant.permission.id, "name": grant.permission.name, "module": grant.permission.module}
                for grant in role.permission_grants.all()
            ]
            data.append(
                {
                    "id": role.id,
                    "name": role.name,
                    "description": role.description,
                    "permissions": permissions,
                }
            )
        return Response(data)


class RbacRoleGrantPermissionView(APIView):
    """Grant a permission to a role."""

    permission_classes = [CanManageRbac]

    def post(self, request, role_id):
        from school.models import Permission as PermModel
        from school.models import Role as RoleModel
        from school.models import RolePermissionGrant

        permission_id = request.data.get("permission_id")
        if not permission_id:
            return Response({"error": "permission_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            role = RoleModel.objects.get(pk=role_id)
            permission = PermModel.objects.get(pk=permission_id)
        except (RoleModel.DoesNotExist, PermModel.DoesNotExist) as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        _, created = RolePermissionGrant.objects.get_or_create(role=role, permission=permission)
        return Response(
            {
                "status": "granted" if created else "already_granted",
                "role": role.name,
                "permission": permission.name,
            }
        )


class RbacRoleRevokePermissionView(APIView):
    """Revoke a permission from a role."""

    permission_classes = [CanManageRbac]

    def post(self, request, role_id):
        from school.models import RolePermissionGrant

        permission_id = request.data.get("permission_id")
        if not permission_id:
            return Response({"error": "permission_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = RolePermissionGrant.objects.filter(
            role_id=role_id, permission_id=permission_id
        ).delete()
        if deleted:
            return Response({"status": "revoked"})
        return Response({"status": "not_found"}, status=status.HTTP_404_NOT_FOUND)


class RbacUserEffectivePermissionsView(APIView):
    """Return the final resolved permission set for a user."""

    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if request.user.pk != user_id and not request_can_manage_rbac(request):
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        target_user = User.objects.filter(pk=user_id).first()
        if not target_user:
            return Response({"error": f"User {user_id} not found"}, status=status.HTTP_404_NOT_FOUND)

        if is_admin_scope(get_user_scope_profile(target_user)):
            permissions = _all_active_permission_names()
            return Response(
                {
                    "user_id": user_id,
                    "permissions": permissions,
                    "count": len(permissions),
                    "is_admin": True,
                }
            )

        try:
            from domains.auth.application.permission_resolver_service import PermissionResolverService
            from domains.auth.infrastructure.django_override_repository import (
                DjangoUserPermissionOverrideRepository,
            )
            from domains.auth.infrastructure.django_permission_repository import DjangoPermissionRepository
            from domains.auth.infrastructure.django_user_repository import DjangoUserRepository

            resolver = PermissionResolverService(
                user_repo=DjangoUserRepository(),
                permission_repo=DjangoPermissionRepository(),
                override_repo=DjangoUserPermissionOverrideRepository(),
            )
            permissions = resolver.resolve(user_id)
            return Response({"user_id": user_id, "permissions": permissions, "count": len(permissions)})
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RbacUserOverrideListView(APIView):
    permission_classes = [CanManageRbac]

    def get(self, request, user_id):
        from school.models import UserPermissionOverride as OverrideModel

        overrides = OverrideModel.objects.filter(user_id=user_id).select_related("permission")
        data = [
            {
                "id": override.id,
                "permission_id": override.permission_id,
                "permission": override.permission.name,
                "is_allowed": override.is_allowed,
                "reason": override.reason,
                "created_at": override.created_at,
            }
            for override in overrides
        ]
        return Response(data)

    def post(self, request, user_id):
        from school.models import Permission as PermModel
        from school.models import UserPermissionOverride as OverrideModel

        permission_id = request.data.get("permission_id")
        is_allowed = request.data.get("is_allowed", True)
        reason = request.data.get("reason", "")

        if not permission_id:
            return Response({"error": "permission_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            permission = PermModel.objects.get(pk=permission_id)
        except PermModel.DoesNotExist:
            return Response({"error": f"Permission {permission_id} not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            target_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"error": f"User {user_id} not found"}, status=status.HTTP_404_NOT_FOUND)

        override, created = OverrideModel.objects.update_or_create(
            user=target_user,
            permission=permission,
            defaults={
                "is_allowed": bool(is_allowed),
                "reason": reason,
                "created_by": request.user,
            },
        )
        return Response(
            {
                "id": override.id,
                "permission": permission.name,
                "is_allowed": override.is_allowed,
                "reason": override.reason,
                "action": "created" if created else "updated",
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class RbacUserOverrideDeleteView(APIView):
    permission_classes = [CanManageRbac]

    def delete(self, request, user_id, permission_id):
        from school.models import UserPermissionOverride as OverrideModel

        deleted, _ = OverrideModel.objects.filter(user_id=user_id, permission_id=permission_id).delete()
        if deleted:
            return Response({"status": "deleted"})
        return Response({"status": "not_found"}, status=status.HTTP_404_NOT_FOUND)
