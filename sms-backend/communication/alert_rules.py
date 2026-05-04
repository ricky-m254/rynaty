from __future__ import annotations

from .dispatch_queue import get_dispatch_queue_health_payload
from .gateway_status import sync_gateway_statuses
from .models import CommunicationAlertEvent, CommunicationAlertRule
from .realtime import publish_alert_event
from .services import now_ts


def _channel_label(channel: str) -> str:
    normalized = str(channel or "").strip().upper()
    labels = {
        "EMAIL": "Email",
        "SMS": "SMS",
        "WHATSAPP": "WhatsApp",
        "PUSH": "Push",
    }
    return labels.get(normalized, "Communication")


def _event_key(rule: CommunicationAlertRule) -> str:
    return f"communication-alert-rule:{rule.id}:{(rule.channel or 'ALL').upper()}"


def _queue_bucket(queue_health: dict, channel: str) -> dict:
    normalized_channel = str(channel or "").strip().lower()
    if normalized_channel:
        return queue_health.get("by_channel", {}).get(normalized_channel, {})
    return queue_health


def _evaluate_queue_ready_backlog(rule: CommunicationAlertRule, queue_health: dict):
    bucket = _queue_bucket(queue_health, rule.channel)
    value = int(bucket.get("ready") or 0)
    threshold = max(int(rule.threshold or 1), 1)
    label = _channel_label(rule.channel)
    if rule.channel:
        title = f"{label} ready queue backlog threshold reached"
        details = f"{value} ready {label.lower()} dispatch item(s) are waiting in the queue. Threshold is {threshold}."
    else:
        title = "Communication ready queue backlog threshold reached"
        details = f"{value} ready communication dispatch item(s) are waiting in the queue. Threshold is {threshold}."
    return value >= threshold, title, details, {
        "rule_type": rule.rule_type,
        "threshold": threshold,
        "current_value": value,
        "channel": rule.channel or "",
        "bucket": bucket,
    }


def _evaluate_queue_failed_items(rule: CommunicationAlertRule, queue_health: dict):
    bucket = _queue_bucket(queue_health, rule.channel)
    value = int(bucket.get("failed") or 0)
    threshold = max(int(rule.threshold or 1), 1)
    label = _channel_label(rule.channel)
    if rule.channel:
        title = f"{label} failed dispatch threshold reached"
        details = f"{value} failed {label.lower()} dispatch item(s) are recorded. Threshold is {threshold}."
    else:
        title = "Communication failed dispatch threshold reached"
        details = f"{value} failed communication dispatch item(s) are recorded. Threshold is {threshold}."
    return value >= threshold, title, details, {
        "rule_type": rule.rule_type,
        "threshold": threshold,
        "current_value": value,
        "channel": rule.channel or "",
        "bucket": bucket,
    }


def _evaluate_queue_retrying_backlog(rule: CommunicationAlertRule, queue_health: dict):
    bucket = _queue_bucket(queue_health, rule.channel)
    value = int(bucket.get("retrying") or 0)
    threshold = max(int(rule.threshold or 1), 1)
    label = _channel_label(rule.channel)
    if rule.channel:
        title = f"{label} retry backlog threshold reached"
        details = f"{value} queued {label.lower()} dispatch item(s) are retrying. Threshold is {threshold}."
    else:
        title = "Communication retry backlog threshold reached"
        details = f"{value} queued communication dispatch item(s) are retrying. Threshold is {threshold}."
    return value >= threshold, title, details, {
        "rule_type": rule.rule_type,
        "threshold": threshold,
        "current_value": value,
        "channel": rule.channel or "",
        "bucket": bucket,
    }


def _evaluate_gateway_unconfigured(rule: CommunicationAlertRule, gateway_rows: dict):
    channel = str(rule.channel or "").strip().upper()
    row = gateway_rows.get(channel)
    configured = bool(getattr(row, "configured", False))
    label = _channel_label(channel)
    title = f"{label} gateway is not configured"
    details = f"{label} delivery is enabled for operational alerting, but the tenant gateway configuration is incomplete."
    return (not configured), title, details, {
        "rule_type": rule.rule_type,
        "channel": channel,
        "provider": getattr(row, "provider", ""),
        "configured": configured,
        "queue_ready": getattr(row, "queue_ready", 0),
        "queue_failed": getattr(row, "queue_failed", 0),
        "queue_retrying": getattr(row, "queue_retrying", 0),
    }


def _evaluate_rule(rule: CommunicationAlertRule, *, queue_health: dict, gateway_rows: dict):
    evaluators = {
        CommunicationAlertRule.RULE_QUEUE_READY_BACKLOG: lambda: _evaluate_queue_ready_backlog(rule, queue_health),
        CommunicationAlertRule.RULE_QUEUE_FAILED_ITEMS: lambda: _evaluate_queue_failed_items(rule, queue_health),
        CommunicationAlertRule.RULE_QUEUE_RETRYING_BACKLOG: lambda: _evaluate_queue_retrying_backlog(rule, queue_health),
        CommunicationAlertRule.RULE_GATEWAY_UNCONFIGURED: lambda: _evaluate_gateway_unconfigured(rule, gateway_rows),
    }
    return evaluators[rule.rule_type]()


def resolve_communication_alert_rule_events(rule: CommunicationAlertRule, *, reason: str = "") -> int:
    now = now_ts()
    resolved = 0
    for event in rule.events.exclude(status=CommunicationAlertEvent.STATUS_RESOLVED):
        metadata = dict(event.metadata or {})
        if reason:
            metadata["resolution_reason"] = reason
        event.status = CommunicationAlertEvent.STATUS_RESOLVED
        event.resolved_at = now
        event.metadata = metadata
        event.save(update_fields=["status", "resolved_at", "metadata"])
        publish_alert_event(event, event_type="alert.event.resolved")
        resolved += 1
    return resolved


def evaluate_communication_alert_rules(*, rule_ids: list[int] | None = None):
    queryset = CommunicationAlertRule.objects.filter(is_active=True).order_by("id")
    if rule_ids:
        queryset = queryset.filter(id__in=rule_ids)
    rules = list(queryset)
    queue_health = get_dispatch_queue_health_payload()
    gateway_rows = sync_gateway_statuses(include_balance=False)
    now = now_ts()
    summary = {
        "rules_evaluated": len(rules),
        "triggered": 0,
        "opened": 0,
        "updated": 0,
        "resolved": 0,
    }

    for rule in rules:
        triggered, title, details, metadata = _evaluate_rule(rule, queue_health=queue_health, gateway_rows=gateway_rows)
        summary["triggered"] += 1 if triggered else 0
        event = CommunicationAlertEvent.objects.filter(event_key=_event_key(rule)).first()

        if triggered:
            if event is None:
                event = CommunicationAlertEvent.objects.create(
                    rule=rule,
                    event_key=_event_key(rule),
                    title=title,
                    details=details,
                    severity=rule.severity,
                    status=CommunicationAlertEvent.STATUS_OPEN,
                    channel=rule.channel,
                    metadata=metadata,
                    first_triggered_at=now,
                    last_triggered_at=now,
                )
                publish_alert_event(event, event_type="alert.event.created")
                summary["opened"] += 1
            else:
                update_fields = []
                if event.title != title:
                    event.title = title
                    update_fields.append("title")
                if event.details != details:
                    event.details = details
                    update_fields.append("details")
                if event.severity != rule.severity:
                    event.severity = rule.severity
                    update_fields.append("severity")
                if event.channel != rule.channel:
                    event.channel = rule.channel
                    update_fields.append("channel")
                if (event.metadata or {}) != metadata:
                    event.metadata = metadata
                    update_fields.append("metadata")
                if event.last_triggered_at != now:
                    event.last_triggered_at = now
                    update_fields.append("last_triggered_at")
                if event.status == CommunicationAlertEvent.STATUS_RESOLVED:
                    event.status = CommunicationAlertEvent.STATUS_OPEN
                    event.resolved_at = None
                    event.acknowledged_at = None
                    update_fields.extend(["status", "resolved_at", "acknowledged_at"])
                if update_fields:
                    event.save(update_fields=update_fields)
                    publish_alert_event(event, event_type="alert.event.updated")
                    summary["updated"] += 1
        elif event is not None and event.status != CommunicationAlertEvent.STATUS_RESOLVED:
            event.status = CommunicationAlertEvent.STATUS_RESOLVED
            event.resolved_at = now
            event.save(update_fields=["status", "resolved_at"])
            publish_alert_event(event, event_type="alert.event.resolved")
            summary["resolved"] += 1

        if rule.last_evaluated_at != now:
            rule.last_evaluated_at = now
            rule.save(update_fields=["last_evaluated_at"])

    return summary


def build_communication_alert_summary(*, limit: int = 10):
    queryset = CommunicationAlertEvent.objects.select_related("rule").all()
    open_count = queryset.filter(status=CommunicationAlertEvent.STATUS_OPEN).count()
    acknowledged_count = queryset.filter(status=CommunicationAlertEvent.STATUS_ACKNOWLEDGED).count()
    resolved_count = queryset.filter(status=CommunicationAlertEvent.STATUS_RESOLVED).count()
    recent = []
    for event in queryset.exclude(status=CommunicationAlertEvent.STATUS_RESOLVED).order_by("-last_triggered_at", "-id")[:limit]:
        recent.append(
            {
                "id": event.id,
                "rule_id": event.rule_id,
                "rule_name": event.rule.name,
                "rule_type": event.rule.rule_type,
                "title": event.title,
                "details": event.details,
                "severity": event.severity,
                "status": event.status,
                "channel": event.channel,
                "last_triggered_at": event.last_triggered_at.isoformat() if event.last_triggered_at else None,
                "acknowledged_at": event.acknowledged_at.isoformat() if event.acknowledged_at else None,
                "metadata": event.metadata or {},
            }
        )
    return {
        "open": open_count,
        "acknowledged": acknowledged_count,
        "resolved": resolved_count,
        "critical_open": queryset.filter(
            status=CommunicationAlertEvent.STATUS_OPEN,
            severity=CommunicationAlertRule.SEVERITY_CRITICAL,
        ).count(),
        "by_severity": {
            "info_open": queryset.filter(status=CommunicationAlertEvent.STATUS_OPEN, severity=CommunicationAlertRule.SEVERITY_INFO).count(),
            "warning_open": queryset.filter(status=CommunicationAlertEvent.STATUS_OPEN, severity=CommunicationAlertRule.SEVERITY_WARNING).count(),
            "critical_open": queryset.filter(status=CommunicationAlertEvent.STATUS_OPEN, severity=CommunicationAlertRule.SEVERITY_CRITICAL).count(),
        },
        "recent": recent,
    }
