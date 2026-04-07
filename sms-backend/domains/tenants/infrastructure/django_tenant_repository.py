"""
DjangoTenantRepository — Phase 12, Prompt 40.
Concrete implementation of TenantRepository using Django ORM (django-tenants Client model).
Falls back gracefully if django-tenants is not installed.
"""
from __future__ import annotations
from typing import List, Optional

from domains.tenants.domain.entities import Tenant
from domains.tenants.domain.interfaces.repositories import TenantRepository


def _tenant_from_orm(client) -> Tenant:
    domain = None
    try:
        first_domain = client.domains.filter(is_primary=True).first()
        domain = first_domain.domain if first_domain else None
    except Exception:
        pass
    return Tenant(
        id=client.pk,
        name=client.name,
        schema_name=client.schema_name,
        domain=domain,
        is_active=getattr(client, 'on_trial', True) or True,
    )


class DjangoTenantRepository(TenantRepository):
    def _model(self):
        try:
            from customers.models import Client
            return Client
        except ImportError:
            try:
                from django_tenants.utils import get_tenant_model
                return get_tenant_model()
            except ImportError:
                raise RuntimeError(
                    "django-tenants is not installed or Client model is not available. "
                    "Cannot use DjangoTenantRepository."
                )

    def get_by_domain(self, domain: str) -> Optional[Tenant]:
        try:
            Model = self._model()
            client = Model.objects.filter(domains__domain=domain).first()
            return _tenant_from_orm(client) if client else None
        except Exception:
            return None

    def get_by_schema(self, schema_name: str) -> Optional[Tenant]:
        try:
            Model = self._model()
            client = Model.objects.get(schema_name=schema_name)
            return _tenant_from_orm(client)
        except Exception:
            return None

    def get_by_id(self, id: int) -> Optional[Tenant]:
        try:
            Model = self._model()
            return _tenant_from_orm(Model.objects.get(pk=id))
        except Exception:
            return None

    def list_active_tenants(self) -> List[Tenant]:
        try:
            Model = self._model()
            return [_tenant_from_orm(c) for c in Model.objects.all()]
        except Exception:
            return []

    def save(self, tenant: Tenant) -> Tenant:
        raise NotImplementedError("Tenant creation via domain layer is not yet implemented.")
