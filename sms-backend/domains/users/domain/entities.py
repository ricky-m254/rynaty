"""
Users Domain Entities — Phase 2 (Prompts 3-4)
Pure Python dataclasses. No Django. No ORM.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Student:
    """Core student entity — domain model only."""
    id: Optional[int]
    admission_number: str
    first_name: str
    last_name: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    grade_level: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def validate(self) -> None:
        errors = []
        if not self.admission_number:
            errors.append("admission_number is required")
        if not self.first_name:
            errors.append("first_name is required")
        if not self.last_name:
            errors.append("last_name is required")
        if self.gender and self.gender not in ("M", "F", "Other"):
            errors.append("gender must be M, F, or Other")
        if errors:
            raise ValueError("; ".join(errors))


@dataclass
class Parent:
    """Parent / Guardian entity."""
    id: Optional[int]
    name: str
    relationship: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: bool = True

    def validate(self) -> None:
        if not self.name:
            raise ValueError("name is required for Parent")


@dataclass
class Guardian:
    """Guardian entity (alias-compatible with Parent, used across multiple domains)."""
    id: Optional[int]
    name: str
    student_id: Optional[int] = None
    relationship: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = False
    is_active: bool = True

    def validate(self) -> None:
        if not self.name:
            raise ValueError("name is required for Guardian")
