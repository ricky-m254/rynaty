"""
HasPermission Middleware — Phase 11, Prompt 31.

Attaches a `has_permission()` helper to each request based on the
PermissionResolverService. Views can call:
    request.has_permission("finance.invoice.read")
to guard actions.

Registration: Add 'domains.auth.infrastructure.has_permission_middleware.HasPermissionMiddleware'
to MIDDLEWARE in settings.py AFTER 'django.contrib.auth.middleware.AuthenticationMiddleware'.
"""
from __future__ import annotations
from typing import Callable


class HasPermissionMiddleware:
    """Attaches `request.has_permission` and `request.effective_permissions` to every request."""

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)

        if user and user.is_authenticated:
            try:
                from domains.auth.infrastructure.django_user_repository import DjangoUserRepository
                from domains.auth.infrastructure.django_permission_repository import DjangoPermissionRepository
                from domains.auth.infrastructure.django_override_repository import DjangoUserPermissionOverrideRepository
                from domains.auth.application.permission_resolver_service import PermissionResolverService

                resolver = PermissionResolverService(
                    user_repo=DjangoUserRepository(),
                    permission_repo=DjangoPermissionRepository(),
                    override_repo=DjangoUserPermissionOverrideRepository(),
                )
                effective = set(resolver.resolve(user.pk))
                request.effective_permissions = effective
                request.has_permission = lambda perm: perm in effective
            except Exception:
                request.effective_permissions = set()
                request.has_permission = lambda perm: False
        else:
            request.effective_permissions = set()
            request.has_permission = lambda perm: False

        return self.get_response(request)
