"""
Base repository and entity interfaces (contracts).
Every domain implements these — never inherits across domain boundaries.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, TypeVar, Generic

T = TypeVar('T')


class AbstractRepository(ABC, Generic[T]):
    """Base contract for all repositories. Keeps domain logic ORM-agnostic."""

    @abstractmethod
    def find_by_id(self, entity_id) -> Optional[T]:
        raise NotImplementedError

    @abstractmethod
    def save(self, entity: T) -> T:
        raise NotImplementedError

    @abstractmethod
    def delete(self, entity_id) -> None:
        raise NotImplementedError


class AbstractEntity(ABC):
    """Marker base for all domain entities (pure Python — no Django ORM)."""

    @abstractmethod
    def validate(self) -> None:
        """Raise DomainValidationError if the entity is in an invalid state."""
        raise NotImplementedError
