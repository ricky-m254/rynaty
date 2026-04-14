from rest_framework import permissions


class IsGlobalSuperAdmin(permissions.BasePermission):
    """
    Allows access to platform-level APIs ONLY for active GlobalSuperAdmin users
    whose request originates in the public (platform) schema.

    School admins with is_superuser=True are explicitly denied — that flag grants
    Django admin access within a tenant schema but confers NO platform privileges.
    Platform routes must only respond to public-schema JWT tokens.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Hard schema guard: platform routes must not respond to school-schema requests.
        # A school admin JWT token carries schema_name = 'school_xxx', not 'public'.
        from django.db import connection as _conn
        from django_tenants.utils import get_public_schema_name as _public
        if getattr(_conn, 'schema_name', None) != _public():
            return False

        # In the public schema, require an active GlobalSuperAdmin record.
        # is_superuser alone is intentionally NOT sufficient — school admins may
        # hold that flag for Django admin access within their tenant schema.
        global_admin = getattr(user, "global_admin", None)
        return bool(global_admin and global_admin.is_active)
