"""
Users Domain — Repository Interfaces (Phase 2, Prompt 4)
Abstract contracts only.  Do NOT implement database logic here.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from domains.users.domain.entities import Student, Parent


class StudentRepository(ABC):
    """Abstract repository contract for Student persistence."""

    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Student]:
        ...

    @abstractmethod
    def get_by_admission_number(self, admission_number: str) -> Optional[Student]:
        ...

    @abstractmethod
    def save(self, student: Student) -> Student:
        ...

    @abstractmethod
    def list(self, filters: dict | None = None) -> List[Student]:
        ...

    @abstractmethod
    def exists(self, admission_number: str) -> bool:
        ...


class ParentRepository(ABC):
    """Abstract repository contract for Parent persistence."""

    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Parent]:
        ...

    @abstractmethod
    def save(self, parent: Parent) -> Parent:
        ...

    @abstractmethod
    def list(self, filters: dict | None = None) -> List[Parent]:
        ...
