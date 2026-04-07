"""
ClockEventRepository — Infrastructure implementation.
Saves ClockEventEntity domain objects to the clockin.ClockEvent ORM table.
"""
from datetime import datetime, timedelta
from typing import Optional

from clockin.domain.entities.clock_event import ClockEventEntity


class AbstractClockEventRepository:
    def save(self, entity: ClockEventEntity): ...
    def find_last_for_person_on_date(self, person_id: int, event_date): ...
    def duplicate_exists(self, person_id: int, event_type: str, timestamp: datetime) -> bool: ...


class DjangoClockEventRepository(AbstractClockEventRepository):

    def save(self, entity: ClockEventEntity):
        """Persist and return the created ORM ClockEvent."""
        from clockin.models import ClockEvent, PersonRegistry, BiometricDevice
        person_obj = PersonRegistry.objects.get(pk=entity.person_id)
        device_obj = None
        if entity.device_id:
            device_obj = BiometricDevice.objects.filter(pk=entity.device_id).first()
        return ClockEvent.objects.create(
            person     = person_obj,
            device     = device_obj,
            event_type = entity.event_type,
            timestamp  = entity.timestamp,
            date       = entity.event_date,
            is_late    = entity.is_late,
            notes      = entity.notes,
        )

    def find_last_for_person_on_date(self, person_id: int, event_date):
        from clockin.models import ClockEvent
        return ClockEvent.objects.filter(person_id=person_id, date=event_date).order_by('-timestamp').first()

    def duplicate_exists(self, person_id: int, event_type: str, timestamp: datetime) -> bool:
        from clockin.models import ClockEvent
        window_start = timestamp - timedelta(seconds=60)
        window_end   = timestamp + timedelta(seconds=60)
        return ClockEvent.objects.filter(
            person_id=person_id,
            event_type=event_type,
            timestamp__range=(window_start, window_end),
        ).exists()
