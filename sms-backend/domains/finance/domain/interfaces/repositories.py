"""
Finance Domain — Repository Interfaces (Phase 6, Prompt 14)
Finance must NOT control Students or Academics — only uses student_id references.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional
from domains.finance.domain.entities import FeeStructure, Invoice, Payment


class FeeStructureRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[FeeStructure]: ...

    @abstractmethod
    def save(self, fee_structure: FeeStructure) -> FeeStructure: ...

    @abstractmethod
    def list(self, filters: dict | None = None) -> List[FeeStructure]: ...


class InvoiceRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Invoice]: ...

    @abstractmethod
    def get_by_student(self, student_id: int) -> List[Invoice]: ...

    @abstractmethod
    def save(self, invoice: Invoice) -> Invoice: ...

    @abstractmethod
    def list(self, filters: dict | None = None) -> List[Invoice]: ...


class PaymentRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Payment]: ...

    @abstractmethod
    def get_by_student(self, student_id: int) -> List[Payment]: ...

    @abstractmethod
    def save(self, payment: Payment) -> Payment: ...

    @abstractmethod
    def get_total_paid(self, student_id: int, invoice_id: int | None = None) -> Decimal: ...
