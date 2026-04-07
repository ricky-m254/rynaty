"""
DjangoStudentRepository — Phase 2-3, Prompt 9.
Concrete implementation of StudentRepository using Django ORM (school.Student model).
"""
from __future__ import annotations
from typing import List, Optional

from domains.users.domain.entities import Student
from domains.users.domain.interfaces.repositories import StudentRepository


def _entity_from_orm(s) -> Student:
    return Student(
        id=s.pk,
        admission_number=s.admission_number,
        first_name=s.first_name,
        last_name=s.last_name,
        date_of_birth=str(s.date_of_birth) if s.date_of_birth else None,
        gender=s.gender if hasattr(s, 'gender') else None,
        grade_level=s.current_class.name if (hasattr(s, 'current_class') and s.current_class) else None,
        phone=getattr(s, 'phone_number', None) or getattr(s, 'phone', None) or '',
        email=getattr(s, 'email', None) or '',
        is_active=s.is_active if hasattr(s, 'is_active') else True,
    )


class DjangoStudentRepository(StudentRepository):
    """Django ORM implementation of StudentRepository."""

    def _model(self):
        from school.models import Student as StudentModel
        return StudentModel

    def get_by_id(self, id: int) -> Optional[Student]:
        try:
            return _entity_from_orm(self._model().objects.get(pk=id))
        except self._model().DoesNotExist:
            return None

    def get_by_admission_number(self, admission_number: str) -> Optional[Student]:
        try:
            return _entity_from_orm(
                self._model().objects.get(admission_number=admission_number)
            )
        except self._model().DoesNotExist:
            return None

    def save(self, student: Student) -> Student:
        Model = self._model()
        if student.id:
            orm_obj = Model.objects.get(pk=student.id)
            orm_obj.first_name = student.first_name
            orm_obj.last_name = student.last_name
            if student.date_of_birth:
                orm_obj.date_of_birth = student.date_of_birth
            if hasattr(orm_obj, 'phone_number'):
                orm_obj.phone_number = student.phone or ''
            orm_obj.save()
        else:
            orm_obj = Model.objects.create(
                admission_number=student.admission_number,
                first_name=student.first_name,
                last_name=student.last_name,
                date_of_birth=student.date_of_birth,
            )
        return _entity_from_orm(orm_obj)

    def list(self, filters: dict | None = None) -> List[Student]:
        qs = self._model().objects.all()
        if filters:
            qs = qs.filter(**filters)
        return [_entity_from_orm(s) for s in qs]

    def exists(self, admission_number: str) -> bool:
        return self._model().objects.filter(admission_number=admission_number).exists()
