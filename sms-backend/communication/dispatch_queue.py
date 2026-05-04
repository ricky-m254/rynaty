from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import connection, transaction

from .campaign_stats import sync_campaign_stats
from .delivery_backbone import (
    attach_task_delivery,
    create_ad_hoc_unified_message,
    ensure_campaign_unified_message,
    ensure_delivery,
    mark_delivery_failed,
    mark_delivery_processing,
    mark_delivery_retry,
    mark_delivery_sent,
    sync_unified_message_status,
)
from .gateway_status import sync_gateway_statuses
from .models import (
    CommunicationDispatchTask,
    EmailCampaign,
    EmailRecipient,
    PushDevice,
    PushNotificationLog,
    SmsMessage,
)
from .realtime import publish_dispatch_task_event
from .services import now_ts, send_email_placeholder, send_push_placeholder, send_sms_placeholder

EMAIL_SUCCESS_STATUSES = {"Sent", "Delivered", "Opened", "Clicked"}
QUEUE_RETRY_DELAY = timedelta(minutes=1)


def _claimable_tasks(*, batch_size: int, channels: list[str] | None = None):
    now = now_ts()
    select_for_update_kwargs = {}
    if getattr(connection.features, "has_select_for_update_skip_locked", False):
        select_for_update_kwargs["skip_locked"] = True

    with transaction.atomic():
        queryset = CommunicationDispatchTask.objects.filter(
            status="Queued",
            available_at__lte=now,
        ).order_by("available_at", "id")
        if channels:
            queryset = queryset.filter(channel__in=channels)
        tasks = list(queryset.select_for_update(**select_for_update_kwargs)[:batch_size])
        for task in tasks:
            task.status = "Processing"
            task.claimed_at = now
            task.attempts += 1
            task.save(update_fields=["status", "claimed_at", "attempts"])
            mark_delivery_processing(task, when=now)
            publish_dispatch_task_event(task, event_type="dispatch.task.claimed")
    if tasks:
        sync_gateway_statuses(channels=sorted({task.channel for task in tasks if task.channel}))
    return tasks


def _queue_task(
    *,
    channel: str,
    dedupe_key: str,
    recipient: str,
    payload: dict,
    source_type: str = "",
    source_id: int | None = None,
    max_attempts: int = 3,
    delivery=None,
):
    task, created = CommunicationDispatchTask.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults={
            "channel": channel,
            "status": "Queued",
            "source_type": source_type,
            "source_id": source_id,
            "recipient": recipient,
            "payload": payload,
            "max_attempts": max_attempts,
            "delivery": delivery,
        },
    )
    if delivery is not None and task.delivery_id != delivery.id:
        task.delivery = delivery
        task.save(update_fields=["delivery"])
    if created:
        publish_dispatch_task_event(task, event_type="dispatch.task.queued")
    return task, created


def queue_direct_emails(*, subject: str, body: str, recipients: list[str], from_email: str | None = None, created_by=None):
    queued = 0
    failed = 0
    task_ids: list[int] = []
    unified_message = None
    for recipient in recipients:
        email = str(recipient or "").strip()
        if not email:
            continue
        if "@" not in email:
            failed += 1
            continue
        if unified_message is None:
            unified_message = create_ad_hoc_unified_message(
                kind="DIRECT",
                source_type="DirectEmailBatch",
                title=subject,
                subject=subject,
                body=body,
                created_by=created_by,
                metadata={"from_email": from_email or "", "recipient_count": len(recipients)},
            )
        task, created = _queue_task(
            channel="EMAIL",
            dedupe_key=f"direct-email:{uuid.uuid4().hex}",
            recipient=email,
            payload={
                "recipient": email,
                "subject": subject,
                "body": body,
                "from_email": from_email or "",
            },
            source_type="DirectEmail",
        )
        delivery, _ = ensure_delivery(
            unified_message=unified_message,
            delivery_key=f"direct-email-task:{task.id}",
            channel="EMAIL",
            recipient=email,
            source_type="DirectEmail",
            source_id=task.id,
            metadata={"from_email": from_email or ""},
            max_attempts=task.max_attempts,
        )
        attach_task_delivery(task, delivery)
        task_ids.append(task.id)
        if created:
            queued += 1
    if unified_message is not None:
        sync_unified_message_status(unified_message)
        sync_gateway_statuses(channels=["EMAIL"])
    return {"queued": queued, "failed": failed, "task_ids": task_ids, "message_id": getattr(unified_message, "id", None)}


def queue_sms_messages(*, phones: list[str], message: str, channel: str, created_by):
    rows = []
    queued = 0
    normalized_channel = str(channel or "SMS").strip()
    task_channel = "WHATSAPP" if normalized_channel == "WhatsApp" else "SMS"
    unified_message = create_ad_hoc_unified_message(
        kind="DIRECT",
        source_type="SmsBatch" if task_channel == "SMS" else "WhatsAppBatch",
        title="SMS message" if task_channel == "SMS" else "WhatsApp message",
        body=message,
        created_by=created_by,
        metadata={"channel": normalized_channel, "recipient_count": len(phones)},
    )
    for phone in phones:
        row = SmsMessage.objects.create(
            recipient_phone=phone,
            message=message,
            channel=normalized_channel,
            status="Queued",
            created_by=created_by,
        )
        delivery, _ = ensure_delivery(
            unified_message=unified_message,
            delivery_key=f"sms-message:{row.id}",
            channel=task_channel,
            recipient=phone,
            source_type="SmsMessage",
            source_id=row.id,
            metadata={"channel": normalized_channel},
        )
        _queue_task(
            channel=task_channel,
            dedupe_key=f"sms-message:{row.id}",
            recipient=phone,
            payload={"channel": normalized_channel},
            source_type="SmsMessage",
            source_id=row.id,
            delivery=delivery,
        )
        rows.append(row)
        queued += 1
    sync_unified_message_status(unified_message)
    sync_gateway_statuses(channels=[task_channel])
    return {"rows": rows, "queued": queued}


def queue_push_notifications(*, user_ids: list[int], title: str, body: str, created_by):
    logs = []
    queued = 0
    unified_message = create_ad_hoc_unified_message(
        kind="DIRECT",
        source_type="PushBatch",
        title=title,
        subject=title,
        body=body,
        created_by=created_by,
        metadata={"recipient_count": len(user_ids)},
    )
    for user_id in user_ids:
        log = PushNotificationLog.objects.create(
            user_id=user_id,
            title=title,
            body=body,
            status="Queued",
            created_by=created_by,
        )
        delivery, _ = ensure_delivery(
            unified_message=unified_message,
            delivery_key=f"push-log:{log.id}",
            channel="PUSH",
            recipient=str(user_id),
            source_type="PushNotificationLog",
            source_id=log.id,
        )
        _queue_task(
            channel="PUSH",
            dedupe_key=f"push-log:{log.id}",
            recipient=str(user_id),
            payload={},
            source_type="PushNotificationLog",
            source_id=log.id,
            delivery=delivery,
        )
        logs.append(log)
        queued += 1
    sync_unified_message_status(unified_message)
    sync_gateway_statuses(channels=["PUSH"])
    return {"logs": logs, "queued": queued}


def enqueue_email_campaign_delivery(campaign: EmailCampaign):
    queued_recipients = list(campaign.recipients.filter(status="Queued").order_by("id"))
    created_count = 0
    unified_message = ensure_campaign_unified_message(campaign)
    for recipient in queued_recipients:
        delivery, _ = ensure_delivery(
            unified_message=unified_message,
            delivery_key=f"email-recipient:{recipient.id}",
            channel="EMAIL",
            recipient=recipient.email,
            source_type="EmailRecipient",
            source_id=recipient.id,
            metadata={"campaign_id": campaign.id},
        )
        _task, created = _queue_task(
            channel="EMAIL",
            dedupe_key=f"email-recipient:{recipient.id}",
            recipient=recipient.email,
            payload={"campaign_id": campaign.id},
            source_type="EmailRecipient",
            source_id=recipient.id,
            delivery=delivery,
        )
        if created:
            created_count += 1

    if queued_recipients:
        campaign.status = "Sending"
        campaign.sent_at = None
        campaign.save(update_fields=["status", "sent_at"])

    sync_unified_message_status(unified_message)
    sync_gateway_statuses(channels=["EMAIL"])
    return {
        "message_id": unified_message.id,
        "queued": created_count,
        "processed": len(queued_recipients),
        "already_enqueued": max(len(queued_recipients) - created_count, 0),
    }


def dispatch_due_email_campaigns(*, campaign_ids: list[int] | None = None, current_time=None):
    current_time = current_time or now_ts()
    due_qs = EmailCampaign.objects.filter(
        is_active=True,
        status="Scheduled",
        scheduled_at__isnull=False,
        scheduled_at__lte=current_time,
    )
    if campaign_ids:
        due_qs = due_qs.filter(id__in=campaign_ids)

    due_ids = list(due_qs.order_by("scheduled_at", "id").values_list("id", flat=True))
    results = []
    for campaign_id in due_ids:
        claimed = EmailCampaign.objects.filter(
            id=campaign_id,
            is_active=True,
            status="Scheduled",
            scheduled_at__isnull=False,
            scheduled_at__lte=current_time,
        ).update(status="Sending")
        if not claimed:
            continue

        campaign = EmailCampaign.objects.get(id=campaign_id)
        result = enqueue_email_campaign_delivery(campaign)
        if result["processed"] == 0:
            campaign.status = "Failed"
            campaign.sent_at = now_ts()
            campaign.save(update_fields=["status", "sent_at"])
        results.append(
            {
                "campaign_id": campaign.id,
                "title": campaign.title,
                "status": campaign.status,
                "queued": result["queued"],
                "processed": result["processed"],
            }
        )

    return {"dispatched": len(results), "results": results}


def _sync_campaign_status(campaign: EmailCampaign):
    recipients = campaign.recipients.all()
    if recipients.filter(status="Queued").exists():
        if campaign.status != "Sending" or campaign.sent_at is not None:
            campaign.status = "Sending"
            campaign.sent_at = None
            campaign.save(update_fields=["status", "sent_at"])
        sync_campaign_stats(campaign)
        return

    next_status = "Sent" if recipients.filter(status__in=EMAIL_SUCCESS_STATUSES).exists() else "Failed"
    updates = []
    if campaign.status != next_status:
        campaign.status = next_status
        updates.append("status")
    if campaign.sent_at is None:
        campaign.sent_at = now_ts()
        updates.append("sent_at")
    if updates:
        campaign.save(update_fields=updates)
    sync_campaign_stats(campaign)


def _queue_for_retry(task: CommunicationDispatchTask, error_message: str):
    now = now_ts()
    task.status = "Queued"
    task.available_at = now + QUEUE_RETRY_DELAY
    task.claimed_at = None
    task.last_error = error_message
    task.save(update_fields=["status", "available_at", "claimed_at", "last_error"])
    mark_delivery_retry(task, error_message, when=now)
    sync_gateway_statuses(channels=[task.channel])
    publish_dispatch_task_event(task, event_type="dispatch.task.retried")


def _fail_task(task: CommunicationDispatchTask, error_message: str):
    now = now_ts()
    task.status = "Failed"
    task.processed_at = now
    task.last_error = error_message
    task.save(update_fields=["status", "processed_at", "last_error"])
    mark_delivery_failed(task, error_message, when=now)
    sync_gateway_statuses(channels=[task.channel])
    publish_dispatch_task_event(task, event_type="dispatch.task.failed")


def _mark_task_sent(task: CommunicationDispatchTask, provider_id: str):
    now = now_ts()
    task.status = "Sent"
    task.provider_id = provider_id or ""
    task.last_error = ""
    task.processed_at = now
    task.save(update_fields=["status", "provider_id", "last_error", "processed_at"])
    mark_delivery_sent(task, provider_id, when=now)
    sync_gateway_statuses(channels=[task.channel])
    publish_dispatch_task_event(task, event_type="dispatch.task.sent")


def _handle_email_recipient_task(task: CommunicationDispatchTask):
    row = EmailRecipient.objects.select_related("campaign").filter(id=task.source_id).first()
    if row is None:
        _fail_task(task, "Email recipient record not found.")
        return "failed"

    result = send_email_placeholder(
        subject=row.campaign.subject,
        body=row.campaign.body_text or row.campaign.body_html,
        recipients=[row.email],
        from_email=row.campaign.sender_email or None,
    )
    if result.status == "Sent":
        row.provider_id = result.provider_id
        row.status = "Sent"
        row.sent_at = now_ts()
        row.bounce_reason = ""
        row.save(update_fields=["provider_id", "status", "sent_at", "bounce_reason"])
        _mark_task_sent(task, result.provider_id)
        _sync_campaign_status(row.campaign)
        return "sent"

    row.bounce_reason = result.failure_reason
    if task.attempts >= task.max_attempts:
        row.status = "Failed"
        row.save(update_fields=["status", "bounce_reason"])
        _fail_task(task, result.failure_reason)
        _sync_campaign_status(row.campaign)
        return "failed"

    row.status = "Queued"
    row.save(update_fields=["status", "bounce_reason"])
    _queue_for_retry(task, result.failure_reason)
    _sync_campaign_status(row.campaign)
    return "retried"


def _handle_direct_email_task(task: CommunicationDispatchTask):
    payload = task.payload or {}
    result = send_email_placeholder(
        subject=str(payload.get("subject") or ""),
        body=str(payload.get("body") or ""),
        recipients=[str(payload.get("recipient") or task.recipient or "")],
        from_email=str(payload.get("from_email") or "") or None,
    )
    if result.status == "Sent":
        _mark_task_sent(task, result.provider_id)
        return "sent"
    if task.attempts >= task.max_attempts:
        _fail_task(task, result.failure_reason)
        return "failed"
    _queue_for_retry(task, result.failure_reason)
    return "retried"


def _handle_sms_task(task: CommunicationDispatchTask):
    row = SmsMessage.objects.filter(id=task.source_id).first()
    if row is None:
        _fail_task(task, "SMS record not found.")
        return "failed"

    result = send_sms_placeholder(phone=row.recipient_phone, message=row.message, channel=row.channel)
    if result.status == "Sent":
        row.status = "Sent"
        row.provider_id = result.provider_id
        row.failure_reason = ""
        row.cost = result.cost
        row.sent_at = now_ts()
        row.save(update_fields=["status", "provider_id", "failure_reason", "cost", "sent_at"])
        _mark_task_sent(task, result.provider_id)
        return "sent"

    row.failure_reason = result.failure_reason
    row.cost = result.cost
    if task.attempts >= task.max_attempts:
        row.status = "Failed"
        row.save(update_fields=["status", "failure_reason", "cost"])
        _fail_task(task, result.failure_reason)
        return "failed"

    row.status = "Queued"
    row.save(update_fields=["status", "failure_reason", "cost"])
    _queue_for_retry(task, result.failure_reason)
    return "retried"


def _handle_push_task(task: CommunicationDispatchTask):
    row = PushNotificationLog.objects.filter(id=task.source_id).first()
    if row is None:
        _fail_task(task, "Push notification log not found.")
        return "failed"

    device = PushDevice.objects.filter(user_id=row.user_id, is_active=True).order_by("-last_seen_at", "-id").first()
    if device is None:
        failure_reason = "No active push device for user."
        if task.attempts >= task.max_attempts:
            row.status = "Failed"
            row.failure_reason = failure_reason
            row.save(update_fields=["status", "failure_reason"])
            _fail_task(task, failure_reason)
            return "failed"
        row.status = "Queued"
        row.failure_reason = failure_reason
        row.save(update_fields=["status", "failure_reason"])
        _queue_for_retry(task, failure_reason)
        return "retried"

    result = send_push_placeholder(token=device.token, title=row.title, body=row.body)
    if result.status == "Sent":
        row.status = "Sent"
        row.provider_id = result.provider_id
        row.failure_reason = ""
        row.sent_at = now_ts()
        row.save(update_fields=["status", "provider_id", "failure_reason", "sent_at"])
        _mark_task_sent(task, result.provider_id)
        return "sent"

    row.failure_reason = result.failure_reason
    if task.attempts >= task.max_attempts:
        row.status = "Failed"
        row.save(update_fields=["status", "failure_reason"])
        _fail_task(task, result.failure_reason)
        return "failed"

    row.status = "Queued"
    row.save(update_fields=["status", "failure_reason"])
    _queue_for_retry(task, result.failure_reason)
    return "retried"


def process_dispatch_queue(*, batch_size: int = 50, channels: list[str] | None = None):
    tasks = _claimable_tasks(batch_size=batch_size, channels=channels)
    summary = {
        "processed": len(tasks),
        "sent": 0,
        "retried": 0,
        "failed": 0,
        "task_ids": [task.id for task in tasks],
    }
    for task in tasks:
        if task.channel == "EMAIL" and task.source_type == "EmailRecipient":
            outcome = _handle_email_recipient_task(task)
        elif task.channel == "EMAIL" and task.source_type == "DirectEmail":
            outcome = _handle_direct_email_task(task)
        elif task.channel in {"SMS", "WHATSAPP"}:
            outcome = _handle_sms_task(task)
        elif task.channel == "PUSH":
            outcome = _handle_push_task(task)
        else:
            _fail_task(task, f"Unsupported dispatch task type: {task.channel}/{task.source_type}")
            outcome = "failed"
        summary[outcome] += 1
    return summary


def _isoformat_or_none(value):
    return value.isoformat() if value else None


def get_dispatch_queue_health_payload():
    now = now_ts()
    queryset = CommunicationDispatchTask.objects.all()
    ready_rows = queryset.filter(status="Queued", available_at__lte=now)
    delayed_rows = queryset.filter(status="Queued", available_at__gt=now)
    retrying_rows = queryset.filter(status="Queued", attempts__gt=0)
    status_keys = ["Queued", "Processing", "Sent", "Failed"]
    channel_keys = ["EMAIL", "SMS", "WHATSAPP", "PUSH"]
    oldest_ready = ready_rows.order_by("available_at", "id").first()

    by_status = {key.lower(): queryset.filter(status=key).count() for key in status_keys}
    by_channel = {}
    for channel in channel_keys:
        channel_rows = queryset.filter(channel=channel)
        channel_ready = channel_rows.filter(status="Queued", available_at__lte=now)
        channel_delayed = channel_rows.filter(status="Queued", available_at__gt=now)
        by_channel[channel.lower()] = {
            "queued_total": channel_rows.filter(status="Queued").count(),
            "ready": channel_ready.count(),
            "delayed": channel_delayed.count(),
            "retrying": channel_rows.filter(status="Queued", attempts__gt=0).count(),
            "processing": channel_rows.filter(status="Processing").count(),
            "sent": channel_rows.filter(status="Sent").count(),
            "failed": channel_rows.filter(status="Failed").count(),
        }

    recent_failures = []
    for task in queryset.filter(status="Failed").order_by("-processed_at", "-id")[:5]:
        recent_failures.append(
            {
                "id": task.id,
                "channel": task.channel,
                "source_type": task.source_type,
                "source_id": task.source_id,
                "recipient": task.recipient,
                "attempts": task.attempts,
                "max_attempts": task.max_attempts,
                "failed_at": _isoformat_or_none(task.processed_at),
                "last_error": task.last_error,
            }
        )

    return {
        "total": queryset.count(),
        "ready": ready_rows.count(),
        "delayed": delayed_rows.count(),
        "retrying": retrying_rows.count(),
        "oldest_ready_at": _isoformat_or_none(oldest_ready.available_at if oldest_ready else None),
        "oldest_ready_age_seconds": (
            max(int((now - oldest_ready.available_at).total_seconds()), 0) if oldest_ready else None
        ),
        "by_status": by_status,
        "by_channel": by_channel,
        "recent_failures": recent_failures,
    }
