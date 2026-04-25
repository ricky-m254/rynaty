from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

from communication.models import Notification, NotificationPreference

from .models import TenantSettings, UserModuleAssignment


DEFAULT_FINANCE_OPERATIONS = {
    "mpesa_reconciliation_minutes": 15,
    "payment_notification_events": {
        "mpesa_received": True,
        "mpesa_failed": False,
        "stripe_received": False,
        "manual_payment_recorded": False,
    },
}


def _student_label(student) -> str:
    if not student:
        return "Unknown Student"
    full_name = f"{getattr(student, 'first_name', '')} {getattr(student, 'last_name', '')}".strip()
    return full_name or getattr(student, "admission_number", "") or "Unknown Student"


def get_finance_operations_settings() -> dict:
    merged = deepcopy(DEFAULT_FINANCE_OPERATIONS)
    row = TenantSettings.objects.filter(key="finance.operations").first()
    raw = row.value if row and isinstance(row.value, dict) else {}

    try:
        minutes = int(raw.get("mpesa_reconciliation_minutes", merged["mpesa_reconciliation_minutes"]))
        merged["mpesa_reconciliation_minutes"] = max(1, minutes)
    except (TypeError, ValueError):
        pass

    event_map = raw.get("payment_notification_events")
    if isinstance(event_map, dict):
        for event_key, default_enabled in merged["payment_notification_events"].items():
            if event_key in event_map:
                merged["payment_notification_events"][event_key] = bool(event_map[event_key])
            else:
                merged["payment_notification_events"][event_key] = default_enabled

    return merged


def finance_payment_event_enabled(event_key: str) -> bool:
    return bool(get_finance_operations_settings()["payment_notification_events"].get(event_key, False))


def finance_notification_recipient_ids() -> list[int]:
    user_ids = list(
        UserModuleAssignment.objects.filter(
            module__key="FINANCE",
            is_active=True,
            user__is_active=True,
        )
        .values_list("user_id", flat=True)
        .distinct()
    )
    if not user_ids:
        return []

    muted_ids = set(
        NotificationPreference.objects.filter(
            user_id__in=user_ids,
            notification_type="Financial",
            channel_in_app=False,
        ).values_list("user_id", flat=True)
    )
    return [user_id for user_id in user_ids if user_id not in muted_ids]


def notify_finance_payment_event(
    event_key: str,
    *,
    title: str,
    message: str,
    priority: str = "Important",
    action_url: str = "/dashboard/finance/payments/",
) -> int:
    if not finance_payment_event_enabled(event_key):
        return 0

    recipient_ids = finance_notification_recipient_ids()
    if not recipient_ids:
        return 0

    Notification.objects.bulk_create(
        [
            Notification(
                recipient_id=user_id,
                notification_type="Financial",
                title=title,
                message=message,
                priority=priority,
                action_url=action_url,
                delivery_status="Sent",
            )
            for user_id in recipient_ids
        ]
    )
    return len(recipient_ids)


def notify_finance_mpesa_failure(tx, *, result_code=None, result_desc="", checkout_id="") -> int:
    student_name = _student_label(getattr(tx, "student", None))
    amount_value = Decimal(str(getattr(tx, "amount", Decimal("0.00")) or Decimal("0.00")))
    checkout_ref = checkout_id or getattr(tx, "external_id", "") or "unknown-checkout"
    suffix = f"Reason: {result_desc}." if result_desc else "Reason: Await the latest Daraja retry detail."
    if result_code not in (None, ""):
        suffix = f"Code: {result_code}. {suffix}"

    return notify_finance_payment_event(
        "mpesa_failed",
        title="M-Pesa Payment Failed",
        message=(
            f"M-Pesa payment attempt for {student_name} did not complete. "
            f"Amount: KES {amount_value:,.2f}. Checkout: {checkout_ref}. {suffix}"
        ),
    )
