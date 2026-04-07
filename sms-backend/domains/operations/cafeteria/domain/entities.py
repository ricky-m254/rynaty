"""Cafeteria Operations Domain Entities — Phase 8 (Prompt 17)."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class MealPlan:
    id: Optional[int]
    name: str
    price: Decimal = Decimal("0")
    meals_per_day: int = 3
    is_active: bool = True


@dataclass
class CafeteriaEnrollment:
    id: Optional[int]
    student_id: int
    plan_id: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_active: bool = True
