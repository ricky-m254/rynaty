"""
Transport Domain Entities — per-app layer (Phase 8).
Re-exports from cross-cutting domains package.
"""
from domains.operations.transport.domain.entities import Vehicle, Route

__all__ = ["Vehicle", "Route"]
