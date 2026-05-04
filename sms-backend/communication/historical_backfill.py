from __future__ import annotations

from .campaign_stats import sync_campaign_stats
from .delivery_backbone import (
    attach_task_delivery,
    ensure_campaign_unified_message,
    ensure_delivery,
    ensure_unified_message,
    sync_unified_message_status,
)
from .gateway_status import sync_gateway_statuses
from .models import CommunicationDispatchTask, EmailCampaign, PushNotificationLog, SmsMessage

TASK_STATUS_TO_DELIVERY_STATUS = {
    "Queued": "Queued",
    "Processing": "Processing",
    "Sent": "Sent",
    "Failed": "Failed",
}
MESSAGE_STATUS_TO_DELIVERY_STATUS = {
    "Queued": "Queued",
    "Sent": "Sent",
    "Delivered": "Delivered",
    "Opened": "Opened",
    "Clicked": "Clicked",
    "Failed": "Failed",
    "Bounced": "Bounced",
}


def _compact_metadata(payload: dict | None) -> dict:
    normalized = {}
    for key, value in (payload or {}).items():
        if value in ("", None, [], {}):
            continue
        normalized[key] = value
    return normalized


def _first_present(*values):
    for value in values:
        if value not in ("", None):
            return value
    return None


def _earliest_timestamp(*values):
    candidates = [value for value in values if value is not None]
    return min(candidates) if candidates else None


def _latest_timestamp(*values):
    candidates = [value for value in values if value is not None]
    return max(candidates) if candidates else None


def _merge_delivery_state(
    delivery,
    *,
    status: str,
    recipient: str | None = None,
    provider_id: str | None = None,
    attempts: int | None = None,
    max_attempts: int | None = None,
    queued_at=None,
    last_attempt_at=None,
    sent_at=None,
    delivered_at=None,
    opened_at=None,
    processed_at=None,
    failure_reason: str | None = None,
    metadata: dict | None = None,
):
    update_fields = []

    if status and delivery.status != status:
        delivery.status = status
        update_fields.append("status")
    if recipient not in ("", None) and delivery.recipient != recipient:
        delivery.recipient = recipient
        update_fields.append("recipient")
    if provider_id not in ("", None) and delivery.provider_id != provider_id:
        delivery.provider_id = provider_id
        update_fields.append("provider_id")
    if attempts is not None and delivery.attempts != attempts:
        delivery.attempts = attempts
        update_fields.append("attempts")
    if max_attempts is not None and delivery.max_attempts != max_attempts:
        delivery.max_attempts = max_attempts
        update_fields.append("max_attempts")

    for field_name, value in (
        ("queued_at", queued_at),
        ("last_attempt_at", last_attempt_at),
        ("sent_at", sent_at),
        ("delivered_at", delivered_at),
        ("opened_at", opened_at),
        ("processed_at", processed_at),
    ):
        if value is not None and getattr(delivery, field_name) != value:
            setattr(delivery, field_name, value)
            update_fields.append(field_name)

    if failure_reason is not None and delivery.failure_reason != failure_reason:
        delivery.failure_reason = failure_reason
        update_fields.append("failure_reason")

    merged_metadata = {**(delivery.metadata or {}), **_compact_metadata(metadata)}
    if merged_metadata != (delivery.metadata or {}):
        delivery.metadata = merged_metadata
        update_fields.append("metadata")

    if update_fields:
        delivery.save(update_fields=update_fields)


def _attach_delivery(task: CommunicationDispatchTask, delivery) -> bool:
    before = (task.delivery_id, task.source_id, delivery.source_type, delivery.source_id)
    attach_task_delivery(task, delivery)
    after = (task.delivery_id, task.source_id, delivery.source_type, delivery.source_id)
    return before != after


def _task_maps():
    email_tasks = {}
    sms_tasks = {}
    push_tasks = {}
    direct_email_tasks = []

    queryset = CommunicationDispatchTask.objects.all().order_by("id")
    for task in queryset:
        if task.source_type == "EmailRecipient" and task.source_id and task.source_id not in email_tasks:
            email_tasks[task.source_id] = task
        elif task.source_type == "SmsMessage" and task.source_id and task.source_id not in sms_tasks:
            sms_tasks[task.source_id] = task
        elif task.source_type == "PushNotificationLog" and task.source_id and task.source_id not in push_tasks:
            push_tasks[task.source_id] = task
        elif task.source_type == "DirectEmail":
            direct_email_tasks.append(task)

    return email_tasks, sms_tasks, push_tasks, direct_email_tasks


def _sync_campaign_backbone(campaign, email_tasks: dict[int, CommunicationDispatchTask], result: dict):
    unified_message = ensure_campaign_unified_message(campaign)
    recipients = list(campaign.recipients.all().order_by("id"))
    for recipient in recipients:
        delivery, _created = ensure_delivery(
            unified_message=unified_message,
            delivery_key=f"email-recipient:{recipient.id}",
            channel="EMAIL",
            recipient=recipient.email,
            source_type="EmailRecipient",
            source_id=recipient.id,
            provider_id=recipient.provider_id,
            metadata={"campaign_id": campaign.id},
        )
        task = email_tasks.get(recipient.id)
        status = MESSAGE_STATUS_TO_DELIVERY_STATUS.get(recipient.status, "Queued")
        sent_at = recipient.sent_at or campaign.sent_at
        delivered_at = recipient.delivered_at
        opened_at = recipient.opened_at
        _merge_delivery_state(
            delivery,
            status=status,
            recipient=recipient.email,
            provider_id=recipient.provider_id or _first_present(getattr(task, "provider_id", None)),
            attempts=getattr(task, "attempts", None),
            max_attempts=getattr(task, "max_attempts", None),
            queued_at=_earliest_timestamp(campaign.created_at, campaign.scheduled_at, sent_at, delivered_at, opened_at),
            last_attempt_at=_latest_timestamp(getattr(task, "claimed_at", None), getattr(task, "processed_at", None), sent_at, delivered_at, opened_at),
            sent_at=sent_at,
            delivered_at=delivered_at,
            opened_at=opened_at,
            processed_at=_latest_timestamp(getattr(task, "processed_at", None), opened_at, delivered_at, sent_at) if status != "Queued" else None,
            failure_reason=recipient.bounce_reason if status in {"Bounced", "Failed"} else "",
            metadata={"campaign_id": campaign.id},
        )
        if task and _attach_delivery(task, delivery):
            result["task_links_attached"] += 1
        result["email_recipients_synced"] += 1

    sync_unified_message_status(unified_message)
    sync_campaign_stats(campaign)
    result["campaigns_synced"] += 1
    result["campaign_stats_synced"] += 1


def _sync_sms_backbone(row, sms_tasks: dict[int, CommunicationDispatchTask], result: dict):
    task_channel = "WHATSAPP" if row.channel == "WhatsApp" else "SMS"
    task = sms_tasks.get(row.id)
    unified_message = ensure_unified_message(
        message_key=f"sms-message:{row.id}",
        kind="DIRECT",
        source_type="SmsMessage",
        source_id=row.id,
        title="WhatsApp message" if task_channel == "WHATSAPP" else "SMS message",
        body=row.message,
        created_by=row.created_by,
        metadata={"channel": row.channel},
    )
    delivery, _created = ensure_delivery(
        unified_message=unified_message,
        delivery_key=f"sms-message:{row.id}",
        channel=task_channel,
        recipient=row.recipient_phone,
        source_type="SmsMessage",
        source_id=row.id,
        provider_id=row.provider_id or _first_present(getattr(task, "provider_id", None)),
        metadata={"channel": row.channel},
        max_attempts=getattr(task, "max_attempts", 3),
    )
    status = MESSAGE_STATUS_TO_DELIVERY_STATUS.get(row.status, TASK_STATUS_TO_DELIVERY_STATUS.get(getattr(task, "status", ""), "Queued"))
    _merge_delivery_state(
        delivery,
        status=status,
        recipient=row.recipient_phone,
        provider_id=row.provider_id or _first_present(getattr(task, "provider_id", None)),
        attempts=getattr(task, "attempts", None),
        max_attempts=getattr(task, "max_attempts", None),
        queued_at=_earliest_timestamp(row.created_at, row.sent_at, row.delivered_at, getattr(task, "available_at", None)),
        last_attempt_at=_latest_timestamp(getattr(task, "claimed_at", None), getattr(task, "processed_at", None), row.delivered_at, row.sent_at),
        sent_at=row.sent_at,
        delivered_at=row.delivered_at,
        processed_at=_latest_timestamp(getattr(task, "processed_at", None), row.delivered_at, row.sent_at) if status != "Queued" else None,
        failure_reason=row.failure_reason if status == "Failed" else "",
        metadata={"channel": row.channel},
    )
    if task and _attach_delivery(task, delivery):
        result["task_links_attached"] += 1
    sync_unified_message_status(unified_message)
    result["sms_rows_synced"] += 1


def _sync_push_backbone(row, push_tasks: dict[int, CommunicationDispatchTask], result: dict):
    task = push_tasks.get(row.id)
    unified_message = ensure_unified_message(
        message_key=f"push-log:{row.id}",
        kind="DIRECT",
        source_type="PushNotificationLog",
        source_id=row.id,
        title=row.title,
        subject=row.title,
        body=row.body,
        created_by=row.created_by,
        metadata={"user_id": row.user_id},
    )
    delivery, _created = ensure_delivery(
        unified_message=unified_message,
        delivery_key=f"push-log:{row.id}",
        channel="PUSH",
        recipient=str(row.user_id),
        source_type="PushNotificationLog",
        source_id=row.id,
        provider_id=row.provider_id or _first_present(getattr(task, "provider_id", None)),
        metadata={"user_id": row.user_id},
        max_attempts=getattr(task, "max_attempts", 3),
    )
    status = MESSAGE_STATUS_TO_DELIVERY_STATUS.get(row.status, TASK_STATUS_TO_DELIVERY_STATUS.get(getattr(task, "status", ""), "Queued"))
    _merge_delivery_state(
        delivery,
        status=status,
        recipient=str(row.user_id),
        provider_id=row.provider_id or _first_present(getattr(task, "provider_id", None)),
        attempts=getattr(task, "attempts", None),
        max_attempts=getattr(task, "max_attempts", None),
        queued_at=_earliest_timestamp(row.created_at, row.sent_at, getattr(task, "available_at", None)),
        last_attempt_at=_latest_timestamp(getattr(task, "claimed_at", None), getattr(task, "processed_at", None), row.sent_at),
        sent_at=row.sent_at,
        processed_at=_latest_timestamp(getattr(task, "processed_at", None), row.sent_at) if status != "Queued" else None,
        failure_reason=row.failure_reason if status == "Failed" else "",
        metadata={"user_id": row.user_id},
    )
    if task and _attach_delivery(task, delivery):
        result["task_links_attached"] += 1
    sync_unified_message_status(unified_message)
    result["push_logs_synced"] += 1


def _sync_direct_email_backbone(task: CommunicationDispatchTask, result: dict):
    payload = task.payload or {}
    recipient = str(task.recipient or payload.get("recipient") or "").strip()
    subject = str(payload.get("subject") or "")
    body = str(payload.get("body") or "")
    from_email = str(payload.get("from_email") or "")
    unified_message = ensure_unified_message(
        message_key=f"direct-email-task:{task.id}",
        kind="DIRECT",
        source_type="DirectEmail",
        source_id=task.id,
        title=subject,
        subject=subject,
        body=body,
        metadata={"from_email": from_email},
    )
    delivery, _created = ensure_delivery(
        unified_message=unified_message,
        delivery_key=f"direct-email-task:{task.id}",
        channel="EMAIL",
        recipient=recipient,
        source_type="DirectEmail",
        source_id=task.id,
        provider_id=task.provider_id,
        metadata={"from_email": from_email},
        max_attempts=task.max_attempts,
    )
    status = TASK_STATUS_TO_DELIVERY_STATUS.get(task.status, "Queued")
    _merge_delivery_state(
        delivery,
        status=status,
        recipient=recipient,
        provider_id=task.provider_id,
        attempts=task.attempts,
        max_attempts=task.max_attempts,
        queued_at=_earliest_timestamp(task.created_at, task.available_at, task.claimed_at, task.processed_at),
        last_attempt_at=_latest_timestamp(task.claimed_at, task.processed_at),
        sent_at=task.processed_at if status == "Sent" else None,
        processed_at=task.processed_at if status in {"Sent", "Failed"} else None,
        failure_reason=task.last_error or "",
        metadata={"from_email": from_email},
    )
    if _attach_delivery(task, delivery):
        result["task_links_attached"] += 1
    sync_unified_message_status(unified_message)
    result["direct_email_tasks_synced"] += 1


def backfill_communication_backbone(*, include_balance: bool = False):
    result = {
        "campaigns_synced": 0,
        "campaign_stats_synced": 0,
        "email_recipients_synced": 0,
        "sms_rows_synced": 0,
        "push_logs_synced": 0,
        "direct_email_tasks_synced": 0,
        "task_links_attached": 0,
        "gateway_channels_synced": [],
    }

    email_tasks, sms_tasks, push_tasks, direct_email_tasks = _task_maps()

    for campaign in EmailCampaign.objects.prefetch_related("recipients").order_by("id"):
        _sync_campaign_backbone(campaign, email_tasks, result)

    for row in SmsMessage.objects.filter(is_active=True).select_related("created_by").order_by("id"):
        _sync_sms_backbone(row, sms_tasks, result)

    for row in PushNotificationLog.objects.select_related("created_by", "user").order_by("id"):
        _sync_push_backbone(row, push_tasks, result)

    for task in direct_email_tasks:
        _sync_direct_email_backbone(task, result)

    gateway_rows = sync_gateway_statuses(include_balance=include_balance)
    result["gateway_channels_synced"] = sorted(gateway_rows.keys())
    return result
