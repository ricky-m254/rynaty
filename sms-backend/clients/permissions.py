from rest_framework import permissions


class IsGlobalSuperAdmin(permissions.BasePermission):
    """
    Allows access to platform-level APIs for active GlobalSuperAdmin users.
    Django superusers are also allowed for operational recovery.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        global_admin = getattr(user, "global_admin", None)
        return bool(global_admin and global_admin.is_active)
