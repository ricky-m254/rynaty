from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from django.db.models import Q
from django.utils import timezone

from .campaign_stats import ensure_campaign_stats
from .gateway_status import sync_gateway_statuses
from .models import (
    Announcement,
    CampaignStats,
    CommunicationAlertEvent,
    CommunicationDispatchTask,
    CommunicationMessage,
    EmailCampaign,
    EmailRecipient,
    GatewayStatus,
    MessageDelivery,
    MessageTemplate,
    PushDevice,
    PushNotificationLog,
    SmsMessage,
    UnifiedMessage,
)


_MIN_AWARE_DATETIME = datetime.min.replace(tzinfo=dt_timezone.utc)


def _isoformat_or_none(value):
    return value.isoformat() if value else None


def _preview(text: str, limit: int = 120) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def _latest_delivery_activity(deliveries, fallback):
    values = [fallback]
    for delivery in deliveries:
        for field_name in ("opened_at", "delivered_at", "sent_at", "processed_at", "last_attempt_at", "queued_at", "created_at"):
            value = getattr(delivery, field_name, None)
            if value:
                values.append(value)
    return max(values) if values else None


def _summarize_delivery_status(deliveries):
    status_totals = {
        "queued": 0,
        "processing": 0,
        "sent": 0,
        "delivered": 0,
        "opened": 0,
        "clicked": 0,
        "failed": 0,
        "bounced": 0,
    }
    by_channel = {}
    for delivery in deliveries:
        status_key = str(delivery.status or "").strip().lower()
        if status_key in status_totals:
            status_totals[status_key] += 1
        channel_key = str(delivery.channel or "").strip().lower()
        bucket = by_channel.setdefault(
            channel_key,
            {
                "total": 0,
                "queued": 0,
                "processing": 0,
                "sent": 0,
                "delivered": 0,
                "opened": 0,
                "clicked": 0,
                "failed": 0,
                "bounced": 0,
            },
        )
        bucket["total"] += 1
        if status_key in bucket:
            bucket[status_key] += 1
    return status_totals, by_channel


def _serialize_message_delivery(delivery):
    return {
        "id": delivery.id,
        "delivery_key": delivery.delivery_key,
        "channel": delivery.channel,
        "status": delivery.status,
        "source_type": delivery.source_type,
        "source_id": delivery.source_id,
        "recipient": delivery.recipient,
        "provider_id": delivery.provider_id,
        "attempts": delivery.attempts,
        "max_attempts": delivery.max_attempts,
        "queued_at": _isoformat_or_none(delivery.queued_at),
        "last_attempt_at": _isoformat_or_none(delivery.last_attempt_at),
        "sent_at": _isoformat_or_none(delivery.sent_at),
        "delivered_at": _isoformat_or_none(delivery.delivered_at),
        "opened_at": _isoformat_or_none(delivery.opened_at),
        "processed_at": _isoformat_or_none(delivery.processed_at),
        "failure_reason": delivery.failure_reason,
        "metadata": delivery.metadata or {},
    }


def _serialize_delivery_reference(delivery):
    return {
        "message_id": delivery.unified_message_id,
        "message_status": delivery.unified_message.status,
        "delivery_id": delivery.id,
        "delivery_status": delivery.status,
        "delivery_channel": delivery.channel,
        "delivery_attempts": delivery.attempts,
        "delivery_last_error": delivery.failure_reason,
    }


def build_unified_message_reference_lookup(*, source_type: str, source_ids: list[int]):
    normalized_ids = [int(source_id) for source_id in source_ids if source_id]
    if not normalized_ids:
        return {}
    rows = (
        UnifiedMessage.objects.select_related("campaign", "created_by")
        .prefetch_related("deliveries")
        .filter(source_type=source_type, source_id__in=normalized_ids)
        .order_by("-id")
    )
    lookup = {}
    for row in rows:
        if row.source_id in lookup:
            continue
        deliveries = list(row.deliveries.all())
        delivery_status, by_channel = _summarize_delivery_status(deliveries)
        lookup[row.source_id] = {
            "message_id": row.id,
            "message_status": row.status,
            "message_kind": row.kind,
            "message_channels": sorted(channel for channel in by_channel.keys() if channel),
            "delivery_summary": {
                "total": len(deliveries),
                **delivery_status,
            },
        }
    return lookup


def build_delivery_reference_lookup(*, source_type: str, source_ids: list[int]):
    normalized_ids = [int(source_id) for source_id in source_ids if source_id]
    if not normalized_ids:
        return {}
    rows = (
        MessageDelivery.objects.select_related("unified_message")
        .filter(source_type=source_type, source_id__in=normalized_ids)
        .order_by("-id")
    )
    lookup = {}
    for row in rows:
        if row.source_id in lookup:
            continue
        lookup[row.source_id] = _serialize_delivery_reference(row)
    return lookup


def _serialize_unified_message(message: UnifiedMessage, *, include_deliveries: bool):
    deliveries = list(message.deliveries.all().order_by("-created_at", "-id"))
    latest_activity_at = _latest_delivery_activity(deliveries, message.updated_at or message.created_at)
    status_totals, by_channel = _summarize_delivery_status(deliveries)
    payload = {
        "id": message.id,
        "message_key": message.message_key,
        "kind": message.kind,
        "status": message.status,
        "source_type": message.source_type,
        "source_id": message.source_id,
        "campaign_id": message.campaign_id,
        "campaign_title": message.campaign.title if message.campaign_id else "",
        "title": message.title,
        "subject": message.subject,
        "body_preview": _preview(message.body),
        "metadata": message.metadata or {},
        "created_by_id": message.created_by_id,
        "created_by_name": getattr(message.created_by, "username", ""),
        "created_at": _isoformat_or_none(message.created_at),
        "updated_at": _isoformat_or_none(message.updated_at),
        "latest_activity_at": _isoformat_or_none(latest_activity_at),
        "delivery_count": len(deliveries),
        "delivery_status": status_totals,
        "delivery_channels": by_channel,
        "channels": sorted(channel for channel in by_channel.keys() if channel),
    }
    if include_deliveries:
        payload["deliveries"] = [_serialize_message_delivery(delivery) for delivery in deliveries]
    return payload


def build_unified_message_feed(
    *,
    limit: int = 50,
    status: str | None = None,
    kind: str | None = None,
    channel: str | None = None,
    source_type: str | None = None,
):
    normalized_limit = max(1, min(int(limit or 50), 200))
    queryset = UnifiedMessage.objects.select_related("campaign", "created_by").prefetch_related("deliveries").all().order_by("-created_at", "-id")
    if status:
        queryset = queryset.filter(status=status)
    if kind:
        queryset = queryset.filter(kind=kind)
    if source_type:
        queryset = queryset.filter(source_type=source_type)
    if channel:
        queryset = queryset.filter(deliveries__channel=channel).distinct()
    return [_serialize_unified_message(message, include_deliveries=False) for message in queryset[:normalized_limit]]


def _activity_channel_for_unified_message(message: UnifiedMessage, deliveries):
    channels = []
    for delivery in deliveries:
        normalized = str(delivery.channel or "").strip().upper()
        if normalized and normalized not in channels:
            channels.append(normalized)
    if channels:
        return channels[0]

    metadata_channel = str((message.metadata or {}).get("channel") or "").strip().upper()
    if metadata_channel:
        return "WHATSAPP" if metadata_channel == "WHATSAPP" else metadata_channel

    return {
        "EmailCampaign": "EMAIL",
        "DirectEmail": "EMAIL",
        "DirectEmailBatch": "EMAIL",
        "SmsBatch": "SMS",
        "SmsMessage": "SMS",
        "WhatsAppBatch": "WHATSAPP",
        "PushBatch": "PUSH",
        "PushNotificationLog": "PUSH",
    }.get(str(message.source_type or "").strip(), "MESSAGE")


def _serialize_communication_message_activity_item(message: CommunicationMessage):
    reference_at = message.sent_at or message.created_at
    preview = _preview(message.content)
    return {
        "id": f"chat-{message.id}",
        "activity_id": message.id,
        "item_type": "conversation_message",
        "source_type": "CommunicationMessage",
        "source_id": message.id,
        "conversation_id": message.conversation_id,
        "content": message.content,
        "description": preview,
        "message": preview,
        "status": message.delivery_status or "Sent",
        "delivery_status": message.delivery_status or "Sent",
        "sender_name": getattr(message.sender, "username", ""),
        "channel": "MESSAGE",
        "channel_type": "MESSAGE",
        "created_at": _isoformat_or_none(reference_at),
        "sent_at": _isoformat_or_none(reference_at),
        "_reference_at": reference_at,
        "_sort_id": message.id,
    }


def _serialize_unified_message_activity_item(message: UnifiedMessage):
    deliveries = list(message.deliveries.all())
    reference_at = _latest_delivery_activity(deliveries, message.updated_at or message.created_at)
    title = message.subject or message.title or _preview(message.body) or "Communication activity"
    preview = _preview(message.body)
    channel = _activity_channel_for_unified_message(message, deliveries)
    payload = {
        "id": f"unified-{message.id}",
        "activity_id": message.id,
        "item_type": "unified_message",
        "source_type": message.source_type,
        "source_id": message.source_id,
        "message_id": message.id,
        "title": title,
        "subject": title,
        "status": message.status or "Queued",
        "channel": channel,
        "channel_type": channel,
        "created_at": _isoformat_or_none(reference_at),
        "sent_at": _isoformat_or_none(reference_at),
        "created_by_name": getattr(message.created_by, "username", ""),
        "delivery_count": len(deliveries),
        "_reference_at": reference_at,
        "_sort_id": message.id,
    }
    if preview and preview != title:
        payload["message"] = preview
    return payload


def _serialize_announcement_activity_item(row: Announcement):
    reference_at = row.publish_at or row.created_at
    payload = {
        "id": f"announcement-{row.id}",
        "activity_id": row.id,
        "item_type": "announcement",
        "source_type": "Announcement",
        "source_id": row.id,
        "title": row.title,
        "subject": row.title,
        "status": "Sent",
        "channel": "ANNOUNCEMENT",
        "channel_type": "ANNOUNCEMENT",
        "priority": row.priority,
        "is_pinned": row.is_pinned,
        "created_by_name": getattr(row.created_by, "username", ""),
        "created_at": _isoformat_or_none(reference_at),
        "sent_at": _isoformat_or_none(reference_at),
        "_reference_at": reference_at,
        "_sort_id": row.id,
    }
    preview = _preview(row.body)
    if preview:
        payload["message"] = preview
    return payload


def build_communication_activity_feed(
    *,
    conversation_messages,
    limit: int = 20,
    include_announcements: bool = True,
    descending: bool = True,
):
    normalized_limit = max(1, min(int(limit or 20), 100))
    rows = [
        _serialize_communication_message_activity_item(row)
        for row in list(conversation_messages)[:normalized_limit]
    ]

    unified_rows = (
        UnifiedMessage.objects.select_related("campaign", "created_by")
        .prefetch_related("deliveries")
        .all()
        .order_by("-updated_at", "-id")[:normalized_limit]
    )
    rows.extend(_serialize_unified_message_activity_item(row) for row in unified_rows)

    if include_announcements:
        now = timezone.now()
        announcement_rows = (
            Announcement.objects.filter(is_active=True, publish_at__lte=now)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .order_by("-publish_at", "-id")[:normalized_limit]
        )
        rows.extend(_serialize_announcement_activity_item(row) for row in announcement_rows)

    rows.sort(
        key=lambda row: (row.get("_reference_at") or _MIN_AWARE_DATETIME, row.get("_sort_id", 0)),
        reverse=descending,
    )

    payload = []
    for row in rows[:normalized_limit]:
        item = dict(row)
        item.pop("_reference_at", None)
        item.pop("_sort_id", None)
        payload.append(item)
    return payload


def build_unified_message_detail(message_id: int):
    message = (
        UnifiedMessage.objects.select_related("campaign", "created_by")
        .prefetch_related("deliveries")
        .filter(id=message_id)
        .first()
    )
    if message is None:
        return None
    return _serialize_unified_message(message, include_deliveries=True)


def _history_row_key(channel: str, source_type: str, source_id, recipient: str):
    return (channel, source_type, source_id or "", recipient or "")


def _build_unified_delivery_history_rows(*, limit: int, channel: str | None = None, status: str | None = None):
    queryset = MessageDelivery.objects.select_related("unified_message", "unified_message__campaign").all().order_by("-created_at", "-id")
    if channel:
        queryset = queryset.filter(channel=channel)
    if status:
        queryset = queryset.filter(status=status)

    rows = []
    for delivery in queryset[:limit]:
        unified_message = delivery.unified_message
        activity_at = delivery.opened_at or delivery.delivered_at or delivery.sent_at or delivery.processed_at or delivery.last_attempt_at or delivery.queued_at or delivery.created_at
        rows.append(
            {
                "channel": delivery.channel,
                "source_type": delivery.source_type or unified_message.source_type,
                "source_id": delivery.source_id,
                "status": delivery.status,
                "recipient": delivery.recipient,
                "provider_id": delivery.provider_id,
                "campaign_id": unified_message.campaign_id,
                "campaign_title": unified_message.title if unified_message.campaign_id else "",
                "subject": unified_message.subject or unified_message.title,
                "message_preview": _preview(unified_message.body),
                "failure_reason": delivery.failure_reason,
                "sent_at": _isoformat_or_none(delivery.sent_at),
                "delivered_at": _isoformat_or_none(delivery.delivered_at),
                "activity_at": _isoformat_or_none(activity_at),
                "_activity_at": activity_at,
                "_key": _history_row_key(delivery.channel, delivery.source_type or unified_message.source_type, delivery.source_id, delivery.recipient),
            }
        )
    return rows


def build_delivery_history(*, limit: int = 50, channel: str | None = None, status: str | None = None):
    normalized_limit = max(1, min(int(limit or 50), 200))
    normalized_channel = str(channel or "").strip().upper()
    normalized_status = str(status or "").strip()
    rows = _build_unified_delivery_history_rows(limit=normalized_limit, channel=normalized_channel or None, status=normalized_status or None)
    seen_keys = {row["_key"] for row in rows}

    if not normalized_channel or normalized_channel == "EMAIL":
        email_rows = EmailRecipient.objects.select_related("campaign").all().order_by("-id")
        if normalized_status:
            email_rows = email_rows.filter(status=normalized_status)
        for row in email_rows[:normalized_limit]:
            activity_at = row.opened_at or row.delivered_at or row.sent_at or row.campaign.sent_at or row.campaign.created_at
            key = _history_row_key("EMAIL", "EmailRecipient", row.id, row.email)
            if key not in seen_keys:
                seen_keys.add(key)
                rows.append(
                    {
                        "channel": "EMAIL",
                        "source_type": "EmailRecipient",
                        "source_id": row.id,
                        "status": row.status,
                        "recipient": row.email,
                        "provider_id": row.provider_id,
                        "campaign_id": row.campaign_id,
                        "campaign_title": row.campaign.title,
                        "subject": row.campaign.subject,
                        "message_preview": _preview(row.campaign.body_text or row.campaign.body_html),
                        "failure_reason": row.bounce_reason,
                        "sent_at": _isoformat_or_none(row.sent_at),
                        "delivered_at": _isoformat_or_none(row.delivered_at),
                        "activity_at": _isoformat_or_none(activity_at),
                        "_activity_at": activity_at,
                        "_key": key,
                    }
                )

        direct_email_rows = CommunicationDispatchTask.objects.filter(source_type="DirectEmail", channel="EMAIL").order_by("-id")
        if normalized_status:
            direct_email_rows = direct_email_rows.filter(status=normalized_status)
        for task in direct_email_rows[:normalized_limit]:
            payload = task.payload or {}
            activity_at = task.processed_at or task.claimed_at or task.available_at or task.created_at
            key = _history_row_key("EMAIL", "DirectEmail", task.id, task.recipient)
            if key not in seen_keys:
                seen_keys.add(key)
                rows.append(
                    {
                        "channel": "EMAIL",
                        "source_type": "DirectEmail",
                        "source_id": task.id,
                        "status": task.status,
                        "recipient": task.recipient,
                        "provider_id": task.provider_id,
                        "campaign_id": None,
                        "campaign_title": "",
                        "subject": str(payload.get("subject") or ""),
                        "message_preview": _preview(payload.get("body") or ""),
                        "failure_reason": task.last_error,
                        "sent_at": _isoformat_or_none(task.processed_at if task.status == "Sent" else None),
                        "delivered_at": None,
                        "activity_at": _isoformat_or_none(activity_at),
                        "_activity_at": activity_at,
                        "_key": key,
                    }
                )

    if not normalized_channel or normalized_channel in {"SMS", "WHATSAPP"}:
        sms_rows = SmsMessage.objects.filter(is_active=True).all().order_by("-created_at", "-id")
        if normalized_channel == "SMS":
            sms_rows = sms_rows.filter(channel="SMS")
        elif normalized_channel == "WHATSAPP":
            sms_rows = sms_rows.filter(channel="WhatsApp")
        if normalized_status:
            sms_rows = sms_rows.filter(status=normalized_status)
        for row in sms_rows[:normalized_limit]:
            activity_at = row.delivered_at or row.sent_at or row.created_at
            channel_key = "WHATSAPP" if row.channel == "WhatsApp" else "SMS"
            key = _history_row_key(channel_key, "SmsMessage", row.id, row.recipient_phone)
            if key not in seen_keys:
                seen_keys.add(key)
                rows.append(
                    {
                        "channel": channel_key,
                        "source_type": "SmsMessage",
                        "source_id": row.id,
                        "status": row.status,
                        "recipient": row.recipient_phone,
                        "provider_id": row.provider_id,
                        "campaign_id": None,
                        "campaign_title": "",
                        "subject": "",
                        "message_preview": _preview(row.message),
                        "failure_reason": row.failure_reason,
                        "sent_at": _isoformat_or_none(row.sent_at),
                        "delivered_at": _isoformat_or_none(row.delivered_at),
                        "activity_at": _isoformat_or_none(activity_at),
                        "_activity_at": activity_at,
                        "_key": key,
                    }
                )

    if not normalized_channel or normalized_channel == "PUSH":
        push_rows = PushNotificationLog.objects.select_related("user").all().order_by("-created_at", "-id")
        if normalized_status:
            push_rows = push_rows.filter(status=normalized_status)
        for row in push_rows[:normalized_limit]:
            activity_at = row.sent_at or row.created_at
            recipient = getattr(row.user, "username", "") or str(row.user_id)
            key = _history_row_key("PUSH", "PushNotificationLog", row.id, recipient)
            if key not in seen_keys:
                seen_keys.add(key)
                rows.append(
                    {
                        "channel": "PUSH",
                        "source_type": "PushNotificationLog",
                        "source_id": row.id,
                        "status": row.status,
                        "recipient": recipient,
                        "provider_id": row.provider_id,
                        "campaign_id": None,
                        "campaign_title": "",
                        "subject": row.title,
                        "message_preview": _preview(row.body),
                        "failure_reason": row.failure_reason,
                        "sent_at": _isoformat_or_none(row.sent_at),
                        "delivered_at": None,
                        "activity_at": _isoformat_or_none(activity_at),
                        "_activity_at": activity_at,
                        "_key": key,
                    }
                )

    rows.sort(
        key=lambda row: (
            row.get("_activity_at") is not None,
            row.get("_activity_at"),
            row.get("source_id") or 0,
        ),
        reverse=True,
    )
    trimmed = rows[:normalized_limit]
    for row in trimmed:
        row.pop("_key", None)
        row.pop("_activity_at", None)
    return trimmed


def build_campaign_performance(*, limit: int = 20):
    normalized_limit = max(1, min(int(limit or 20), 100))
    campaigns = EmailCampaign.objects.all().order_by("-created_at", "-id")[:normalized_limit]
    rows = []
    for campaign in campaigns:
        stats = CampaignStats.objects.select_related("unified_message").filter(campaign=campaign).first() or ensure_campaign_stats(campaign)
        rows.append(
            {
                "campaign_id": campaign.id,
                "message_id": stats.unified_message_id,
                "message_status": getattr(stats.unified_message, "status", ""),
                "title": campaign.title,
                "subject": campaign.subject,
                "status": campaign.status,
                "scheduled_at": _isoformat_or_none(campaign.scheduled_at),
                "sent_at": _isoformat_or_none(campaign.sent_at),
                "total_recipients": stats.total_recipients,
                "queued_recipients": stats.queued_recipients,
                "successful_recipients": stats.successful_recipients,
                "delivered_recipients": stats.delivered_recipients,
                "opened_recipients": stats.opened_recipients,
                "clicked_recipients": stats.clicked_recipients,
                "bounced_recipients": stats.bounced_recipients,
                "failed_recipients": stats.failed_recipients,
                "open_events": stats.open_events,
                "click_events": stats.click_events,
                "delivery_rate": float(stats.delivery_rate),
                "open_rate": float(stats.open_rate),
                "click_rate": float(stats.click_rate),
                "last_event_at": _isoformat_or_none(stats.last_event_at),
                "last_synced_at": _isoformat_or_none(stats.last_synced_at),
            }
        )
    return rows


def _latest_timestamp(rows, *field_names):
    values = []
    for row in rows:
        for field_name in field_names:
            value = getattr(row, field_name, None)
            if value:
                values.append(value)
    return max(values) if values else None


def _serialize_gateway_status(row: GatewayStatus):
    payload = {
        "provider": row.provider,
        "configured": row.configured,
        "queue": {
            "queued_total": row.queue_queued_total,
            "ready": row.queue_ready,
            "delayed": row.queue_delayed,
            "retrying": row.queue_retrying,
            "processing": row.queue_processing,
            "sent": row.queue_sent,
            "failed": row.queue_failed,
        },
        "last_success_at": _isoformat_or_none(row.last_success_at),
        "last_failure_at": _isoformat_or_none(row.last_failure_at),
        "last_synced_at": _isoformat_or_none(row.last_synced_at),
    }
    payload.update(row.metadata or {})
    if row.balance_payload:
        payload["balance"] = row.balance_payload
    if row.active_devices:
        payload["active_devices"] = row.active_devices
    return payload


def build_gateway_health_payload(*, include_balance: bool = True):
    rows = sync_gateway_statuses(include_balance=include_balance)
    return {
        "email": _serialize_gateway_status(rows["EMAIL"]),
        "sms": _serialize_gateway_status(rows["SMS"]),
        "whatsapp": _serialize_gateway_status(rows["WHATSAPP"]),
        "push": _serialize_gateway_status(rows["PUSH"]),
    }


def _announcement_priority_rank(value: str) -> int:
    ranks = {
        "Urgent": 0,
        "Important": 1,
        "Normal": 2,
    }
    return ranks.get(str(value or "").strip(), 3)


def _serialize_announcement_alert_item(row: Announcement):
    return {
        "id": row.id,
        "item_type": "announcement",
        "title": row.title,
        "message": row.body,
        "priority": row.priority,
        "audience_type": row.audience_type,
        "is_pinned": row.is_pinned,
        "publish_at": _isoformat_or_none(row.publish_at),
        "expires_at": _isoformat_or_none(row.expires_at),
        "notify_email": row.notify_email,
        "notify_sms": row.notify_sms,
        "notify_push": row.notify_push,
    }


def _serialize_alert_event_feed_item(row: CommunicationAlertEvent):
    metadata = row.metadata or {}
    return {
        "id": row.id,
        "item_type": "alert",
        "rule_id": row.rule_id,
        "rule_name": row.rule.name,
        "rule_type": row.rule.rule_type,
        "title": row.title,
        "message": row.details,
        "severity": row.severity,
        "status": row.status,
        "channel": row.channel,
        "last_triggered_at": _isoformat_or_none(row.last_triggered_at),
        "acknowledged_at": _isoformat_or_none(row.acknowledged_at),
        "resolved_at": _isoformat_or_none(row.resolved_at),
        "metadata": metadata,
    }


def _build_operational_reminders(*, limit: int):
    now = timezone.now()
    reminders = []

    scheduled_campaigns = list(
        EmailCampaign.objects.filter(
            is_active=True,
            status="Scheduled",
            scheduled_at__isnull=False,
            scheduled_at__gt=now,
        )
        .order_by("scheduled_at", "id")[:5]
    )
    if scheduled_campaigns:
        first = scheduled_campaigns[0]
        reminders.append(
            {
                "id": "scheduled-campaigns",
                "item_type": "reminder",
                "category": "campaign",
                "severity": "info",
                "title": f"{len(scheduled_campaigns)} scheduled campaign(s) pending dispatch",
                "message": f"The next scheduled campaign is '{first.title}' at {_isoformat_or_none(first.scheduled_at)}.",
                "action_path": "/modules/communication/email",
                "reference_at": _isoformat_or_none(first.scheduled_at),
            }
        )

    draft_campaign_count = EmailCampaign.objects.filter(is_active=True, status="Draft").count()
    if draft_campaign_count:
        reminders.append(
            {
                "id": "draft-campaigns",
                "item_type": "reminder",
                "category": "campaign",
                "severity": "warning",
                "title": f"{draft_campaign_count} draft campaign(s) need review",
                "message": "Review unfinished communication drafts and either schedule or archive them.",
                "action_path": "/modules/communication/email",
                "reference_at": None,
            }
        )

    template_count = MessageTemplate.objects.filter(is_active=True).count()
    if template_count == 0:
        reminders.append(
            {
                "id": "missing-templates",
                "item_type": "reminder",
                "category": "template",
                "severity": "warning",
                "title": "No active communication templates configured",
                "message": "Create baseline templates for reminders, alerts, and parent notices before bulk sending.",
                "action_path": "/modules/communication/templates",
                "reference_at": None,
            }
        )

    push_devices = PushDevice.objects.filter(is_active=True).count()
    if push_devices == 0:
        reminders.append(
            {
                "id": "no-push-devices",
                "item_type": "reminder",
                "category": "push",
                "severity": "info",
                "title": "No active push devices registered",
                "message": "Push delivery is configured only after users register at least one active device.",
                "action_path": "/modules/communication/settings",
                "reference_at": None,
            }
        )

    return reminders[: max(int(limit or 0), 0)]


def build_alerts_center_payload(*, alert_limit: int = 20, announcement_limit: int = 20, reminder_limit: int = 10):
    normalized_alert_limit = max(1, min(int(alert_limit or 20), 100))
    normalized_announcement_limit = max(1, min(int(announcement_limit or 20), 100))
    normalized_reminder_limit = max(1, min(int(reminder_limit or 10), 50))
    now = timezone.now()

    announcement_rows = list(
        Announcement.objects.filter(is_active=True, publish_at__lte=now)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    )
    announcement_rows.sort(
        key=lambda row: (
            0 if row.is_pinned else 1,
            _announcement_priority_rank(row.priority),
            -(row.publish_at.timestamp() if row.publish_at else 0),
            -row.id,
        )
    )
    announcement_payload = [
        _serialize_announcement_alert_item(row)
        for row in announcement_rows[:normalized_announcement_limit]
    ]

    alert_rows = list(
        CommunicationAlertEvent.objects.select_related("rule")
        .exclude(status=CommunicationAlertEvent.STATUS_RESOLVED)
        .order_by("-last_triggered_at", "-id")[:normalized_alert_limit]
    )
    alert_payload = [_serialize_alert_event_feed_item(row) for row in alert_rows]
    reminder_payload = _build_operational_reminders(limit=normalized_reminder_limit)

    return {
        "summary": {
            "announcements": len(announcement_payload),
            "system_alerts": len(alert_payload),
            "reminders": len(reminder_payload),
            "critical_alerts": len([row for row in alert_payload if row["severity"] == "CRITICAL"]),
            "total": len(announcement_payload) + len(alert_payload) + len(reminder_payload),
        },
        "announcements": announcement_payload,
        "alerts": alert_payload,
        "reminders": reminder_payload,
    }
