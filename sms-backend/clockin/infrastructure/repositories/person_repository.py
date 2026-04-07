"""
PersonRepository — Infrastructure implementation.
Queries PersonRegistry ORM model; returns domain entities, NOT ORM instances.
This eliminates cross-domain model imports elsewhere.
"""
from typing import Optional
from clockin.domain.entities.person import PersonEntity


class AbstractPersonRepository:
    def find_by_id(self, person_id: int) -> Optional[PersonEntity]: ...
    def find_by_card_no(self, card_no: str) -> Optional[PersonEntity]: ...
    def find_by_user_id(self, user_id: str) -> Optional[PersonEntity]: ...
    def find_by_name(self, name: str) -> Optional[PersonEntity]: ...


class DjangoPersonRepository(AbstractPersonRepository):
    """
    Reads from clockin.PersonRegistry (ORM).
    Always returns PersonEntity (domain DTO), never a raw Django model.
    """

    def find_by_id(self, person_id: int) -> Optional[PersonEntity]:
        from clockin.models import PersonRegistry
        p = PersonRegistry.objects.filter(pk=person_id, is_active=True).first()
        return self._to_entity(p)

    def find_by_card_no(self, card_no: str) -> Optional[PersonEntity]:
        if not card_no:
            return None
        from clockin.models import PersonRegistry
        p = PersonRegistry.objects.filter(card_no=card_no, is_active=True).first()
        return self._to_entity(p)

    def find_by_user_id(self, user_id: str) -> Optional[PersonEntity]:
        if not user_id:
            return None
        from clockin.models import PersonRegistry
        p = (PersonRegistry.objects.filter(dahua_user_id=user_id, is_active=True).first() or
             PersonRegistry.objects.filter(fingerprint_id=user_id, is_active=True).first())
        return self._to_entity(p)

    def find_by_fingerprint(self, fingerprint_id: str) -> Optional[PersonEntity]:
        from clockin.models import PersonRegistry
        p = PersonRegistry.objects.filter(fingerprint_id=fingerprint_id, is_active=True).first()
        return self._to_entity(p)

    def find_by_name(self, name: str) -> Optional[PersonEntity]:
        from clockin.models import PersonRegistry
        p = PersonRegistry.objects.filter(display_name__iexact=name, is_active=True).first()
        return self._to_entity(p)

    @staticmethod
    def _to_entity(p) -> Optional[PersonEntity]:
        if not p:
            return None
        return PersonEntity(
            id              = p.pk,
            display_name    = p.display_name,
            person_type     = p.person_type,
            fingerprint_id  = p.fingerprint_id,
            card_no         = p.card_no or '',
            dahua_user_id   = p.dahua_user_id or '',
            student_id      = p.student_id,
            employee_id     = p.employee_id,
            is_active       = p.is_active,
        )


class PersonEntityAdapter:
    """Converts a PersonRegistry ORM instance to PersonEntity (for legacy views)."""

    @staticmethod
    def from_model(p) -> PersonEntity:
        return DjangoPersonRepository._to_entity(p)
