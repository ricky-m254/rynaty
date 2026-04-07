"""
Academics Domain — Repository Interfaces re-export.
"""
from domains.academics.domain.interfaces.repositories import (
    ClassRepository,
    SubjectRepository,
    EnrollmentRepository,
)

__all__ = ["ClassRepository", "SubjectRepository", "EnrollmentRepository"]
