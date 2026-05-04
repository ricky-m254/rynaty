from __future__ import annotations

import uuid

from .models import EmailCampaign, MessageDelivery, UnifiedMessage
from .services import now_ts

DELIVERY_SUCCESS_STATUSES = {"Sent", "Delivered", "Opened", "Clicked"}
DELIVERY_FAILURE_STATUSES = {"Failed", "Bounced"}


def _isoformat_or_none(value):
    return value.isoformat() if value else None


def _compact_metadata(payload: dict | None) -> dict:
    normalized = {}
    for key, value in (payload or {}).items():
        if value in ("", None, [], {}):
            continue
        normalized[key] = value
    return normalized


def _upsert_unified_message(
    *,
    message_key: str,
    kind: str,
    source_type: str,
    source_id: int | None = None,
    campaign: EmailCampaign | None = None,
    title: str = "",
    subject: str = "",
    body: str = "",
    created_by=None,
    metadata: dict | None = None,
):
    defaults = {
        "kind": kind,
        "status": "Queued",
        "source_type": source_type,
        "source_id": source_id,
        "campaign": campaign,
        "title": title,
        "subject": subject,
        "body": body,
        "metadata": _compact_metadata(metadata),
        "created_by": created_by,
    }
    message, created = UnifiedMessage.objects.get_or_create(message_key=message_key, defaults=defaults)
    if created:
        return message

    update_fields = []
    for field_name, value in defaults.items():
        current_value = getattr(message, field_name)
        if field_name == "metadata":
            merged = {**current_value, **value}
            if merged != current_value:
                message.metadata = merged
                update_fields.append("metadata")
            continue
        if value and current_value != value:
            setattr(message, field_name, value)
            update_fields.append(field_name)
    if update_fields:
        message.save(update_fields=update_fields)
    return message


def create_ad_hoc_unified_message(
    *,
    kind: str,
    source_type: str,
    title: str = "",
    subject: str = "",
    body: str = "",
    created_by=None,
    metadata: dict | None = None,
):
    return UnifiedMessage.objects.create(
        message_key=f"{source_type.lower()}:{uuid.uuid4().hex}",
        kind=kind,
        status="Queued",
        source_type=source_type,
        title=title,
        subject=subject,
        body=body,
        metadata=_compact_metadata(metadata),
        created_by=created_by,
    )


def ensure_unified_message(
    *,
    message_key: str,
    kind: str,
    source_type: str,
    source_id: int | None = None,
    campaign: EmailCampaign | None = None,
    title: str = "",
    subject: str = "",
    body: str = "",
    created_by=None,
    metadata: dict | None = None,
):
    return _upsert_unified_message(
        message_key=message_key,
        kind=kind,
        source_type=source_type,
        source_id=source_id,
        campaign=campaign,
        title=title,
        subject=subject,
        body=body,
        created_by=created_by,
        metadata=metadata,
    )


def ensure_campaign_unified_message(campaign: EmailCampaign):
    return _upsert_unified_message(
        message_key=f"email-campaign:{campaign.id}",
        kind="CAMPAIGN",
        source_type="EmailCampaign",
        source_id=campaign.id,
        campaign=campaign,
        title=campaign.title,
        subject=campaign.subject,
        body=campaign.body_text or campaign.body_html,
        created_by=campaign.created_by,
        metadata={
            "scheduled_at": _isoformat_or_none(campaign.scheduled_at),
            "sender_email": campaign.sender_email,
            "sender_name": campaign.sender_name,
            "reply_to": campaign.reply_to,
        },
    )


def ensure_delivery(
    *,
    unified_message: UnifiedMessage,
    delivery_key: str,
    channel: str,
    recipient: str,
    source_type: str = "",
    source_id: int | None = None,
    provider_id: str = "",
    metadata: dict | None = None,
    max_attempts: int = 3,
):
    defaults = {
        "unified_message": unified_message,
        "channel": channel,
        "status": "Queued",
        "source_type": source_type,
        "source_id": source_id,
        "recipient": recipient,
        "provider_id": provider_id,
        "max_attempts": max_attempts,
        "metadata": _compact_metadata(metadata),
    }
    delivery, created = MessageDelivery.objects.get_or_create(delivery_key=delivery_key, defaults=defaults)
    if created:
        return delivery, created

    update_fields = []
    if delivery.unified_message_id != unified_message.id:
        delivery.unified_message = unified_message
        update_fields.append("unified_message")
    for field_name in ("channel", "source_type", "source_id", "recipient", "provider_id", "max_attempts"):
        value = defaults[field_name]
        if value not in ("", None) and getattr(delivery, field_name) != value:
            setattr(delivery, field_name, value)
            update_fields.append(field_name)
    merged_metadata = {**delivery.metadata, **defaults["metadata"]}
    if merged_metadata != delivery.metadata:
        delivery.metadata = merged_metadata
        update_fields.append("metadata")
    if update_fields:
        delivery.save(update_fields=update_fields)
    return delivery, created


def attach_task_delivery(task, delivery: MessageDelivery):
    update_fields = []
    if task.delivery_id != delivery.id:
        task.delivery = delivery
        update_fields.append("delivery")
    if task.source_type == "DirectEmail" and task.source_id is None:
        task.source_id = task.id
        update_fields.append("source_id")
    if update_fields:
        task.save(update_fields=update_fields)

    delivery_updates = []
    if delivery.source_type != task.source_type and task.source_type:
        delivery.source_type = task.source_type
        delivery_updates.append("source_type")
    if task.source_id and delivery.source_id != task.source_id:
        delivery.source_id = task.source_id
        delivery_updates.append("source_id")
    if delivery_updates:
        delivery.save(update_fields=delivery_updates)


def sync_unified_message_status(unified_message: UnifiedMessage):
    deliveries = unified_message.deliveries.all()
    if not deliveries.exists():
        next_status = "Queued"
    elif deliveries.filter(status="Processing").exists():
        next_status = "Sending"
    elif deliveries.filter(status="Queued").exists():
        next_status = "Sending" if deliveries.exclude(status="Queued").exists() else "Queued"
    else:
        success_count = deliveries.filter(status__in=DELIVERY_SUCCESS_STATUSES).count()
        failure_count = deliveries.filter(status__in=DELIVERY_FAILURE_STATUSES).count()
        if success_count and failure_count:
            next_status = "Partial"
        elif success_count:
            next_status = "Sent"
        elif failure_count:
            next_status = "Failed"
        else:
            next_status = "Queued"
    if unified_message.status != next_status:
        unified_message.status = next_status
        unified_message.save(update_fields=["status"])


def mark_delivery_processing(task, *, when=None):
    if not task.delivery_id:
        return
    when = when or now_ts()
    delivery = task.delivery
    delivery.status = "Processing"
    delivery.attempts = task.attempts
    delivery.max_attempts = task.max_attempts
    delivery.last_attempt_at = when
    delivery.save(update_fields=["status", "attempts", "max_attempts", "last_attempt_at"])
    sync_unified_message_status(delivery.unified_message)


def mark_delivery_retry(task, error_message: str, *, when=None):
    if not task.delivery_id:
        return
    when = when or now_ts()
    delivery = task.delivery
    delivery.status = "Queued"
    delivery.attempts = task.attempts
    delivery.max_attempts = task.max_attempts
    delivery.last_attempt_at = when
    delivery.failure_reason = error_message
    delivery.save(update_fields=["status", "attempts", "max_attempts", "last_attempt_at", "failure_reason"])
    sync_unified_message_status(delivery.unified_message)


def mark_delivery_sent(task, provider_id: str, *, when=None):
    if not task.delivery_id:
        return
    when = when or now_ts()
    delivery = task.delivery
    delivery.status = "Sent"
    delivery.provider_id = provider_id or ""
    delivery.attempts = task.attempts
    delivery.max_attempts = task.max_attempts
    delivery.last_attempt_at = when
    delivery.sent_at = when
    delivery.processed_at = when
    delivery.failure_reason = ""
    delivery.save(
        update_fields=[
            "status",
            "provider_id",
            "attempts",
            "max_attempts",
            "last_attempt_at",
            "sent_at",
            "processed_at",
            "failure_reason",
        ]
    )
    sync_unified_message_status(delivery.unified_message)


def mark_delivery_failed(task, error_message: str, *, when=None):
    if not task.delivery_id:
        return
    when = when or now_ts()
    delivery = task.delivery
    delivery.status = "Failed"
    delivery.attempts = task.attempts
    delivery.max_attempts = task.max_attempts
    delivery.last_attempt_at = when
    delivery.processed_at = when
    delivery.failure_reason = error_message
    delivery.save(
        update_fields=["status", "attempts", "max_attempts", "last_attempt_at", "processed_at", "failure_reason"]
    )
    sync_unified_message_status(delivery.unified_message)


def sync_email_delivery_webhook(email_recipient, normalized_status: str, reason: str = ""):
    delivery = (
        MessageDelivery.objects.select_related("unified_message")
        .filter(source_type="EmailRecipient", source_id=email_recipient.id)
        .order_by("-id")
        .first()
    )
    if delivery is None:
        return

    now = now_ts()
    update_fields = []
    if delivery.status != normalized_status:
        delivery.status = normalized_status
        update_fields.append("status")
    if email_recipient.provider_id and delivery.provider_id != email_recipient.provider_id:
        delivery.provider_id = email_recipient.provider_id
        update_fields.append("provider_id")
    if normalized_status in {"Delivered", "Opened", "Clicked"}:
        delivered_at = email_recipient.delivered_at or now
        if delivery.delivered_at != delivered_at:
            delivery.delivered_at = delivered_at
            update_fields.append("delivered_at")
    if normalized_status in {"Opened", "Clicked"}:
        opened_at = email_recipient.opened_at or now
        if delivery.opened_at != opened_at:
            delivery.opened_at = opened_at
            update_fields.append("opened_at")
    if normalized_status in DELIVERY_FAILURE_STATUSES:
        failure_reason = reason or email_recipient.bounce_reason
        if delivery.failure_reason != failure_reason:
            delivery.failure_reason = failure_reason
            update_fields.append("failure_reason")
    if normalized_status in DELIVERY_SUCCESS_STATUSES | DELIVERY_FAILURE_STATUSES:
        if delivery.processed_at != now:
            delivery.processed_at = now
            update_fields.append("processed_at")
    if update_fields:
        delivery.save(update_fields=update_fields)
        sync_unified_message_status(delivery.unified_message)


def sync_sms_delivery_webhook(sms_message, normalized_status: str, reason: str = ""):
    delivery = (
        MessageDelivery.objects.select_related("unified_message")
        .filter(source_type="SmsMessage", source_id=sms_message.id)
        .order_by("-id")
        .first()
    )
    if delivery is None:
        return

    now = now_ts()
    update_fields = []
    if delivery.status != normalized_status:
        delivery.status = normalized_status
        update_fields.append("status")
    if sms_message.provider_id and delivery.provider_id != sms_message.provider_id:
        delivery.provider_id = sms_message.provider_id
        update_fields.append("provider_id")
    if normalized_status == "Delivered":
        delivered_at = sms_message.delivered_at or now
        if delivery.delivered_at != delivered_at:
            delivery.delivered_at = delivered_at
            update_fields.append("delivered_at")
    if normalized_status == "Failed":
        failure_reason = reason or sms_message.failure_reason
        if delivery.failure_reason != failure_reason:
            delivery.failure_reason = failure_reason
            update_fields.append("failure_reason")
    if normalized_status in {"Delivered", "Failed"}:
        if delivery.processed_at != now:
            delivery.processed_at = now
            update_fields.append("processed_at")
    if update_fields:
        delivery.save(update_fields=update_fields)
        sync_unified_message_status(delivery.unified_message)
