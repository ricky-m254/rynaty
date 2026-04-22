from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import F
from django.utils import timezone

from school.models import (
    Expense,
    StoreCategory,
    StoreItem,
    StoreOrderItem,
    StoreOrderRequest,
    StoreSupplier,
    StoreTransaction,
)


def _previous_month_start(month_start):
    return (month_start - timedelta(days=1)).replace(day=1)


def _next_month_start(month_start):
    return (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)


def _decimal_or_zero(value):
    return value or Decimal("0.00")


class DjangoStoreRepository:
    def list_categories(
        self,
        *,
        item_type: str | None = None,
        is_active: bool | None = None,
    ):
        queryset = StoreCategory.objects.all()
        if item_type:
            queryset = queryset.filter(item_type=item_type.upper())
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        return queryset.order_by("name")

    def list_suppliers(self, *, is_active: bool | None = None, search: str | None = None):
        queryset = StoreSupplier.objects.all()
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by("name")

    def list_items(
        self,
        *,
        item_type: str | None = None,
        low_stock: bool = False,
        is_active: bool | None = None,
        search: str | None = None,
    ):
        queryset = StoreItem.objects.select_related("category").all()
        if item_type and item_type.upper() != "ALL":
            queryset = queryset.filter(item_type=item_type.upper())
        if low_stock:
            queryset = queryset.filter(current_stock__lte=F("reorder_level"))
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by("name")

    def list_transactions(
        self,
        *,
        item_id: str | None = None,
        transaction_type: str | None = None,
        department: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        queryset = StoreTransaction.objects.select_related("item", "performed_by").all()
        if item_id:
            queryset = queryset.filter(item_id=item_id)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type.upper())
        if department:
            queryset = queryset.filter(department__icontains=department)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        return queryset.order_by("-date", "-created_at")

    def list_orders(
        self,
        *,
        status: str | None = None,
        send_to: str | None = None,
        procurement_type: str | None = None,
        office_owner: str | None = None,
        receiving_state: str | None = None,
        supplier_id: str | None = None,
        document_number: str | None = None,
    ):
        queryset = (
            StoreOrderRequest.objects.select_related(
                "requested_by",
                "reviewed_by",
                "received_by",
                "supplier",
                "generated_expense",
            )
            .prefetch_related("items__item")
            .all()
        )
        if status:
            queryset = queryset.filter(status=status.upper())
        if send_to:
            queryset = queryset.filter(send_to__in=[send_to.upper(), "BOTH"])
        if procurement_type:
            queryset = queryset.filter(procurement_type=procurement_type.upper())
        if office_owner:
            queryset = queryset.filter(office_owner=office_owner.upper())
        if receiving_state:
            queryset = queryset.filter(receiving_state=receiving_state.upper())
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        if document_number:
            queryset = queryset.filter(document_number__icontains=document_number)
        return queryset.order_by("-created_at")

    def find_order(self, order_id: int):
        return (
            StoreOrderRequest.objects.select_related(
                "requested_by",
                "reviewed_by",
                "received_by",
                "supplier",
                "generated_expense",
            )
            .prefetch_related("items__item")
            .filter(id=order_id)
            .first()
        )

    def find_order_item(self, order_item_id: int):
        return StoreOrderItem.objects.filter(id=order_item_id).first()

    def find_item_name(self, item_id: int | None) -> str:
        if not item_id:
            return ""
        return (
            StoreItem.objects.filter(id=item_id).values_list("name", flat=True).first() or ""
        )

    def find_item_cost_price(self, item_id: int | None) -> Decimal:
        if not item_id:
            return Decimal("0.00")
        value = StoreItem.objects.filter(id=item_id).values_list("cost_price", flat=True).first()
        return value or Decimal("0.00")

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
    ):
        return StoreOrderItem.objects.create(
            order=order,
            item_id=item_id,
            item_name=item_name,
            unit=unit,
            quantity_requested=quantity_requested,
            quoted_unit_price=quoted_unit_price,
            notes=notes,
        )

    def save_order(self, order, update_fields: list[str] | None = None):
        if update_fields:
            order.save(update_fields=update_fields)
        else:
            order.save()
        return order

    def save_order_item(self, order_item, update_fields: list[str] | None = None):
        if update_fields:
            order_item.save(update_fields=update_fields)
        else:
            order_item.save()
        return order_item

    def calculate_order_total(self, order) -> Decimal:
        approved_total = getattr(order, "approved_total", None)
        if approved_total and approved_total > Decimal("0.00"):
            return approved_total
        total = Decimal("0")
        for order_item in order.items.select_related("item").all():
            quantity = order_item.quantity_approved or order_item.quantity_requested or Decimal("0")
            quoted_unit_price = order_item.quoted_unit_price or Decimal("0")
            if quoted_unit_price <= 0 and order_item.item_id and order_item.item:
                quoted_unit_price = order_item.item.cost_price or Decimal("0")
            total += quantity * (quoted_unit_price or Decimal("0"))
        return total

    def create_expense_for_order(self, *, order, amount, expense_date, description: str):
        supplier_name = ""
        if getattr(order, "supplier", None):
            supplier_name = order.supplier.name or ""
        return Expense.objects.create(
            category="Local Purchase" if getattr(order, "procurement_type", "LPO") == "LPO" else "Local Supply",
            amount=max(amount, Decimal("0.01")),
            expense_date=expense_date,
            vendor=supplier_name or (order.office_owner or "Store"),
            invoice_number=order.document_number or order.request_code or f"REQ-{order.id}",
            approval_status="Approved",
            description=description,
        )

    def build_dashboard_payload(self) -> dict[str, object]:
        low_stock_items = list(
            StoreItem.objects.filter(is_active=True, current_stock__lte=F("reorder_level"))
            .values("id", "name", "current_stock", "reorder_level", "unit", "item_type")[:10]
        )
        recent_transactions = list(
            StoreTransaction.objects.select_related("item")
            .values("id", "transaction_type", "quantity", "date", "item__name", "item__unit", "purpose")
            .order_by("-date", "-created_at")[:10]
        )
        procurement_orders = list(
            StoreOrderRequest.objects.select_related("supplier")
            .prefetch_related("items__item")
            .all()
        )
        return {
            "total_items": StoreItem.objects.filter(is_active=True).count(),
            "low_stock_count": len(low_stock_items),
            "low_stock_items": low_stock_items,
            "pending_orders": StoreOrderRequest.objects.filter(status="PENDING").count(),
            "pending_procurement_orders": StoreOrderRequest.objects.filter(status="PENDING").count(),
            "pending_lpo_orders": StoreOrderRequest.objects.filter(status="PENDING", procurement_type="LPO").count(),
            "pending_lso_orders": StoreOrderRequest.objects.filter(status="PENDING", procurement_type="LSO").count(),
            "approved_procurement_total": float(
                sum(
                    (self.calculate_order_total(order) for order in procurement_orders if order.status in {"APPROVED", "FULFILLED"}),
                    Decimal("0.00"),
                )
            ),
            "total_categories": StoreCategory.objects.filter(is_active=True).count(),
            "recent_transactions": recent_transactions,
        }

    def build_reports_payload(self) -> dict[str, object]:
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        previous_month_start = _previous_month_start(current_month_start)

        active_items = list(StoreItem.objects.filter(is_active=True).order_by("name"))
        inventory_value = sum(
            (_decimal_or_zero(item.current_stock) * _decimal_or_zero(item.cost_price))
            for item in active_items
        )
        low_stock_items = sum(1 for item in active_items if item.current_stock <= item.reorder_level)

        def transaction_value(transaction):
            item_cost = _decimal_or_zero(getattr(transaction.item, "cost_price", None))
            return _decimal_or_zero(transaction.quantity) * item_cost

        current_month_receipts = list(
            StoreTransaction.objects.select_related("item")
            .filter(
                transaction_type="RECEIPT",
                date__gte=current_month_start,
                date__lte=today,
            )
            .order_by("date", "created_at")
        )
        previous_month_receipts = list(
            StoreTransaction.objects.select_related("item")
            .filter(
                transaction_type="RECEIPT",
                date__gte=previous_month_start,
                date__lt=current_month_start,
            )
            .order_by("date", "created_at")
        )
        current_month_issuances = list(
            StoreTransaction.objects.select_related("item")
            .filter(
                transaction_type="ISSUANCE",
                date__gte=current_month_start,
                date__lte=today,
            )
            .order_by("date", "created_at")
        )
        procurement_orders = list(
            StoreOrderRequest.objects.select_related("supplier")
            .prefetch_related("items__item")
            .filter(status__in=["APPROVED", "FULFILLED"])
            .order_by("created_at")
        )

        monthly_procurement_total = sum((transaction_value(tx) for tx in current_month_receipts), Decimal("0.00"))
        previous_month_procurement_total = sum(
            (transaction_value(tx) for tx in previous_month_receipts),
            Decimal("0.00"),
        )
        monthly_consumption_total = sum(
            (transaction_value(tx) for tx in current_month_issuances),
            Decimal("0.00"),
        )

        procurement_change_pct = None
        if previous_month_procurement_total:
            procurement_change_pct = round(
                float(
                    ((monthly_procurement_total - previous_month_procurement_total) / previous_month_procurement_total)
                    * Decimal("100")
                ),
                1,
            )
        elif monthly_procurement_total == Decimal("0.00"):
            procurement_change_pct = 0.0

        monthly_procurement = []
        month_starts = []
        cursor = current_month_start
        for _ in range(6):
            month_starts.append(cursor)
            cursor = _previous_month_start(cursor)
        month_starts.reverse()

        for month_start in month_starts:
            next_month_start = _next_month_start(month_start)
            month_receipts = StoreTransaction.objects.select_related("item").filter(
                transaction_type="RECEIPT",
                date__gte=month_start,
                date__lt=next_month_start,
            )
            total_value = sum((transaction_value(tx) for tx in month_receipts), Decimal("0.00"))
            monthly_procurement.append(
                {
                    "month": month_start.strftime("%b"),
                    "value": float(total_value),
                }
            )

        procurement_orders_total = sum(
            (self.calculate_order_total(order) for order in procurement_orders),
            Decimal("0.00"),
        )
        procurement_type_breakdown = []
        for procurement_type, label in (("LPO", "Local Purchase Orders"), ("LSO", "Local Supply Orders")):
            type_orders = [order for order in procurement_orders if order.procurement_type == procurement_type]
            procurement_type_breakdown.append(
                {
                    "type": procurement_type,
                    "label": label,
                    "count": len(type_orders),
                    "value": float(sum((self.calculate_order_total(order) for order in type_orders), Decimal("0.00"))),
                }
            )

        receiving_state_breakdown = []
        for receiving_state, label in (("PENDING", "Pending"), ("PARTIAL", "Partially Received"), ("RECEIVED", "Received")):
            receiving_state_breakdown.append(
                {
                    "state": receiving_state,
                    "label": label,
                    "count": StoreOrderRequest.objects.filter(receiving_state=receiving_state).count(),
                }
            )

        department_totals = {}
        top_consumed_items = {}
        for transaction in current_month_issuances:
            department = (transaction.department or "").strip() or "Unspecified"
            item_name = getattr(transaction.item, "name", "") or "Unknown Item"
            item_unit = getattr(transaction.item, "unit", "") or "pcs"
            quantity = _decimal_or_zero(transaction.quantity)
            value = transaction_value(transaction)

            department_totals[department] = department_totals.get(department, Decimal("0.00")) + value

            key = (item_name, department, item_unit)
            if key not in top_consumed_items:
                top_consumed_items[key] = {
                    "item": item_name,
                    "department": department,
                    "consumed": Decimal("0.00"),
                    "unit": item_unit,
                    "value": Decimal("0.00"),
                }
            top_consumed_items[key]["consumed"] += quantity
            top_consumed_items[key]["value"] += value

        department_usage = []
        for department, total_value in sorted(
            department_totals.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            pct = 0
            if monthly_consumption_total:
                pct = round(float((total_value / monthly_consumption_total) * Decimal("100")))
            department_usage.append(
                {
                    "dept": department,
                    "value": float(total_value),
                    "pct": int(pct),
                }
            )

        top_consumed = []
        for row in sorted(
            top_consumed_items.values(),
            key=lambda item: (-item["value"], -item["consumed"], item["item"], item["department"]),
        )[:10]:
            top_consumed.append(
                {
                    "item": row["item"],
                    "department": row["department"],
                    "consumed": float(row["consumed"]),
                    "unit": row["unit"],
                    "value": float(row["value"]),
                }
            )

        return {
            "report_month_label": current_month_start.strftime("%B %Y"),
            "total_inventory_value": float(inventory_value),
            "tracked_items": len(active_items),
            "low_stock_items": low_stock_items,
            "monthly_procurement_total": float(monthly_procurement_total),
            "monthly_consumption_total": float(monthly_consumption_total),
            "procurement_change_pct": procurement_change_pct,
            "monthly_procurement": monthly_procurement,
            "procurement_orders_total": float(procurement_orders_total),
            "procurement_type_breakdown": procurement_type_breakdown,
            "receiving_state_breakdown": receiving_state_breakdown,
            "department_usage": department_usage,
            "top_consumed_items": top_consumed,
        }

    def build_module_summary(self) -> dict[str, int]:
        return {
            "total_items": StoreItem.objects.filter(is_active=True).count(),
            "low_stock": StoreItem.objects.filter(
                is_active=True,
                current_stock__lte=F("reorder_level"),
            ).count(),
            "pending_orders": StoreOrderRequest.objects.filter(status="PENDING").count(),
        }
