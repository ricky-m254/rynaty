"""Transport Operations Domain Entities — Phase 8 (Prompt 17)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Vehicle:
    id: Optional[int]
    registration: str
    make: Optional[str] = None
    model: Optional[str] = None
    capacity: int = 40
    status: str = "Active"
    notes: Optional[str] = None

    def validate(self) -> None:
        if not self.registration:
            raise ValueError("Vehicle registration is required")


@dataclass
class Route:
    id: Optional[int]
    name: str
    direction: str = "ONE_WAY"
    vehicle_id: Optional[int] = None
    is_active: bool = True
