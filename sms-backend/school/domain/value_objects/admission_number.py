"""AdmissionNumber value object — immutable, validated."""
import re
from common.exceptions import DomainValidationError

PATTERN = re.compile(r'^[A-Z]{2,4}\d{4,8}$')


class AdmissionNumber:
    def __init__(self, value: str):
        v = str(value).strip().upper()
        if not PATTERN.match(v):
            raise DomainValidationError(
                f"Invalid admission number '{value}'. Expected format: STM2025001"
            )
        self._value = v

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return self._value

    def __eq__(self, other) -> bool:
        return isinstance(other, AdmissionNumber) and self._value == other._value
