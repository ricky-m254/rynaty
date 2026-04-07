"""
EventType value object.
Immutable; equality by value, not identity.
"""
from enum import Enum


class EventType(str, Enum):
    IN  = 'IN'
    OUT = 'OUT'

    @classmethod
    def from_direction(cls, direction: str) -> 'EventType':
        """
        Convert a Dahua direction string/int to EventType.
        direction: 'in' | 'out' | '0' | '1' | 'auto'
        """
        d = str(direction).lower().strip()
        if d in ('in', '0', 'entry'):
            return cls.IN
        if d in ('out', '1', 'exit'):
            return cls.OUT
        return cls.IN   # default for 'auto' — resolved by domain rules

    @classmethod
    def from_last_event(cls, last_event_type: str | None) -> 'EventType':
        """Alternating logic: if last was IN → now OUT, else IN."""
        if last_event_type == cls.IN:
            return cls.OUT
        return cls.IN


class PersonType(str, Enum):
    STUDENT = 'STUDENT'
    TEACHER = 'TEACHER'
    STAFF   = 'STAFF'
