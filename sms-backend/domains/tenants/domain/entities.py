"""
Tenants Domain Entities — Phase 12 (Prompts 37-38)
Pure Python dataclasses. No Django. No ORM.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Tenant:
    """
    Tenant entity — represents a school in the multi-tenant system.
    Maps to django-tenants Client model via infrastructure layer.
    """
    id: Optional[int]
    name: str
    schema_name: str
    domain: Optional[str] = None
    subdomain: Optional[str] = None
    is_active: bool = True

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Tenant name is required")
        if not self.schema_name:
            raise ValueError("schema_name is required")
