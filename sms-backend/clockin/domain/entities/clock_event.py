"""
ClockEvent — pure domain entity.
No Django ORM. No framework imports. Fully unit-testable.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from common.exceptions import DomainValidationError


@dataclass
class ClockEventEntity:
    """
    Represents a single attendance scan event in the domain layer.
    Created by the ProcessScan use case; persisted by ClockEventRepository.
    """
    person_id: int
    event_type: str          # 'IN' | 'OUT'
    timestamp: datetime
    event_date: object       # date
    is_late: bool = False
    device_id: Optional[int] = None
    notes: str = ''

    VALID_TYPES = ('IN', 'OUT')

    def validate(self) -> None:
        if not self.person_id:
            raise DomainValidationError("ClockEvent requires a valid person_id")
        if self.event_type not in self.VALID_TYPES:
            raise DomainValidationError(f"event_type must be one of {self.VALID_TYPES}")
        if not isinstance(self.timestamp, datetime):
            raise DomainValidationError("timestamp must be a datetime object")

    def is_clock_in(self) -> bool:
        return self.event_type == 'IN'

    def is_clock_out(self) -> bool:
        return self.event_type == 'OUT'
