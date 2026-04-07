"""
Academics Domain Entities — per-app layer (Phase 5).
Re-exports from the cross-cutting domains package for convenience.
"""
from domains.academics.domain.entities import (
    AcademicYear,
    Term,
    SchoolClass,
    Subject,
    Enrollment,
)

__all__ = ["AcademicYear", "Term", "SchoolClass", "Subject", "Enrollment"]
