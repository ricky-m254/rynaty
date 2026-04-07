"""Inventory Domain — Repository Interfaces (Phase 7)."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from domains.inventory.domain.entities import Item, Stock, StockMovement, Asset


class ItemRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Item]: ...

    @abstractmethod
    def save(self, item: Item) -> Item: ...

    @abstractmethod
    def list(self, filters: dict | None = None) -> List[Item]: ...


class StockRepository(ABC):
    @abstractmethod
    def get_by_item(self, item_id: int) -> Optional[Stock]: ...

    @abstractmethod
    def save(self, stock: Stock) -> Stock: ...

    @abstractmethod
    def list_low_stock(self, reorder_level: int = 5) -> List[Stock]: ...


class StockMovementRepository(ABC):
    @abstractmethod
    def save(self, movement: StockMovement) -> StockMovement: ...

    @abstractmethod
    def list(self, item_id: int | None = None) -> List[StockMovement]: ...


class AssetRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Asset]: ...

    @abstractmethod
    def save(self, asset: Asset) -> Asset: ...

    @abstractmethod
    def list(self, filters: dict | None = None) -> List[Asset]: ...
