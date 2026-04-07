"""
Tenants Domain — Repository Interface (Phase 12, Prompt 39)
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from domains.tenants.domain.entities import Tenant


class TenantRepository(ABC):
    @abstractmethod
    def get_by_domain(self, domain: str) -> Optional[Tenant]: ...

    @abstractmethod
    def get_by_schema(self, schema_name: str) -> Optional[Tenant]: ...

    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Tenant]: ...

    @abstractmethod
    def list_active_tenants(self) -> List[Tenant]: ...

    @abstractmethod
    def save(self, tenant: Tenant) -> Tenant: ...
