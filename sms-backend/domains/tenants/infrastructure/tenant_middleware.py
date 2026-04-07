"""
TenantResolverMiddleware — Phase 12, Prompt 42.

Attaches the resolved Tenant domain object to each request as `request.tenant_obj`.
This DOES NOT replace django-tenants schema switching — it adds a domain-layer
Tenant entity alongside the existing django-tenants infrastructure.

Resolution order:
  1. X-Tenant-ID header (schema name)
  2. HTTP_HOST domain matching
  3. None (public tenant / platform-level request)

Registration: Add to MIDDLEWARE after SessionMiddleware.
"""
from __future__ import annotations
from typing import Callable


class TenantResolverMiddleware:
    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request):
        request.tenant_obj = None
        try:
            from domains.tenants.infrastructure.django_tenant_repository import DjangoTenantRepository
            from domains.tenants.application.tenant_resolver_service import TenantResolverService

            repo = DjangoTenantRepository()
            service = TenantResolverService(repo)
            header = request.META.get('HTTP_X_TENANT_ID')
            host = request.get_host().split(':')[0]
            request.tenant_obj = service.resolve(header_value=header, domain=host)
        except Exception:
            pass

        return self.get_response(request)
