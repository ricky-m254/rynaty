"""
EnrollStudentService — Phase 5, Prompt 12.

Responsibilities:
- Student must exist
- Class must exist
- No duplicate enrollment (same student + class + term)
"""
from __future__ import annotations
from domains.academics.domain.entities import Enrollment
from domains.academics.domain.interfaces.repositories import (
    ClassRepository, EnrollmentRepository
)
from domains.users.domain.interfaces.repositories import StudentRepository


class EnrollStudentService:
    """Use case: Enroll a student into a class for a term."""

    def __init__(
        self,
        student_repo: StudentRepository,
        class_repo: ClassRepository,
        enrollment_repo: EnrollmentRepository,
    ) -> None:
        self._students = student_repo
        self._classes = class_repo
        self._enrollments = enrollment_repo

    def execute(
        self,
        student_id: int,
        class_id: int,
        term_id: int | None = None,
        enrollment_date: str | None = None,
    ) -> Enrollment:
        student = self._students.get_by_id(student_id)
        if student is None:
            raise ValueError(f"Student with id={student_id} does not exist.")

        school_class = self._classes.get_by_id(class_id)
        if school_class is None:
            raise ValueError(f"Class with id={class_id} does not exist.")

        if self._enrollments.exists(student_id, class_id, term_id):
            raise ValueError(
                f"Student {student_id} is already enrolled in class {class_id}"
                + (f" for term {term_id}" if term_id else "") + "."
            )

        enrollment = Enrollment(
            id=None,
            student_id=student_id,
            class_id=class_id,
            term_id=term_id,
            enrollment_date=enrollment_date,
        )
        enrollment.validate()
        return self._enrollments.save(enrollment)
