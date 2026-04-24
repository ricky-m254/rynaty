import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from django.conf import settings

if not settings.configured:
    settings.configure(USE_TZ=True, TIME_ZONE="UTC")

from domains.inventory.application.services import (
    InventoryNotFoundError,
    InventoryValidationError,
    StoreDashboardService,
    StoreOrderWorkflowService,
    StoreReportsService,
    extract_order_items_payload,
    normalize_review_action,
)


class FakeRepository:
    def __init__(self):
        self.order = SimpleNamespace(
            id=3,
            status="PENDING",
            notes="keep",
            request_code="REQ-2026-0003",
            document_number="LPO-2026-0003",
            title="Restock Office Supplies",
            description="Bulk order",
            procurement_type="LPO",
            office_owner="FINANCE",
            supplier=SimpleNamespace(name="Acme Supplies"),
            reviewed_at=None,
            reviewed_by=None,
            approval_trail=[],
            approved_total=Decimal("0.00"),
            receiving_state="PENDING",
            received_by=None,
            received_at=None,
            received_notes="",
            generated_expense_id=None,
            generated_expense=None,
        )
        self.order_items = {
            7: SimpleNamespace(
                id=7,
                quantity_requested=Decimal("5"),
                quantity_approved=None,
                quoted_unit_price=Decimal("31.25"),
                approved_total=Decimal("0.00"),
                item=SimpleNamespace(cost_price=Decimal("31.25")),
                item_id=5,
            )
        }
        self.order.items = SimpleNamespace(all=lambda: list(self.order_items.values()))
        self.item_cost_prices = {5: Decimal("25.00")}
        self.created_items = []
        self.saved_orders = []
        self.saved_order_items = []
        self.expense_calls = []

    def find_order(self, order_id: int):
        return self.order if order_id == self.order.id else None

    def find_order_item(self, order_item_id: int):
        return self.order_items.get(order_item_id)

    def find_item_name(self, item_id: int | None) -> str:
        return "Fallback Name" if item_id else ""

    def find_item_cost_price(self, item_id: int | None) -> Decimal:
        return self.item_cost_prices.get(item_id, Decimal("0.00"))

    def create_order_item(self, **kwargs):
        self.created_items.append(kwargs)

    def save_order(self, order, update_fields=None):
        self.saved_orders.append((order.status, update_fields))
        return order

    def save_order_item(self, order_item, update_fields=None):
        self.saved_order_items.append((order_item.id, order_item.quantity_approved, update_fields))
        return order_item

    def calculate_order_total(self, order):
        return Decimal("125.50")

    def create_expense_for_order(self, **kwargs):
        self.expense_calls.append(kwargs)
        return SimpleNamespace(id=91)

    def build_dashboard_payload(self):
        return {"total_items": 4, "low_stock_count": 1}

    def build_reports_payload(self):
        return {"report_month_label": "April 2026", "monthly_procurement_total": 125.5}

    def build_module_summary(self):
        return {"total_items": 4, "low_stock": 1, "pending_orders": 2}


class StoreWorkflowServiceTests(unittest.TestCase):
    def test_normalize_review_action_accepts_action_or_status(self):
        self.assertEqual(normalize_review_action(action="approve"), "APPROVE")
        self.assertEqual(normalize_review_action(status_value="rejected"), "REJECT")

    def test_normalize_review_action_rejects_unknown_values(self):
        with self.assertRaises(InventoryValidationError):
            normalize_review_action(action="ship")

    def test_extract_order_items_payload_supports_legacy_and_new_keys(self):
        self.assertEqual(extract_order_items_payload({"items": [{"item_name": "A"}]}), [{"item_name": "A"}])
        self.assertEqual(
            extract_order_items_payload({"order_items": [{"item_name": "B"}], "items": [{"item_name": "A"}]}),
            [{"item_name": "B"}],
        )

    def test_create_order_items_accepts_frontend_items_payload(self):
        repository = FakeRepository()
        service = StoreOrderWorkflowService(repository)

        service.create_order_items(
            order=repository.order,
            payload={
                "items": [
                    {
                        "item": 5,
                        "quantity_requested": 3,
                        "unit": "box",
                        "notes": "urgent",
                    }
                ]
            },
        )

        self.assertEqual(len(repository.created_items), 1)
        self.assertEqual(repository.created_items[0]["item_name"], "Fallback Name")
        self.assertEqual(repository.created_items[0]["unit"], "box")
        self.assertEqual(repository.created_items[0]["quoted_unit_price"], Decimal("25.00"))

    def test_review_order_supports_status_payload_and_updates_approved_items(self):
        repository = FakeRepository()
        service = StoreOrderWorkflowService(repository)

        response = service.review_order(
            order_id=3,
            payload={
                "status": "approved",
                "notes": "looks good",
                "approved_items": [{"id": 7, "quantity_approved": Decimal("4")}],
            },
            reviewer="auditor",
        )

        self.assertEqual(response["status"], "APPROVED")
        self.assertEqual(repository.order.status, "APPROVED")
        self.assertEqual(repository.order.notes, "looks good")
        self.assertEqual(repository.order.reviewed_by, "auditor")
        self.assertIsInstance(repository.order.reviewed_at, datetime)
        self.assertEqual(repository.order.approved_total, Decimal("125.00"))
        self.assertEqual(repository.order.approval_trail[-1]["action"], "APPROVE")
        self.assertEqual(repository.order_items[7].quantity_approved, Decimal("4"))
        self.assertEqual(repository.order_items[7].approved_total, Decimal("125.00"))
        self.assertEqual(repository.saved_order_items[0][0], 7)

    def test_review_order_coerces_string_payload_numbers(self):
        repository = FakeRepository()
        service = StoreOrderWorkflowService(repository)

        response = service.review_order(
            order_id=3,
            payload={
                "action": "APPROVE",
                "approved_items": [{"id": 7, "quantity_approved": "5.00", "quoted_unit_price": "31.25"}],
            },
            reviewer="auditor",
        )

        self.assertEqual(response["status"], "APPROVED")
        self.assertEqual(repository.order_items[7].quantity_approved, Decimal("5.00"))
        self.assertEqual(repository.order_items[7].quoted_unit_price, Decimal("31.25"))
        self.assertEqual(repository.order_items[7].approved_total, Decimal("156.2500"))

    def test_review_order_rejects_invalid_numeric_payload(self):
        repository = FakeRepository()
        service = StoreOrderWorkflowService(repository)

        with self.assertRaises(InventoryValidationError):
            service.review_order(
                order_id=3,
                payload={
                    "action": "APPROVE",
                    "approved_items": [{"id": 7, "quantity_approved": "five"}],
                },
                reviewer="auditor",
            )

    def test_review_order_records_fulfillment_and_receiving_state(self):
        repository = FakeRepository()
        repository.order.status = "APPROVED"
        repository.order.approved_total = Decimal("125.50")
        service = StoreOrderWorkflowService(repository)

        response = service.review_order(
            order_id=3,
            payload={
                "status": "fulfilled",
                "notes": "received from supplier",
            },
            reviewer="storekeeper",
        )

        self.assertEqual(response["status"], "FULFILLED")
        self.assertEqual(repository.order.status, "FULFILLED")
        self.assertEqual(repository.order.receiving_state, "RECEIVED")
        self.assertEqual(repository.order.received_by, "storekeeper")
        self.assertIsNotNone(repository.order.received_at)
        self.assertEqual(repository.order.received_notes, "received from supplier")
        self.assertEqual(repository.order.approval_trail[-1]["action"], "FULFILL")

    def test_review_order_raises_for_missing_order(self):
        repository = FakeRepository()
        service = StoreOrderWorkflowService(repository)

        with self.assertRaises(InventoryNotFoundError):
            service.review_order(order_id=999, payload={"action": "APPROVE"}, reviewer="auditor")

    def test_generate_expense_returns_existing_link_without_duplicate_creation(self):
        repository = FakeRepository()
        repository.order.generated_expense_id = 44
        service = StoreOrderWorkflowService(repository)

        response = service.generate_expense(order_id=3)

        self.assertTrue(response["already_generated"])
        self.assertEqual(response["expense_id"], 44)
        self.assertEqual(repository.expense_calls, [])

    def test_generate_expense_requires_approved_state(self):
        repository = FakeRepository()
        service = StoreOrderWorkflowService(repository)

        with self.assertRaises(InventoryValidationError):
            service.generate_expense(order_id=3)

    def test_generate_expense_creates_linked_expense(self):
        repository = FakeRepository()
        repository.order.status = "APPROVED"
        repository.order.reviewed_at = datetime(2026, 3, 30, 12, 0, 0)
        repository.order.approved_total = Decimal("125.50")
        service = StoreOrderWorkflowService(repository)

        response = service.generate_expense(order_id=3)

        self.assertEqual(response["expense_id"], 91)
        self.assertEqual(response["amount"], Decimal("125.50"))
        self.assertEqual(repository.expense_calls[0]["amount"], Decimal("125.50"))
        self.assertEqual(repository.expense_calls[0]["expense_date"], date(2026, 3, 30))
        self.assertEqual(repository.expense_calls[0]["description"], "LPO-2026-0003: Restock Office Supplies. Bulk order")
        self.assertEqual(repository.order.generated_expense.id, 91)
        self.assertEqual(repository.saved_orders[-1][1], ["generated_expense"])
        self.assertEqual(repository.expense_calls[0]["order"].document_number, "LPO-2026-0003")
        self.assertEqual(repository.expense_calls[0]["order"].supplier.name, "Acme Supplies")

    def test_dashboard_service_proxies_repository_summary(self):
        repository = FakeRepository()
        service = StoreDashboardService(repository)

        self.assertEqual(service.get_dashboard(), {"total_items": 4, "low_stock_count": 1})
        self.assertEqual(
            service.get_module_summary(),
            {"total_items": 4, "low_stock": 1, "pending_orders": 2},
        )

    def test_reports_service_proxies_repository_payload(self):
        repository = FakeRepository()
        service = StoreReportsService(repository)

        self.assertEqual(
            service.get_reports(),
            {"report_month_label": "April 2026", "monthly_procurement_total": 125.5},
        )


if __name__ == "__main__":
    unittest.main()
