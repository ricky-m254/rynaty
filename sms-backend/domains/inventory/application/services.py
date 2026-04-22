from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from django.utils import timezone


class InventoryValidationError(Exception):
    """Raised when an inventory workflow request is invalid."""


class InventoryNotFoundError(Exception):
    """Raised when an inventory workflow target cannot be found."""


_ACTION_TO_STATUS = {
    "APPROVE": "APPROVED",
    "REJECT": "REJECTED",
    "FULFILL": "FULFILLED",
}

_STATUS_TO_ACTION = {value: key for key, value in _ACTION_TO_STATUS.items()}


class StoreRepositoryProtocol(Protocol):
    def find_order(self, order_id: int): ...
    def find_order_item(self, order_item_id: int): ...
    def find_item_name(self, item_id: int | None) -> str: ...
    def create_order_item(
        self,
        *,
        order,
        item_id: int | None,
        item_name: str,
        unit: str,
        quantity_requested,
        quoted_unit_price,
        notes: str,
    ): ...
    def find_item_cost_price(self, item_id: int | None) -> Decimal: ...
    def save_order(self, order, update_fields: list[str] | None = None): ...
    def save_order_item(self, order_item, update_fields: list[str] | None = None): ...
    def calculate_order_total(self, order): ...
    def create_expense_for_order(self, *, order, amount, expense_date: date, description: str): ...
    def build_dashboard_payload(self) -> dict[str, Any]: ...
    def build_reports_payload(self) -> dict[str, Any]: ...
    def build_module_summary(self) -> dict[str, int]: ...


def normalize_review_action(*, action: str | None = None, status_value: str | None = None) -> str:
    normalized_action = (action or "").strip().upper()
    if normalized_action in _ACTION_TO_STATUS:
        return normalized_action

    normalized_status = (status_value or "").strip().upper()
    if normalized_status in _STATUS_TO_ACTION:
        return _STATUS_TO_ACTION[normalized_status]

    raise InventoryValidationError("action must be APPROVE, REJECT, or FULFILL.")


def extract_order_items_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("order_items")
    if items is None:
        items = payload.get("items", [])
    return items or []


def _order_trail_entry(*, action: str, reviewer, notes: str, status: str, order) -> dict[str, Any]:
    reviewer_name = getattr(reviewer, "get_username", None)
    reviewer_label = reviewer.get_username() if callable(reviewer_name) else str(reviewer)
    return {
        "action": action,
        "status": status,
        "order_id": order.id,
        "order_code": getattr(order, "document_number", None) or getattr(order, "request_code", None),
        "office_owner": getattr(order, "office_owner", None),
        "procurement_type": getattr(order, "procurement_type", None),
        "notes": notes,
        "actor": reviewer_label,
        "timestamp": timezone.now().isoformat(),
    }


@dataclass
class StoreDashboardService:
    repository: StoreRepositoryProtocol

    def get_dashboard(self) -> dict[str, Any]:
        return self.repository.build_dashboard_payload()

    def get_module_summary(self) -> dict[str, int]:
        return self.repository.build_module_summary()


@dataclass
class StoreReportsService:
    repository: StoreRepositoryProtocol

    def get_reports(self) -> dict[str, Any]:
        return self.repository.build_reports_payload()


@dataclass
class StoreOrderWorkflowService:
    repository: StoreRepositoryProtocol

    def create_order_items(self, *, order, payload: dict[str, Any]) -> None:
        for item_data in extract_order_items_payload(payload):
            item_id = item_data.get("item") or None
            item_name = (item_data.get("item_name") or "").strip()
            fallback_name = self.repository.find_item_name(item_id) if item_id else ""
            quoted_unit_price = item_data.get("quoted_unit_price")
            if quoted_unit_price in (None, ""):
                quoted_unit_price = self.repository.find_item_cost_price(item_id)
            self.repository.create_order_item(
                order=order,
                item_id=item_id,
                item_name=item_name or fallback_name,
                unit=item_data.get("unit", "pcs"),
                quantity_requested=item_data.get("quantity_requested", 1),
                quoted_unit_price=quoted_unit_price,
                notes=item_data.get("notes", ""),
            )

    def review_order(self, *, order_id: int, payload: dict[str, Any], reviewer) -> dict[str, str]:
        order = self.repository.find_order(order_id)
        if order is None:
            raise InventoryNotFoundError("Order not found.")

        action = normalize_review_action(
            action=payload.get("action"),
            status_value=payload.get("status"),
        )
        if action in {"APPROVE", "REJECT"} and order.status != "PENDING":
            raise InventoryValidationError("Only pending orders can be reviewed.")
        if action == "FULFILL" and order.status != "APPROVED":
            raise InventoryValidationError("Only approved orders can be fulfilled.")

        approved_total = Decimal("0.00")
        current_item_map = {item.id: item for item in order.items.all()}
        for approved_item in payload.get("approved_items", []) or []:
            order_item_id = approved_item.get("id")
            if not order_item_id:
                continue
            order_item = current_item_map.get(order_item_id) or self.repository.find_order_item(order_item_id)
            if order_item is None:
                continue
            order_item.quantity_approved = approved_item.get(
                "quantity_approved",
                order_item.quantity_requested,
            )
            quoted_unit_price = approved_item.get("quoted_unit_price", order_item.quoted_unit_price)
            if quoted_unit_price in (None, ""):
                quoted_unit_price = order_item.item.cost_price if order_item.item_id and order_item.item else Decimal("0.00")
            order_item.quoted_unit_price = quoted_unit_price
            order_item.approved_total = (order_item.quantity_approved or Decimal("0.00")) * (
                order_item.quoted_unit_price or Decimal("0.00")
            )
            approved_total += order_item.approved_total
            self.repository.save_order_item(
                order_item,
                update_fields=["quantity_approved", "quoted_unit_price", "approved_total"],
            )

        if action in {"APPROVE", "FULFILL"} and approved_total <= Decimal("0.00"):
            approved_total = self.repository.calculate_order_total(order)

        order.status = _ACTION_TO_STATUS[action]
        order.reviewed_by = reviewer
        order.reviewed_at = timezone.now()
        order.notes = str(payload.get("notes") or order.notes or "").strip()
        if action == "APPROVE":
            order.receiving_state = "PENDING"
            order.approved_total = approved_total
        elif action == "REJECT":
            order.approved_total = Decimal("0.00")
            order.receiving_state = "PENDING"
        elif action == "FULFILL":
            order.receiving_state = "RECEIVED"
            order.received_by = reviewer
            order.received_at = timezone.now()
            order.received_notes = str(payload.get("notes") or order.received_notes or "").strip()
            if order.approved_total <= Decimal("0.00"):
                order.approved_total = self.repository.calculate_order_total(order)

        trail = list(getattr(order, "approval_trail", []) or [])
        trail.append(
            _order_trail_entry(
                action=action,
                reviewer=reviewer,
                notes=payload.get("notes", ""),
                status=order.status,
                order=order,
            )
        )
        order.approval_trail = trail
        self.repository.save_order(
            order,
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "notes",
                "approval_trail",
                "approved_total",
                "receiving_state",
                "received_by",
                "received_at",
                "received_notes",
            ],
        )

        return {
            "detail": f"Order {order.status.lower()}.",
            "status": order.status,
        }

    def generate_expense(self, *, order_id: int) -> dict[str, Any]:
        order = self.repository.find_order(order_id)
        if order is None:
            raise InventoryNotFoundError("Order not found.")

        if order.generated_expense_id:
            return {
                "already_generated": True,
                "expense_id": order.generated_expense_id,
                "message": f"Expense already generated (Expense #{order.generated_expense_id}).",
            }

        if order.status not in ("APPROVED", "FULFILLED"):
            raise InventoryValidationError(
                "Only approved or fulfilled orders can generate expenses."
            )

        total = self.repository.calculate_order_total(order)
        expense = self.repository.create_expense_for_order(
            order=order,
            amount=total,
            expense_date=order.reviewed_at.date() if order.reviewed_at else date.today(),
            description=(
                f'{order.document_number or order.request_code or ("Order #" + str(order.id))}: '
                f'{order.title}. {order.description}'
            ).strip(),
        )
        order.generated_expense = expense
        self.repository.save_order(order, update_fields=["generated_expense"])

        return {
            "expense_id": expense.id,
            "amount": total,
            "message": "Expense record created.",
        }


def get_store_module_summary(repository: StoreRepositoryProtocol | None = None) -> dict[str, int]:
    if repository is None:
        from domains.inventory.infrastructure.django_store_repository import (
            DjangoStoreRepository,
        )

        repository = DjangoStoreRepository()

    return StoreDashboardService(repository).get_module_summary()
