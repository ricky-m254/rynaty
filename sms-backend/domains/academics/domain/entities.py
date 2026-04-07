"""
Academics Domain Entities — Phase 5 (Prompts 10-11)
Pure Python dataclasses. No Django. No ORM.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class AcademicYear:
    id: Optional[int]
    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Academic year name is required")


@dataclass
class Term:
    id: Optional[int]
    name: str
    academic_year_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False


@dataclass
class SchoolClass:
    """Represents a classroom / grade level."""
    id: Optional[int]
    name: str
    grade_level: Optional[str] = None
    capacity: int = 40
    is_active: bool = True

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Class name is required")
        if self.capacity < 1:
            raise ValueError("Capacity must be at least 1")


@dataclass
class Subject:
    id: Optional[int]
    name: str
    code: Optional[str] = None
    is_compulsory: bool = True
    is_active: bool = True

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Subject name is required")


@dataclass
class Enrollment:
    """Student enrolled in a class for a term."""
    id: Optional[int]
    student_id: int
    class_id: int
    term_id: Optional[int] = None
    enrollment_date: Optional[str] = None
    is_active: bool = True

    def validate(self) -> None:
        if not self.student_id:
            raise ValueError("student_id is required for Enrollment")
        if not self.class_id:
            raise ValueError("class_id is required for Enrollment")
