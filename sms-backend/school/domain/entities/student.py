"""Student — pure domain entity. No Django. No ORM."""
from dataclasses import dataclass, field
from typing import Optional
from common.exceptions import DomainValidationError


@dataclass
class StudentEntity:
    id: int
    admission_number: str
    first_name: str
    last_name: str
    date_of_birth: object        # date
    gender: str                  # M | F
    grade_level: str
    ulid: str = ''
    is_active: bool = True
    email: str = ''
    phone: str = ''

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def validate(self) -> None:
        if not self.admission_number:
            raise DomainValidationError("admission_number is required")
        if not self.first_name or not self.last_name:
            raise DomainValidationError("first_name and last_name are required")
        if self.gender not in ('M', 'F'):
            raise DomainValidationError("gender must be M or F")
