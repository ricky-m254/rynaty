"""ShiftRepository — reads SchoolShift and returns plain dicts (not ORM instances)."""
from typing import Optional


class DjangoShiftRepository:

    def find_active_shift_for_person_type(self, person_type: str) -> Optional[dict]:
        from clockin.models import SchoolShift
        from django.db.models import Q
        shift = SchoolShift.objects.filter(
            Q(person_type='ALL') | Q(person_type=person_type),
            is_active=True,
        ).first()
        if not shift:
            return None
        return {
            'id':                 shift.pk,
            'name':               shift.name,
            'expected_arrival':   shift.expected_arrival,
            'grace_period_minutes': shift.grace_period_minutes,
            'expected_departure': shift.expected_departure,
        }
