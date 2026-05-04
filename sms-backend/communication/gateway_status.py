from __future__ import annotations

from .models import (
    CommunicationDispatchTask,
    EmailRecipient,
    GatewayStatus,
    PushDevice,
    PushNotificationLog,
    SmsMessage,
)
from .realtime import publish_gateway_status_event
from .services import (
    email_gateway_snapshot,
    now_ts,
    push_gateway_snapshot,
    sms_balance_placeholder,
    sms_gateway_snapshot,
    whatsapp_gateway_snapshot,
)

EMAIL_SUCCESS_STATUSES = {"Sent", "Delivered", "Opened", "Clicked"}
EMAIL_FAILED_STATUSES = {"Failed", "Bounced"}
MESSAGE_SUCCESS_STATUSES = {"Sent", "Delivered"}


def _isoformat_or_none(value):
    return value.isoformat() if value else None


def _latest_timestamp(rows, *field_names):
    values = []
    for row in rows:
        for field_name in field_names:
            value = getattr(row, field_name, None)
            if value:
                values.append(value)
    return max(values) if values else None


def _serialize_email_recipient_sample(row: EmailRecipient):
    activity_at = row.opened_at or row.delivered_at or row.sent_at
    return {
        "recipient": row.email,
        "status": row.status,
        "provider_id": row.provider_id,
        "subject": str(getattr(getattr(row, "campaign", None), "subject", "") or ""),
        "sent_at": _isoformat_or_none(row.sent_at),
        "delivered_at": _isoformat_or_none(row.delivered_at),
        "opened_at": _isoformat_or_none(row.opened_at),
        "activity_at": _isoformat_or_none(activity_at),
        "failure_reason": row.bounce_reason,
        "source_type": "EmailRecipient",
        "source_id": row.id,
    }


def _serialize_direct_email_task_sample(row: CommunicationDispatchTask):
    payload = row.payload or {}
    return {
        "recipient": row.recipient,
        "status": row.status,
        "provider_id": row.provider_id,
        "subject": str(payload.get("subject") or ""),
        "sent_at": _isoformat_or_none(row.processed_at if row.status == "Sent" else None),
        "delivered_at": None,
        "opened_at": None,
        "activity_at": _isoformat_or_none(row.processed_at),
        "failure_reason": row.last_error,
        "source_type": row.source_type or "DirectEmail",
        "source_id": row.id,
    }


def _serialize_sms_sample(row: SmsMessage):
    activity_at = row.delivered_at or row.sent_at or row.created_at
    return {
        "recipient": row.recipient_phone,
        "status": row.status,
        "provider_id": row.provider_id,
        "message_preview": str(row.message or "")[:120],
        "sent_at": _isoformat_or_none(row.sent_at),
        "delivered_at": _isoformat_or_none(row.delivered_at),
        "activity_at": _isoformat_or_none(activity_at),
        "failure_reason": row.failure_reason,
        "source_type": "SmsMessage",
        "source_id": row.id,
    }


def _serialize_push_sample(row: PushNotificationLog):
    activity_at = row.sent_at or row.created_at
    return {
        "recipient": getattr(getattr(row, "user", None), "username", "") or str(row.user_id),
        "status": row.status,
        "provider_id": row.provider_id,
        "title": row.title,
        "message_preview": str(row.body or "")[:120],
        "sent_at": _isoformat_or_none(row.sent_at),
        "activity_at": _isoformat_or_none(activity_at),
        "failure_reason": row.failure_reason,
        "source_type": "PushNotificationLog",
        "source_id": row.id,
    }


def _channel_queue_snapshot(channel: str):
    now = now_ts()
    rows = CommunicationDispatchTask.objects.filter(channel=channel)
    return {
        "queued_total": rows.filter(status="Queued").count(),
        "ready": rows.filter(status="Queued", available_at__lte=now).count(),
        "delayed": rows.filter(status="Queued", available_at__gt=now).count(),
        "retrying": rows.filter(status="Queued", attempts__gt=0).count(),
        "processing": rows.filter(status="Processing").count(),
        "sent": rows.filter(status="Sent").count(),
        "failed": rows.filter(status="Failed").count(),
    }


def _email_status_defaults():
    success_rows = list(
        EmailRecipient.objects.filter(status__in=EMAIL_SUCCESS_STATUSES)
        .select_related("campaign")
        .order_by("-opened_at", "-delivered_at", "-sent_at", "-id")[:5]
    )
    direct_success_rows = list(
        CommunicationDispatchTask.objects.filter(channel="EMAIL", source_type="DirectEmail", status="Sent")
        .order_by("-processed_at", "-id")[:5]
    )
    failure_rows = list(
        EmailRecipient.objects.filter(status__in=EMAIL_FAILED_STATUSES).order_by("-id")[:5]
    )
    direct_failure_rows = list(
        CommunicationDispatchTask.objects.filter(channel="EMAIL", source_type="DirectEmail", status="Failed")
        .order_by("-processed_at", "-id")[:5]
    )
    gateway = email_gateway_snapshot()
    recent_successes = [_serialize_email_recipient_sample(row) for row in success_rows]
    recent_successes.extend(_serialize_direct_email_task_sample(row) for row in direct_success_rows)
    recent_failures = [_serialize_email_recipient_sample(row) for row in failure_rows]
    recent_failures.extend(_serialize_direct_email_task_sample(row) for row in direct_failure_rows)
    recent_successes = sorted(
        recent_successes,
        key=lambda row: row.get("activity_at") or "",
        reverse=True,
    )[:5]
    recent_failures = sorted(
        recent_failures,
        key=lambda row: row.get("activity_at") or "",
        reverse=True,
    )[:5]
    return {
        "provider": gateway["provider"],
        "configured": gateway["configured"],
        "metadata": {
            "sender_email": gateway.get("sender_email", ""),
            "recent_successes": recent_successes,
            "recent_failures": recent_failures,
        },
        "balance_payload": {},
        "active_devices": 0,
        "last_success_at": max(
            filter(
                None,
                [
                    _latest_timestamp(success_rows, "opened_at", "delivered_at", "sent_at"),
                    _latest_timestamp(direct_success_rows, "processed_at"),
                ],
            ),
            default=None,
        ),
        "last_failure_at": max(
            filter(
                None,
                [
                    _latest_timestamp(failure_rows, "sent_at"),
                    _latest_timestamp(direct_failure_rows, "processed_at"),
                ],
            ),
            default=None,
        ),
    }


def _sms_status_defaults(*, include_balance: bool, existing: GatewayStatus | None = None):
    success_rows = list(
        SmsMessage.objects.filter(channel="SMS", status__in=MESSAGE_SUCCESS_STATUSES, is_active=True)
        .order_by("-delivered_at", "-sent_at", "-created_at", "-id")[:5]
    )
    failure_rows = list(
        SmsMessage.objects.filter(channel="SMS", status="Failed", is_active=True).order_by("-created_at", "-id")[:5]
    )
    gateway = sms_gateway_snapshot()
    return {
        "provider": gateway["provider"],
        "configured": gateway["configured"],
        "metadata": {
            "sender_id": gateway.get("sender_id", ""),
            "username": gateway.get("username", ""),
            "recent_successes": [_serialize_sms_sample(row) for row in success_rows[:5]],
            "recent_failures": [_serialize_sms_sample(row) for row in failure_rows[:5]],
        },
        "balance_payload": sms_balance_placeholder() if include_balance else (existing.balance_payload if existing else {}),
        "active_devices": 0,
        "last_success_at": _latest_timestamp(success_rows, "delivered_at", "sent_at", "created_at"),
        "last_failure_at": _latest_timestamp(failure_rows, "created_at", "sent_at"),
    }


def _whatsapp_status_defaults():
    success_rows = list(
        SmsMessage.objects.filter(channel="WhatsApp", status__in=MESSAGE_SUCCESS_STATUSES, is_active=True)
        .order_by("-delivered_at", "-sent_at", "-created_at", "-id")[:5]
    )
    failure_rows = list(
        SmsMessage.objects.filter(channel="WhatsApp", status="Failed", is_active=True).order_by("-created_at", "-id")[:5]
    )
    gateway = whatsapp_gateway_snapshot()
    return {
        "provider": gateway["provider"],
        "configured": gateway["configured"],
        "metadata": {
            "phone_id": gateway.get("phone_id", ""),
            "recent_successes": [_serialize_sms_sample(row) for row in success_rows[:5]],
            "recent_failures": [_serialize_sms_sample(row) for row in failure_rows[:5]],
        },
        "balance_payload": {},
        "active_devices": 0,
        "last_success_at": _latest_timestamp(success_rows, "delivered_at", "sent_at", "created_at"),
        "last_failure_at": _latest_timestamp(failure_rows, "created_at", "sent_at"),
    }


def _push_status_defaults():
    success_rows = list(
        PushNotificationLog.objects.filter(status__in=MESSAGE_SUCCESS_STATUSES).order_by("-sent_at", "-created_at", "-id")[:5]
    )
    failure_rows = list(
        PushNotificationLog.objects.filter(status="Failed").order_by("-created_at", "-id")[:5]
    )
    gateway = push_gateway_snapshot()
    return {
        "provider": gateway["provider"],
        "configured": gateway["configured"],
        "metadata": {
            "setting_key": gateway.get("setting_key", ""),
            "recent_successes": [_serialize_push_sample(row) for row in success_rows[:5]],
            "recent_failures": [_serialize_push_sample(row) for row in failure_rows[:5]],
        },
        "balance_payload": {},
        "active_devices": PushDevice.objects.filter(is_active=True).count(),
        "last_success_at": _latest_timestamp(success_rows, "sent_at", "created_at"),
        "last_failure_at": _latest_timestamp(failure_rows, "created_at", "sent_at"),
    }


def _snapshot_defaults_for_channel(channel: str, *, include_balance: bool, existing: GatewayStatus | None = None):
    providers = {
        "EMAIL": _email_status_defaults,
        "SMS": lambda: _sms_status_defaults(include_balance=include_balance, existing=existing),
        "WHATSAPP": _whatsapp_status_defaults,
        "PUSH": _push_status_defaults,
    }
    defaults = providers[channel]()
    queue = _channel_queue_snapshot(channel)
    defaults.update(
        {
            "queue_queued_total": queue["queued_total"],
            "queue_ready": queue["ready"],
            "queue_delayed": queue["delayed"],
            "queue_retrying": queue["retrying"],
            "queue_processing": queue["processing"],
            "queue_sent": queue["sent"],
            "queue_failed": queue["failed"],
            "last_synced_at": now_ts(),
        }
    )
    return defaults


def _gateway_change_signature(row: GatewayStatus | None):
    if row is None:
        return None
    return {
        "provider": row.provider,
        "configured": row.configured,
        "metadata": row.metadata or {},
        "queue_queued_total": row.queue_queued_total,
        "queue_ready": row.queue_ready,
        "queue_delayed": row.queue_delayed,
        "queue_retrying": row.queue_retrying,
        "queue_processing": row.queue_processing,
        "queue_sent": row.queue_sent,
        "queue_failed": row.queue_failed,
        "active_devices": row.active_devices,
        "balance_payload": row.balance_payload or {},
        "last_success_at": _isoformat_or_none(row.last_success_at),
        "last_failure_at": _isoformat_or_none(row.last_failure_at),
    }


def sync_gateway_statuses(*, channels: list[str] | None = None, include_balance: bool = False):
    normalized_channels = []
    for channel in channels or ["EMAIL", "SMS", "WHATSAPP", "PUSH"]:
        normalized = str(channel or "").strip().upper()
        if normalized and normalized not in normalized_channels:
            normalized_channels.append(normalized)

    existing_map = {
        row.channel: row
        for row in GatewayStatus.objects.filter(channel__in=normalized_channels)
    }
    rows = {}
    for channel in normalized_channels:
        existing = existing_map.get(channel)
        before = _gateway_change_signature(existing)
        defaults = _snapshot_defaults_for_channel(
            channel,
            include_balance=include_balance,
            existing=existing,
        )
        row, _created = GatewayStatus.objects.update_or_create(channel=channel, defaults=defaults)
        rows[channel] = row
        if before != _gateway_change_signature(row):
            publish_gateway_status_event(row)
    return rows


def ensure_gateway_statuses(*, channels: list[str] | None = None, include_balance: bool = False):
    normalized_channels = []
    for channel in channels or ["EMAIL", "SMS", "WHATSAPP", "PUSH"]:
        normalized = str(channel or "").strip().upper()
        if normalized and normalized not in normalized_channels:
            normalized_channels.append(normalized)

    existing = set(GatewayStatus.objects.filter(channel__in=normalized_channels).values_list("channel", flat=True))
    missing = [channel for channel in normalized_channels if channel not in existing]
    if missing:
        sync_gateway_statuses(channels=missing, include_balance=include_balance)
    return {row.channel: row for row in GatewayStatus.objects.filter(channel__in=normalized_channels)}
