"""
Inventory Domain Entities — Phase 7 (Prompts 15-16)
Covers: Item, Stock, StockMovement, Asset
Pure Python dataclasses. No Django. No ORM.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class Item:
    id: Optional[int]
    name: str
    code: Optional[str] = None
    category: Optional[str] = None
    unit: str = "PCS"
    reorder_level: int = 5
    is_active: bool = True

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Item name is required")
        if self.reorder_level < 0:
            raise ValueError("reorder_level must be non-negative")


@dataclass
class Stock:
    id: Optional[int]
    item_id: int
    quantity: int
    location: Optional[str] = None
    last_updated: Optional[str] = None

    def validate(self) -> None:
        if self.quantity < 0:
            raise ValueError("Stock quantity must be non-negative")

    @property
    def is_low(self) -> bool:
        return self.quantity <= 0


@dataclass
class StockMovement:
    id: Optional[int]
    item_id: int
    movement_type: str
    quantity: int
    reason: Optional[str] = None
    reference: Optional[str] = None
    moved_at: Optional[str] = None

    MOVEMENT_TYPES = ("IN", "OUT", "ADJUSTMENT", "TRANSFER")

    def validate(self) -> None:
        if self.movement_type not in self.MOVEMENT_TYPES:
            raise ValueError(f"movement_type must be one of {self.MOVEMENT_TYPES}")
        if self.quantity <= 0:
            raise ValueError("StockMovement quantity must be positive")


@dataclass
class Asset:
    id: Optional[int]
    name: str
    asset_tag: Optional[str] = None
    category: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_cost: Decimal = Decimal("0")
    current_value: Decimal = Decimal("0")
    location: Optional[str] = None
    status: str = "ACTIVE"
    is_active: bool = True

    STATUSES = ("ACTIVE", "MAINTENANCE", "DISPOSED", "LOST")

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Asset name is required")
        if self.status not in self.STATUSES:
            raise ValueError(f"status must be one of {self.STATUSES}")
