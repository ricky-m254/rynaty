"""Staff — pure domain entity."""
from dataclasses import dataclass
from common.exceptions import DomainValidationError


@dataclass
class StaffEntity:
    id: int
    employee_id: str
    first_name: str
    last_name: str
    role: str
    department: str
    is_active: bool = True
    email: str = ''

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def validate(self) -> None:
        if not self.employee_id:
            raise DomainValidationError("employee_id is required")
        if not self.first_name or not self.last_name:
            raise DomainValidationError("first_name and last_name are required")
