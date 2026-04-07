"""
TenantResolverService — Phase 12, Prompt 41.

Responsibilities:
- Resolve tenant from HTTP request:
  - X-Tenant-ID header OR
  - domain/subdomain matching
- Validate tenant is active
- Return Tenant object

Does NOT integrate into middleware yet (Prompt 42 does that).
"""
from __future__ import annotations
from typing import Optional
from domains.tenants.domain.entities import Tenant
from domains.tenants.domain.interfaces.repositories import TenantRepository


class TenantResolverService:
    """Application service to resolve a tenant from a request context."""

    def __init__(self, repository: TenantRepository) -> None:
        self._repo = repository

    def resolve_from_header(self, header_value: str | None) -> Optional[Tenant]:
        """Resolve tenant using the X-Tenant-ID header (schema name)."""
        if not header_value:
            return None
        tenant = self._repo.get_by_schema(header_value.strip())
        if tenant and not tenant.is_active:
            raise PermissionError(f"Tenant '{header_value}' is inactive.")
        return tenant

    def resolve_from_domain(self, domain: str) -> Optional[Tenant]:
        """Resolve tenant from the request domain/subdomain."""
        if not domain:
            return None
        tenant = self._repo.get_by_domain(domain)
        if tenant and not tenant.is_active:
            raise PermissionError(f"Tenant for domain '{domain}' is inactive.")
        return tenant

    def resolve(
        self,
        header_value: str | None = None,
        domain: str | None = None,
    ) -> Optional[Tenant]:
        """Try header first, then domain."""
        tenant = self.resolve_from_header(header_value)
        if tenant:
            return tenant
        if domain:
            return self.resolve_from_domain(domain)
        return None
