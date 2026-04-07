"""
DjangoStudentRepository — DBMA-mandated repository pattern.
Returns StudentEntity (domain), never raw Django model instances.
"""
from typing import Optional
from school.domain.entities.student import StudentEntity


class AbstractStudentRepository:
    def find_by_id(self, student_id: int) -> Optional[StudentEntity]: ...
    def find_by_admission_number(self, number: str) -> Optional[StudentEntity]: ...
    def save(self, entity: StudentEntity) -> StudentEntity: ...


class DjangoStudentRepository(AbstractStudentRepository):

    def find_by_id(self, student_id: int) -> Optional[StudentEntity]:
        from school.models import Student
        s = Student.objects.filter(pk=student_id).first()
        return self._to_entity(s)

    def find_by_admission_number(self, number: str) -> Optional[StudentEntity]:
        from school.models import Student
        s = Student.objects.filter(admission_number=number).first()
        return self._to_entity(s)

    @staticmethod
    def _to_entity(s) -> Optional[StudentEntity]:
        if not s:
            return None
        return StudentEntity(
            id               = s.pk,
            admission_number = s.admission_number,
            first_name       = s.first_name,
            last_name        = s.last_name,
            date_of_birth    = s.date_of_birth,
            gender           = s.gender,
            grade_level      = str(getattr(s, 'grade', '') or ''),
            ulid             = getattr(s, 'ulid', '') or '',
            is_active        = s.is_active,
            email            = getattr(s, 'email', '') or '',
            phone            = getattr(s, 'phone', '') or '',
        )

    def save(self, entity: StudentEntity) -> StudentEntity:
        from school.models import Student
        Student.objects.filter(pk=entity.id).update(
            first_name=entity.first_name,
            last_name=entity.last_name,
            email=entity.email,
            phone=entity.phone,
        )
        return entity
