"""Hostel Operations Domain Entities — Phase 8 (Prompt 17)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Dormitory:
    id: Optional[int]
    name: str
    gender: Optional[str] = None
    total_beds: int = 0
    is_active: bool = True


@dataclass
class BedAllocation:
    id: Optional[int]
    student_id: int
    dormitory_id: int
    bed_number: Optional[str] = None
    allocated_date: Optional[str] = None
    is_active: bool = True
