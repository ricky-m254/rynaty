"""Library Operations Domain Entities — Phase 8 (Prompt 17)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Book:
    id: Optional[int]
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    category: Optional[str] = None
    copies_total: int = 1
    copies_available: int = 1
    is_active: bool = True

    def validate(self) -> None:
        if not self.title:
            raise ValueError("Book title is required")
        if self.copies_total < 0:
            raise ValueError("copies_total must be non-negative")


@dataclass
class Circulation:
    """A library book loan record."""
    id: Optional[int]
    book_id: int
    member_id: int
    issued_date: Optional[str] = None
    due_date: Optional[str] = None
    returned_date: Optional[str] = None
    status: str = "ISSUED"

    STATUSES = ("ISSUED", "RETURNED", "OVERDUE")
