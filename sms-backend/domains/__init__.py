"""
SmartCampus DBMA — Cross-cutting Domains Package
=================================================
Phase 1-16 implementation per the DBMA Implementation Roadmap.

Each domain follows Clean Architecture layers:
  domain        — pure business entities, value objects, repository interfaces
  application   — use cases and services (orchestration only)
  infrastructure — concrete repository implementations (Django ORM adapters)
  presentation  — API adapters (not used here; apps own their API layer)

Rule #1: Do NOT break existing functionality.
Rule #2: Prefer adding new code over modifying old code.
"""
