from __future__ import annotations

from django.conf import settings

from school.models import AuditLog, SchoolProfile, TenantSettings
from school.serializers import SchoolProfileSerializer
from school.tenant_secrets import (
    get_tenant_secret,
    resolve_school_profile_secret,
    sanitize_tenant_setting_value_for_storage,
    set_tenant_secret,
    tenant_setting_secret_key,
)

from .models import PushDevice
from .read_models import build_gateway_health_payload
from .services import send_email_placeholder, send_push_placeholder, send_sms_placeholder


PUSH_SETTING_KEYS = ("integrations.push", "integrations.fcm")
DEFAULT_PUSH_SETTING_KEY = "integrations.push"


def _mask_secret_preview(raw_value: str) -> str:
    text = str(raw_value or "").strip()
    if not text:
        return ""
    if len(text) <= 4:
        return "*" * len(text)
    if len(text) <= 8:
        return f"{text[:1]}{'*' * max(len(text) - 2, 1)}{text[-1:]}"
    return f"{text[:2]}{'*' * max(len(text) - 4, 4)}{text[-2:]}"


def _secret_state(raw_value: str) -> dict:
    text = str(raw_value or "").strip()
    if not text:
        return {"configured": False, "masked_label": "", "preview": ""}
    return {
        "configured": True,
        "masked_label": "Configured (hidden)",
        "preview": _mask_secret_preview(text),
    }


def _active_school_profile(*, create: bool = False, tenant=None):
    profile = SchoolProfile.objects.filter(is_active=True).first()
    if profile or not create:
        return profile
    return SchoolProfile.objects.create(
        school_name=(getattr(tenant, "name", None) or "School").strip() or "School",
        is_active=True,
    )


def _push_settings_row():
    fallback = None
    for setting_key in PUSH_SETTING_KEYS:
        row = TenantSettings.objects.filter(key=setting_key).first()
        if not row:
            continue
        if fallback is None:
            fallback = row
        if isinstance(row.value, dict) and row.value:
            return row
    return fallback


def _push_settings_state():
    row = _push_settings_row()
    setting_key = row.key if row else DEFAULT_PUSH_SETTING_KEY
    value = dict(row.value) if row and isinstance(row.value, dict) else {}
    server_key = get_tenant_secret(tenant_setting_secret_key(setting_key, "server_key"), default=None)
    if server_key in (None, "") and row:
        for alternate_key in PUSH_SETTING_KEYS:
            if alternate_key == setting_key:
                continue
            alternate = get_tenant_secret(tenant_setting_secret_key(alternate_key, "server_key"), default=None)
            if alternate not in (None, ""):
                server_key = alternate
                break
    return {
        "setting_key": setting_key,
        "value": value,
        "server_key": str(server_key or "").strip(),
    }


def run_communication_gateway_test(*, channel: str, request, target_user_id: int | None = None) -> dict:
    normalized_channel = str(channel or "").strip().upper()
    profile = _active_school_profile()
    school_name = (
        str(getattr(profile, "school_name", "") or "").strip()
        or str(getattr(getattr(request, "tenant", None), "name", None) or "").strip()
        or "School"
    )

    if normalized_channel == "EMAIL":
        if not profile:
            return {"ok": False, "error": "Save school communication settings before running the email test."}
        smtp_host = str(profile.smtp_host or "").strip()
        recipient = str(profile.smtp_user or profile.email_address or "").strip()
        if not smtp_host:
            return {"ok": False, "error": "Set the SMTP host before running the email test."}
        if not recipient:
            return {"ok": False, "error": "Set the SMTP username/email before running the email test."}
        result = send_email_placeholder(
            subject=f"{school_name} test email",
            body=(
                f"This is a test email from {school_name}. "
                "If you received this message, the communication test endpoint is working."
            ),
            recipients=[recipient],
            from_email=recipient,
        )
        if result.status != "Sent":
            return {"ok": False, "error": result.failure_reason or "Email test failed."}
        payload = {
            "channel": "EMAIL",
            "message": f"Test email sent to {recipient}.",
            "provider_id": result.provider_id,
        }
        if result.failure_reason:
            payload["note"] = result.failure_reason
        return {"ok": True, "payload": payload}

    if normalized_channel == "SMS":
        if not profile:
            return {"ok": False, "error": "Save school communication settings before running the SMS test."}
        phone = str(profile.phone or "").strip()
        provider = str(profile.sms_provider or "").strip()
        if not provider:
            return {"ok": False, "error": "Set the SMS provider before running the SMS test."}
        if not phone:
            return {"ok": False, "error": "Set the school phone number before running the SMS test."}
        result = send_sms_placeholder(
            phone=phone,
            message=f"{school_name}: this is a test SMS from the communication settings page.",
            channel="SMS",
        )
        if result.status != "Sent":
            return {"ok": False, "error": result.failure_reason or "SMS test failed."}
        payload = {
            "channel": "SMS",
            "message": f"Test SMS sent to {phone}.",
            "provider_id": result.provider_id,
        }
        if result.failure_reason:
            payload["note"] = result.failure_reason
        return {"ok": True, "payload": payload}

    if normalized_channel == "WHATSAPP":
        if not profile:
            return {"ok": False, "error": "Save school communication settings before running the WhatsApp test."}
        phone = str(profile.phone or "").strip()
        if not phone:
            return {"ok": False, "error": "Set the school phone number before running the WhatsApp test."}
        result = send_sms_placeholder(
            phone=phone,
            message=f"{school_name}: this is a test WhatsApp message from the communication settings page.",
            channel="WhatsApp",
        )
        if result.status != "Sent":
            return {"ok": False, "error": result.failure_reason or "WhatsApp test failed."}
        payload = {
            "channel": "WHATSAPP",
            "message": f"Test WhatsApp message sent to {phone}.",
            "provider_id": result.provider_id,
        }
        if result.failure_reason:
            payload["note"] = result.failure_reason
        return {"ok": True, "payload": payload}

    if normalized_channel == "PUSH":
        push_user_id = int(target_user_id or getattr(request.user, "id", 0) or 0)
        if not push_user_id:
            return {"ok": False, "error": "Select a user with an active push device before running the push test."}
        device = PushDevice.objects.filter(user_id=push_user_id, is_active=True).order_by("-last_seen_at", "-id").first()
        if not device:
            return {"ok": False, "error": "Register an active push device before running the push test."}
        result = send_push_placeholder(
            token=device.token,
            title=f"{school_name} test notification",
            body=(
                f"This is a test push notification from {school_name}. "
                "If you received this message, push delivery is configured for this tenant."
            ),
        )
        if result.status != "Sent":
            return {"ok": False, "error": result.failure_reason or "Push test failed."}
        payload = {
            "channel": "PUSH",
            "message": f"Test push notification sent to user {push_user_id}.",
            "provider_id": result.provider_id,
        }
        if result.failure_reason:
            payload["note"] = result.failure_reason
        return {"ok": True, "payload": payload}

    return {"ok": False, "error": f"Unsupported gateway test channel: {normalized_channel or 'unknown'}."}


def build_communication_gateway_settings_payload(*, request=None) -> dict:
    profile = _active_school_profile()
    tenant = getattr(request, "tenant", None)
    gateway_health = build_gateway_health_payload(include_balance=False)
    push_state = _push_settings_state()
    push_value = dict(push_state["value"])

    school_name = ""
    phone = ""
    email_address = ""
    smtp_host = ""
    smtp_port = 587
    smtp_user = ""
    smtp_use_tls = True
    sms_provider = ""
    sms_username = ""
    sms_sender_id = ""
    whatsapp_phone_id = ""
    smtp_password = ""
    sms_api_key = ""
    whatsapp_api_key = ""

    if profile:
        school_name = str(profile.school_name or "").strip()
        phone = str(profile.phone or "").strip()
        email_address = str(profile.email_address or "").strip()
        smtp_host = str(profile.smtp_host or "").strip()
        smtp_port = int(profile.smtp_port or 587)
        smtp_user = str(profile.smtp_user or "").strip()
        smtp_use_tls = bool(profile.smtp_use_tls)
        sms_provider = str(profile.sms_provider or "").strip().lower()
        sms_username = str(profile.sms_username or "").strip()
        sms_sender_id = str(profile.sms_sender_id or "").strip()
        whatsapp_phone_id = str(profile.whatsapp_phone_id or "").strip()
        smtp_password = resolve_school_profile_secret(profile, "smtp_password", default="")
        sms_api_key = resolve_school_profile_secret(profile, "sms_api_key", default="")
        whatsapp_api_key = resolve_school_profile_secret(profile, "whatsapp_api_key", default="")
    else:
        school_name = str(getattr(tenant, "name", None) or "").strip()

    email_settings_ready = bool(smtp_host and smtp_user and str(smtp_password or "").strip())
    sms_settings_ready = bool(sms_provider and str(sms_api_key or "").strip())
    whatsapp_settings_ready = bool(whatsapp_phone_id and str(whatsapp_api_key or "").strip())
    push_settings_ready = bool(push_state["server_key"])

    return {
        "profile": {
            "school_name": school_name,
            "phone": phone,
            "email_address": email_address,
        },
        "email": {
            **gateway_health["email"],
            "settings_configured": email_settings_ready,
            "settings": {
                "sender_email": email_address or str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip(),
                "test_recipient": smtp_user or email_address,
                "smtp_host": smtp_host,
                "smtp_port": smtp_port,
                "smtp_user": smtp_user,
                "smtp_use_tls": smtp_use_tls,
                "smtp_password": _secret_state(smtp_password),
            },
        },
        "sms": {
            **gateway_health["sms"],
            "settings_configured": sms_settings_ready,
            "settings": {
                "provider": sms_provider,
                "test_phone": phone,
                "username": sms_username,
                "sender_id": sms_sender_id,
                "api_key": _secret_state(sms_api_key),
            },
        },
        "whatsapp": {
            **gateway_health["whatsapp"],
            "settings_configured": whatsapp_settings_ready,
            "settings": {
                "test_phone": phone,
                "phone_id": whatsapp_phone_id,
                "api_key": _secret_state(whatsapp_api_key),
            },
        },
        "push": {
            **gateway_health["push"],
            "settings_configured": push_settings_ready,
            "settings": {
                "setting_key": push_state["setting_key"],
                "provider": str(push_value.get("provider") or "fcm").strip().lower() or "fcm",
                "enabled": bool(push_value.get("enabled")),
                "project_id": str(push_value.get("project_id") or "").strip(),
                "sender_id": str(push_value.get("sender_id") or "").strip(),
                "server_key": _secret_state(push_state["server_key"]),
            },
        },
    }


def _apply_push_settings(push_payload: dict, *, user=None):
    row = _push_settings_row()
    requested_key = str(push_payload.get("setting_key") or "").strip()
    target_key = row.key if row else (requested_key or DEFAULT_PUSH_SETTING_KEY)
    current_value = dict(row.value) if row and isinstance(row.value, dict) else {}
    next_value = dict(current_value)

    for field_name in ("enabled", "project_id", "sender_id"):
        if field_name in push_payload:
            value = push_payload[field_name]
            if field_name == "enabled":
                next_value[field_name] = bool(value)
            else:
                next_value[field_name] = str(value or "").strip()

    if "provider" in push_payload:
        next_value["provider"] = str(push_payload.get("provider") or "fcm").strip().lower() or "fcm"

    if "server_key" in push_payload:
        set_tenant_secret(
            tenant_setting_secret_key(target_key, "server_key"),
            push_payload.get("server_key"),
            updated_by=user,
            description=f"{target_key}.server_key",
        )

    sanitized_value = sanitize_tenant_setting_value_for_storage(target_key, next_value, updated_by=user)
    TenantSettings.objects.update_or_create(
        key=target_key,
        defaults={
            "value": sanitized_value,
            "description": "Communication push gateway settings",
            "category": "integrations",
            "updated_by": user,
        },
    )


def apply_communication_gateway_settings(payload: dict, *, request) -> dict:
    tenant = getattr(request, "tenant", None)
    profile = _active_school_profile(create=True, tenant=tenant)
    school_payload = {}

    profile_payload = payload.get("profile") or {}
    for field_name in ("school_name", "phone", "email_address"):
        if field_name in profile_payload:
            school_payload[field_name] = profile_payload[field_name]

    email_payload = payload.get("email") or {}
    email_field_map = {
        "sender_email": "email_address",
        "smtp_host": "smtp_host",
        "smtp_port": "smtp_port",
        "smtp_user": "smtp_user",
        "smtp_password": "smtp_password",
        "smtp_use_tls": "smtp_use_tls",
    }
    for source_field, target_field in email_field_map.items():
        if source_field in email_payload:
            school_payload[target_field] = email_payload[source_field]

    sms_payload = payload.get("sms") or {}
    sms_field_map = {
        "provider": "sms_provider",
        "username": "sms_username",
        "sender_id": "sms_sender_id",
        "api_key": "sms_api_key",
    }
    for source_field, target_field in sms_field_map.items():
        if source_field in sms_payload:
            school_payload[target_field] = sms_payload[source_field]

    whatsapp_payload = payload.get("whatsapp") or {}
    whatsapp_field_map = {
        "phone_id": "whatsapp_phone_id",
        "api_key": "whatsapp_api_key",
    }
    for source_field, target_field in whatsapp_field_map.items():
        if source_field in whatsapp_payload:
            school_payload[target_field] = whatsapp_payload[source_field]

    updated_sections = []
    if school_payload:
        serializer = SchoolProfileSerializer(
            profile,
            data=school_payload,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        updated_sections.append("school_profile")

    if "push" in payload:
        _apply_push_settings(payload.get("push") or {}, user=request.user)
        updated_sections.append("push")

    if updated_sections:
        AuditLog.objects.create(
            user=request.user,
            action="UPSERT",
            model_name="CommunicationGatewaySettings",
            object_id=str(profile.id),
            details=f"Updated sections: {', '.join(updated_sections)}",
        )

    return build_communication_gateway_settings_payload(request=request)
