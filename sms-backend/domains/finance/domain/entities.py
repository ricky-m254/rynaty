"""
Finance Domain Entities — Phase 6 (Prompts 13-14)
Pure Python dataclasses. No Django. No ORM.
IPSAS-compliant — uses student_id references only (no FK coupling to Student model).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List


@dataclass
class FeeStructure:
    id: Optional[int]
    name: str
    amount: Decimal
    currency: str = "KES"
    term_id: Optional[int] = None
    grade_level: Optional[str] = None
    is_active: bool = True

    def validate(self) -> None:
        if not self.name:
            raise ValueError("FeeStructure name is required")
        if self.amount < Decimal("0"):
            raise ValueError("Amount must be non-negative")


@dataclass
class Invoice:
    id: Optional[int]
    student_id: int
    amount: Decimal
    currency: str = "KES"
    status: str = "UNPAID"
    due_date: Optional[str] = None
    term_id: Optional[int] = None
    notes: Optional[str] = None

    ALLOWED_STATUSES = ("UNPAID", "PARTIAL", "PAID", "CANCELLED", "OVERDUE")

    def validate(self) -> None:
        if self.amount < Decimal("0"):
            raise ValueError("Invoice amount must be non-negative")
        if self.status not in self.ALLOWED_STATUSES:
            raise ValueError(f"status must be one of {self.ALLOWED_STATUSES}")

    @property
    def is_settled(self) -> bool:
        return self.status == "PAID"


@dataclass
class Payment:
    id: Optional[int]
    student_id: int
    invoice_id: Optional[int]
    amount: Decimal
    currency: str = "KES"
    payment_method: str = "CASH"
    reference: Optional[str] = None
    paid_date: Optional[str] = None
    notes: Optional[str] = None

    def validate(self) -> None:
        if self.amount <= Decimal("0"):
            raise ValueError("Payment amount must be positive")
