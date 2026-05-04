from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError

from clients.models import Domain, Tenant
from school.permissions import request_has_module_access
from school.role_scope import ADMIN_SCOPE_PROFILES, user_has_any_scope

from .models import (
    CommunicationAlertEvent,
    CommunicationMessage,
    CommunicationRealtimeEvent,
    CommunicationRealtimePresence,
    CommunicationDispatchTask,
    Conversation,
    ConversationParticipant,
    GatewayStatus,
    Notification,
)

User = get_user_model()

SUMMARY_STREAM = "summary"
CONVERSATION_STREAM_PREFIX = "conversation:"
SOCKET_POLL_SECONDS = 1.0
PRESENCE_REFRESH_SECONDS = 30
PRESENCE_TTL_SECONDS = 90
TYPING_TTL_SECONDS = 15
MAX_REPLAY_EVENTS = 200

CONVERSATION_PATH_RE = re.compile(r"^/ws/communication/conversations/(?P<conversation_id>\d+)/$")


def _isoformat_or_none(value):
    return value.isoformat() if value else None


def _stream_for_conversation(conversation_id: int) -> str:
    return f"{CONVERSATION_STREAM_PREFIX}{conversation_id}"


def serialize_realtime_event(row: CommunicationRealtimeEvent) -> dict:
    return {
        "event_id": row.id,
        "stream": row.stream,
        "type": row.event_type,
        "occurred_at": _isoformat_or_none(row.occurred_at),
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "payload": row.payload or {},
    }


def publish_realtime_event(
    *,
    stream: str,
    event_type: str,
    entity_type: str,
    entity_id,
    payload: dict | None = None,
):
    row = CommunicationRealtimeEvent.objects.create(
        stream=str(stream or SUMMARY_STREAM).strip() or SUMMARY_STREAM,
        event_type=str(event_type or "").strip() or "event",
        entity_type=str(entity_type or "").strip() or "entity",
        entity_id=str(entity_id or "").strip(),
        payload=payload or {},
    )
    return row


def publish_summary_event(*, event_type: str, entity_type: str, entity_id, payload: dict | None = None):
    return publish_realtime_event(
        stream=SUMMARY_STREAM,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )


def publish_conversation_event(
    *,
    conversation_id: int,
    event_type: str,
    entity_type: str,
    entity_id,
    payload: dict | None = None,
):
    return publish_realtime_event(
        stream=_stream_for_conversation(conversation_id),
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )


def _message_payload(message: CommunicationMessage) -> dict:
    return {
        "conversation_id": message.conversation_id,
        "message_id": message.id,
        "sender_id": message.sender_id,
        "content": message.content,
        "message_type": message.message_type,
        "delivery_status": message.delivery_status,
        "reply_to_id": message.reply_to_id,
        "is_deleted": message.is_deleted,
        "is_edited": message.is_edited,
        "sent_at": _isoformat_or_none(message.sent_at),
        "edited_at": _isoformat_or_none(message.edited_at),
    }


def publish_message_event(message: CommunicationMessage, *, event_type: str):
    payload = _message_payload(message)
    publish_summary_event(
        event_type=event_type,
        entity_type="communication_message",
        entity_id=message.id,
        payload=payload,
    )
    publish_conversation_event(
        conversation_id=message.conversation_id,
        event_type=event_type,
        entity_type="communication_message",
        entity_id=message.id,
        payload=payload,
    )


def _notification_payload(row: Notification) -> dict:
    return {
        "notification_id": row.id,
        "recipient_id": row.recipient_id,
        "recipient_name": getattr(row.recipient, "username", ""),
        "notification_type": row.notification_type,
        "title": row.title,
        "message": row.message,
        "priority": row.priority,
        "action_url": row.action_url,
        "is_read": row.is_read,
        "read_at": _isoformat_or_none(row.read_at),
        "sent_at": _isoformat_or_none(row.sent_at),
    }


def publish_notification_event(row: Notification, *, event_type: str):
    publish_summary_event(
        event_type=event_type,
        entity_type="notification",
        entity_id=row.id,
        payload=_notification_payload(row),
    )


def publish_notification_bulk_event(*, event_type: str, user_id: int, updated: int):
    publish_summary_event(
        event_type=event_type,
        entity_type="notification",
        entity_id=user_id,
        payload={"user_id": user_id, "updated": updated},
    )


def _dispatch_task_payload(task: CommunicationDispatchTask) -> dict:
    return {
        "task_id": task.id,
        "channel": task.channel,
        "status": task.status,
        "source_type": task.source_type,
        "source_id": task.source_id,
        "recipient": task.recipient,
        "attempts": task.attempts,
        "max_attempts": task.max_attempts,
        "available_at": _isoformat_or_none(task.available_at),
        "claimed_at": _isoformat_or_none(task.claimed_at),
        "processed_at": _isoformat_or_none(task.processed_at),
        "provider_id": task.provider_id,
        "last_error": task.last_error,
        "delivery_id": task.delivery_id,
    }


def publish_dispatch_task_event(task: CommunicationDispatchTask, *, event_type: str):
    publish_summary_event(
        event_type=event_type,
        entity_type="dispatch_task",
        entity_id=task.id,
        payload=_dispatch_task_payload(task),
    )


def _gateway_status_payload(row: GatewayStatus) -> dict:
    payload = {
        "channel": row.channel,
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
        "active_devices": row.active_devices,
        "balance": row.balance_payload or {},
        "last_success_at": _isoformat_or_none(row.last_success_at),
        "last_failure_at": _isoformat_or_none(row.last_failure_at),
        "last_synced_at": _isoformat_or_none(row.last_synced_at),
    }
    payload.update(row.metadata or {})
    return payload


def publish_gateway_status_event(row: GatewayStatus, *, event_type: str = "gateway.status.updated"):
    publish_summary_event(
        event_type=event_type,
        entity_type="gateway_status",
        entity_id=row.channel,
        payload=_gateway_status_payload(row),
    )


def _alert_event_payload(row: CommunicationAlertEvent) -> dict:
    return {
        "alert_event_id": row.id,
        "rule_id": row.rule_id,
        "rule_name": getattr(row.rule, "name", ""),
        "rule_type": getattr(row.rule, "rule_type", ""),
        "title": row.title,
        "details": row.details,
        "severity": row.severity,
        "status": row.status,
        "channel": row.channel,
        "metadata": row.metadata or {},
        "first_triggered_at": _isoformat_or_none(row.first_triggered_at),
        "last_triggered_at": _isoformat_or_none(row.last_triggered_at),
        "acknowledged_at": _isoformat_or_none(row.acknowledged_at),
        "resolved_at": _isoformat_or_none(row.resolved_at),
    }


def publish_alert_event(row: CommunicationAlertEvent, *, event_type: str):
    publish_summary_event(
        event_type=event_type,
        entity_type="communication_alert_event",
        entity_id=row.id,
        payload=_alert_event_payload(row),
    )


def publish_alert_rule_event(*, rule_id: int, event_type: str, payload: dict | None = None):
    publish_summary_event(
        event_type=event_type,
        entity_type="communication_alert_rule",
        entity_id=rule_id,
        payload=payload or {"rule_id": rule_id},
    )


def publish_delivery_webhook_event(*, channel: str, source_type: str, source_id: int, payload: dict):
    publish_summary_event(
        event_type=f"delivery.{str(channel or '').lower()}.webhook",
        entity_type=source_type,
        entity_id=source_id,
        payload=payload,
    )


def _presence_payload(row: CommunicationRealtimePresence, *, event_name: str) -> dict:
    return {
        "conversation_id": row.conversation_id,
        "user_id": row.user_id,
        "username": getattr(row.user, "username", ""),
        "session_key": row.session_key,
        "event": event_name,
        "is_typing": bool(row.typing_expires_at and row.typing_expires_at > row.last_seen_at),
        "presence_expires_at": _isoformat_or_none(row.presence_expires_at),
        "typing_expires_at": _isoformat_or_none(row.typing_expires_at),
        "last_seen_at": _isoformat_or_none(row.last_seen_at),
        "metadata": row.metadata or {},
    }


def _publish_presence_row(row: CommunicationRealtimePresence, *, event_name: str, event_type: str):
    publish_conversation_event(
        conversation_id=row.conversation_id,
        event_type=event_type,
        entity_type="communication_presence",
        entity_id=f"{row.user_id}:{row.session_key}",
        payload=_presence_payload(row, event_name=event_name),
    )


def _extract_scope_headers(scope) -> dict[str, str]:
    headers = {}
    for key, value in scope.get("headers", []):
        headers[key.decode("latin1").lower()] = value.decode("latin1")
    return headers


def _extract_socket_context(scope):
    headers = _extract_scope_headers(scope)
    query_params = parse_qs((scope.get("query_string", b"") or b"").decode("utf-8"))
    tenant_hint = (
        (query_params.get("tenant_id") or query_params.get("tenant") or [headers.get("x-tenant-id", "")])[0]
        or ""
    ).strip()
    host = (headers.get("host", "") or "").split(":")[0].strip().lower()
    auth_header = (headers.get("authorization", "") or "").strip()
    token = ((query_params.get("token") or [""])[0] or "").strip()
    if not token and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    public_schema = get_public_schema_name()
    with schema_context(public_schema):
        tenant = None
        if tenant_hint:
            tenant = (
                Tenant.objects.filter(schema_name=tenant_hint).first()
                or Tenant.objects.filter(subdomain=tenant_hint).first()
                or Tenant.objects.filter(domains__domain__startswith=f"{tenant_hint}.")
                .exclude(schema_name=public_schema)
                .first()
            )
        if tenant is None and host:
            domain_row = Domain.objects.select_related("tenant").filter(domain=host).first()
            tenant = getattr(domain_row, "tenant", None)
        if tenant is None and host:
            subdomain = host.split(".")[0].strip().lower()
            if subdomain:
                tenant = Tenant.objects.filter(schema_name=subdomain).first() or Tenant.objects.filter(subdomain=subdomain).first()

    if tenant is None:
        raise AuthenticationFailed("Tenant context could not be resolved for websocket connection.")

    if not token:
        raise AuthenticationFailed("A JWT access token is required for communication websocket access.")

    with schema_context(tenant.schema_name):
        auth = JWTAuthentication()
        try:
            validated_token = auth.get_validated_token(token)
        except (InvalidToken, TokenError) as exc:
            raise AuthenticationFailed("Invalid access token for websocket connection.") from exc
        token_schema = validated_token.get("tenant_id")
        if token_schema and token_schema != tenant.schema_name:
            raise AuthenticationFailed("Token was issued for a different schema and cannot be used here.")
        user = auth.get_user(validated_token)
        request_like = SimpleNamespace(user=user)
        if not request_has_module_access(request_like, "COMMUNICATION"):
            raise AuthenticationFailed("The current user does not have communication module access.")

        path = str(scope.get("path") or "").strip()
        conversation_match = CONVERSATION_PATH_RE.match(path)
        if path == "/ws/communication/summary/":
            stream = SUMMARY_STREAM
            conversation_id = None
        elif conversation_match:
            conversation_id = int(conversation_match.group("conversation_id"))
            stream = _stream_for_conversation(conversation_id)
            conversation_exists = Conversation.objects.filter(id=conversation_id).exists()
            if not conversation_exists:
                raise AuthenticationFailed("Conversation stream does not exist.")
            if not user_has_any_scope(user, ADMIN_SCOPE_PROFILES):
                allowed = ConversationParticipant.objects.filter(
                    conversation_id=conversation_id,
                    user=user,
                    is_active=True,
                ).exists()
                if not allowed:
                    raise AuthenticationFailed("You are not allowed to access this conversation stream.")
        else:
            raise AuthenticationFailed("Unsupported communication websocket route.")

    try:
        last_event_id = int((query_params.get("last_event_id") or ["0"])[0] or 0)
    except (TypeError, ValueError):
        last_event_id = 0

    return {
        "tenant_schema": tenant.schema_name,
        "user_id": user.id,
        "username": user.username,
        "stream": stream,
        "conversation_id": conversation_id,
        "last_event_id": max(last_event_id, 0),
    }


def _load_replay_events(*, tenant_schema: str, stream: str, last_event_id: int):
    with schema_context(tenant_schema):
        rows = list(
            CommunicationRealtimeEvent.objects.filter(stream=stream, id__gt=max(int(last_event_id or 0), 0))
            .order_by("id")[:MAX_REPLAY_EVENTS]
        )
        return [serialize_realtime_event(row) for row in rows]


def _refresh_presence(*, tenant_schema: str, conversation_id: int, user_id: int, session_key: str):
    with schema_context(tenant_schema):
        now = timezone.now()
        row, _created = CommunicationRealtimePresence.objects.update_or_create(
            conversation_id=conversation_id,
            user_id=user_id,
            session_key=session_key,
            defaults={
                "last_seen_at": now,
                "presence_expires_at": now + timedelta(seconds=PRESENCE_TTL_SECONDS),
                "typing_expires_at": None,
            },
        )
        row = CommunicationRealtimePresence.objects.select_related("user").get(id=row.id)
        _publish_presence_row(row, event_name="online", event_type="presence.updated")


def _set_typing_presence(
    *,
    tenant_schema: str,
    conversation_id: int,
    user_id: int,
    session_key: str,
    is_typing: bool,
):
    with schema_context(tenant_schema):
        now = timezone.now()
        row, _created = CommunicationRealtimePresence.objects.update_or_create(
            conversation_id=conversation_id,
            user_id=user_id,
            session_key=session_key,
            defaults={
                "last_seen_at": now,
                "presence_expires_at": now + timedelta(seconds=PRESENCE_TTL_SECONDS),
                "typing_expires_at": now + timedelta(seconds=TYPING_TTL_SECONDS) if is_typing else None,
            },
        )
        row = CommunicationRealtimePresence.objects.select_related("user").get(id=row.id)
        _publish_presence_row(
            row,
            event_name="typing" if is_typing else "typing_stopped",
            event_type="typing.updated",
        )


def _clear_presence(*, tenant_schema: str, conversation_id: int, user_id: int, session_key: str):
    with schema_context(tenant_schema):
        row = (
            CommunicationRealtimePresence.objects.select_related("user")
            .filter(conversation_id=conversation_id, user_id=user_id, session_key=session_key)
            .first()
        )
        if not row:
            return
        payload = _presence_payload(row, event_name="offline")
        row.delete()
        publish_conversation_event(
            conversation_id=conversation_id,
            event_type="presence.updated",
            entity_type="communication_presence",
            entity_id=f"{user_id}:{session_key}",
            payload=payload,
        )


async def _send_json(send, payload: dict):
    await send({"type": "websocket.send", "text": json.dumps(payload)})


async def communication_websocket_application(scope, receive, send):
    try:
        context = await sync_to_async(_extract_socket_context, thread_sensitive=True)(scope)
    except AuthenticationFailed:
        await send({"type": "websocket.close", "code": 4403})
        return
    except Exception:
        await send({"type": "websocket.close", "code": 4401})
        return

    await send({"type": "websocket.accept"})

    tenant_schema = context["tenant_schema"]
    stream = context["stream"]
    conversation_id = context["conversation_id"]
    user_id = context["user_id"]
    session_key = uuid.uuid4().hex
    last_event_id = context["last_event_id"]
    last_presence_refresh = asyncio.get_running_loop().time()

    replay_events = await sync_to_async(
        _load_replay_events,
        thread_sensitive=True,
    )(tenant_schema=tenant_schema, stream=stream, last_event_id=last_event_id)
    for event in replay_events:
        last_event_id = max(last_event_id, int(event.get("event_id") or 0))
        await _send_json(send, event)

    if conversation_id is not None:
        await sync_to_async(_refresh_presence, thread_sensitive=True)(
            tenant_schema=tenant_schema,
            conversation_id=conversation_id,
            user_id=user_id,
            session_key=session_key,
        )

    try:
        while True:
            incoming = None
            try:
                incoming = await asyncio.wait_for(receive(), timeout=SOCKET_POLL_SECONDS)
            except asyncio.TimeoutError:
                incoming = None

            if incoming:
                event_type = incoming.get("type")
                if event_type == "websocket.disconnect":
                    break
                if event_type == "websocket.receive":
                    raw_text = incoming.get("text") or ""
                    if raw_text:
                        try:
                            payload = json.loads(raw_text)
                        except json.JSONDecodeError:
                            payload = {}
                        action = str(payload.get("action") or "").strip().lower()
                        if conversation_id is not None and action in {"ping", "presence"}:
                            await sync_to_async(_refresh_presence, thread_sensitive=True)(
                                tenant_schema=tenant_schema,
                                conversation_id=conversation_id,
                                user_id=user_id,
                                session_key=session_key,
                            )
                            await _send_json(
                                send,
                                {
                                    "event_id": last_event_id,
                                    "stream": stream,
                                    "type": "presence.pong",
                                    "occurred_at": None,
                                    "entity_type": "communication_presence",
                                    "entity_id": f"{user_id}:{session_key}",
                                    "payload": {"conversation_id": conversation_id, "user_id": user_id},
                                },
                            )
                        elif conversation_id is not None and action == "typing":
                            await sync_to_async(_set_typing_presence, thread_sensitive=True)(
                                tenant_schema=tenant_schema,
                                conversation_id=conversation_id,
                                user_id=user_id,
                                session_key=session_key,
                                is_typing=bool(payload.get("is_typing", True)),
                            )

            replay_events = await sync_to_async(
                _load_replay_events,
                thread_sensitive=True,
            )(tenant_schema=tenant_schema, stream=stream, last_event_id=last_event_id)
            for event in replay_events:
                last_event_id = max(last_event_id, int(event.get("event_id") or 0))
                await _send_json(send, event)

            if conversation_id is not None:
                current_time = asyncio.get_running_loop().time()
                if current_time - last_presence_refresh >= PRESENCE_REFRESH_SECONDS:
                    await sync_to_async(_refresh_presence, thread_sensitive=True)(
                        tenant_schema=tenant_schema,
                        conversation_id=conversation_id,
                        user_id=user_id,
                        session_key=session_key,
                    )
                    last_presence_refresh = current_time
    finally:
        if conversation_id is not None:
            await sync_to_async(_clear_presence, thread_sensitive=True)(
                tenant_schema=tenant_schema,
                conversation_id=conversation_id,
                user_id=user_id,
                session_key=session_key,
            )
