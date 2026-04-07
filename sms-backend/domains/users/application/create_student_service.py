"""
CreateStudentService — Phase 2, Prompt 5 + Phase 3, Prompts 6-8.

Responsibilities:
- Validate required fields
- Prevent duplicate students (by admission number)
- Delegate persistence to StudentRepository interface
"""
from __future__ import annotations
from domains.users.domain.entities import Student
from domains.users.domain.interfaces.repositories import StudentRepository


class CreateStudentService:
    """Use case: Create a new Student."""

    def __init__(self, repository: StudentRepository) -> None:
        self._repo = repository

    def execute(
        self,
        admission_number: str,
        first_name: str,
        last_name: str,
        date_of_birth: str | None = None,
        gender: str | None = None,
        grade_level: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
    ) -> Student:
        student = Student(
            id=None,
            admission_number=admission_number.strip(),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            date_of_birth=date_of_birth,
            gender=gender,
            grade_level=grade_level,
            phone=phone,
            email=email,
            address=address,
        )
        student.validate()

        if self._repo.exists(student.admission_number):
            raise ValueError(
                f"A student with admission number '{student.admission_number}' already exists."
            )

        return self._repo.save(student)
