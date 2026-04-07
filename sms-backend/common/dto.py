"""
Base Data Transfer Object.
DTOs carry data across domain and layer boundaries without leaking models.
"""
from dataclasses import dataclass, asdict


@dataclass
class BaseDTO:
    """All DTOs inherit from this. Provides dict serialisation."""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PersonDTO(BaseDTO):
    """
    Immutable read-only view of a registered person.
    Used by any domain that needs to reference a person without importing
    school.models or hr.models directly.
    """
    id: int
    display_name: str
    person_type: str          # STUDENT | TEACHER | STAFF
    student_id: Optional[int] = None
    employee_id: Optional[int] = None
    admission_number: str = ''
    employee_number: str = ''

    from typing import Optional   # noqa: F401 — kept for type hint above


@dataclass
class AttendanceDTO(BaseDTO):
    """Cross-domain attendance result written back to school/hr domains."""
    person_id: int
    person_type: str
    event_type: str            # IN | OUT
    timestamp_iso: str
    is_late: bool
    student_id: Optional[int] = None
    employee_id: Optional[int] = None

    from typing import Optional   # noqa
