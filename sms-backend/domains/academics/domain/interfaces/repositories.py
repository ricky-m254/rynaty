"""
Academics Domain — Repository Interfaces
Abstract contracts only.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from domains.academics.domain.entities import SchoolClass, Subject, Enrollment


class ClassRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[SchoolClass]: ...

    @abstractmethod
    def save(self, school_class: SchoolClass) -> SchoolClass: ...

    @abstractmethod
    def list(self, filters: dict | None = None) -> List[SchoolClass]: ...


class SubjectRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Subject]: ...

    @abstractmethod
    def save(self, subject: Subject) -> Subject: ...

    @abstractmethod
    def list(self, filters: dict | None = None) -> List[Subject]: ...


class EnrollmentRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Enrollment]: ...

    @abstractmethod
    def save(self, enrollment: Enrollment) -> Enrollment: ...

    @abstractmethod
    def list(self, filters: dict | None = None) -> List[Enrollment]: ...

    @abstractmethod
    def exists(self, student_id: int, class_id: int, term_id: int | None) -> bool: ...
