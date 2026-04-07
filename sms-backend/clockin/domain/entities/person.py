"""
Person — domain representation of a registered biometric person.
Mirrors PersonRegistry but with zero ORM dependency.
"""
from dataclasses import dataclass
from typing import Optional

VALID_PERSON_TYPES = ('STUDENT', 'TEACHER', 'STAFF')


@dataclass
class PersonEntity:
    """
    Read-only domain view of a PersonRegistry record.
    Populated by PersonRepository.find_*() methods.
    """
    id: int
    display_name: str
    person_type: str           # STUDENT | TEACHER | STAFF
    fingerprint_id: str
    card_no: str = ''
    dahua_user_id: str = ''
    student_id: Optional[int] = None
    employee_id: Optional[int] = None
    is_active: bool = True

    def validate(self) -> None:
        from common.exceptions import DomainValidationError
        if self.person_type not in VALID_PERSON_TYPES:
            raise DomainValidationError(f"person_type must be one of {VALID_PERSON_TYPES}")
        if not self.display_name:
            raise DomainValidationError("display_name is required")

    def is_student(self) -> bool:
        return self.person_type == 'STUDENT'

    def is_staff(self) -> bool:
        return self.person_type in ('TEACHER', 'STAFF')
