"""Visitor Management Operations Domain Entities — Phase 8 (Prompt 17)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Visitor:
    id: Optional[int]
    name: str
    id_number: Optional[str] = None
    phone: Optional[str] = None
    purpose: Optional[str] = None
    host_name: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    status: str = "CHECKED_IN"

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Visitor name is required")
