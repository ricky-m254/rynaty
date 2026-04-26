import hashlib
import hmac
import logging
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)

AFRICAS_TALKING_SMS_URL = "https://api.africastalking.com/version1/messaging"
AFRICAS_TALKING_BALANCE_URL = "https://api.africastalking.com/version1/user"
TWILIO_BASE_URL = "https://api.twilio.com/2010-04-01/Accounts"
INFOBIP_SMS_URL = "https://api.infobip.com/sms/2/text/single"
VONAGE_SMS_URL = "https://rest.nexmo.com/sms/json"
WHATSAPP_CLOUD_API_VERSION = "v19.0"
FCM_LEGACY_URL = "https://fcm.googleapis.com/fcm/send"
HTTP_TIMEOUT_SECONDS = 20


def render_template_placeholders(text: str, data: dict) -> str:
    rendered = text or ""
    for key, value in (data or {}).items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    return rendered


@dataclass
class DispatchResult:
    status: str
    provider_id: str
    failure_reason: str = ""
    cost: Decimal = Decimal("0")


def _dispatch_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _failure_result(prefix: str, reason: str) -> DispatchResult:
    return DispatchResult(status="Failed", provider_id=_dispatch_id(prefix), failure_reason=str(reason or "").strip())


def _coerce_decimal(value) -> Decimal:
    text = str(value or "").strip()
    if not text:
        return Decimal("0")
    normalized = re.sub(r"[^0-9.\-]", "", text)
    if not normalized:
        return Decimal("0")
    try:
        return Decimal(normalized)
    except Exception:
        return Decimal("0")


def _school_profile():
    from school.models import SchoolProfile

    return SchoolProfile.objects.filter(is_active=True).first()


def _school_secret(profile, field_name: str, default: str = "") -> str:
    from school.tenant_secrets import resolve_school_profile_secret

    if not profile:
        return default
    return str(resolve_school_profile_secret(profile, field_name, default=default) or default).strip()


def _tenant_setting_value(setting_key: str):
    from school.models import TenantSettings
    from school.tenant_secrets import merge_tenant_setting_secrets

    row = TenantSettings.objects.filter(key=setting_key).first()
    if not row:
        return {}
    return merge_tenant_setting_secrets(setting_key, row.value) or {}


def _provider_json(response):
    try:
        return response.json()
    except ValueError:
        return {}


def _response_error(response):
    payload = _provider_json(response)
    detail = payload if payload else (response.text or "").strip()
    if isinstance(detail, dict):
        detail = str(detail)
    return f"HTTP {response.status_code}: {detail}"[:500]


def _schema_label() -> str:
    return str(getattr(connection, "schema_name", "unknown") or "unknown")


def _sms_config():
    profile = _school_profile()
    return {
        "profile": profile,
        "provider": str(getattr(profile, "sms_provider", "") or "").strip().lower(),
        "api_key": _school_secret(profile, "sms_api_key"),
        "username": str(getattr(profile, "sms_username", "") or "").strip(),
        "sender_id": str(getattr(profile, "sms_sender_id", "") or "").strip(),
    }


def _whatsapp_config():
    profile = _school_profile()
    return {
        "profile": profile,
        "api_key": _school_secret(profile, "whatsapp_api_key"),
        "phone_id": str(getattr(profile, "whatsapp_phone_id", "") or "").strip(),
    }


def _push_config():
    for setting_key in ("integrations.push", "integrations.fcm"):
        value = _tenant_setting_value(setting_key)
        if isinstance(value, dict) and value:
            server_key = str(value.get("server_key") or "").strip()
            if server_key:
                return {"setting_key": setting_key, "server_key": server_key}
    return {"setting_key": "", "server_key": ""}


def _send_sms_africas_talking(phone: str, message: str, config: dict) -> DispatchResult:
    api_key = config["api_key"]
    username = config["username"] or "sandbox"
    if not api_key:
        return _failure_result("sms-at", "Africa's Talking API key is not configured for this tenant.")

    payload = {"username": username, "to": phone, "message": message}
    if config["sender_id"]:
        payload["from"] = config["sender_id"]
    try:
        response = requests.post(
            AFRICAS_TALKING_SMS_URL,
            headers={"apiKey": api_key, "Accept": "application/json"},
            data=payload,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return _failure_result("sms-at", f"Africa's Talking request failed: {exc}")
    if response.status_code >= 400:
        return _failure_result("sms-at", f"Africa's Talking rejected the request. {_response_error(response)}")

    payload = _provider_json(response)
    recipients = (((payload.get("SMSMessageData") or {}).get("Recipients")) or [])
    row = recipients[0] if recipients else {}
    provider_id = str(row.get("messageId") or row.get("message_id") or _dispatch_id("sms-at")).strip()
    status_text = str(row.get("status") or "").lower()
    if "fail" in status_text or "reject" in status_text or "invalid" in status_text:
        return DispatchResult(
            status="Failed",
            provider_id=provider_id,
            failure_reason=str(row.get("status") or payload.get("SMSMessageData", {}).get("Message") or "Africa's Talking send failed."),
            cost=_coerce_decimal(row.get("cost")),
        )
    return DispatchResult(status="Sent", provider_id=provider_id, cost=_coerce_decimal(row.get("cost")))


def _send_sms_twilio(phone: str, message: str, config: dict) -> DispatchResult:
    account_sid = config["username"]
    auth_token = config["api_key"]
    sender = config["sender_id"]
    if not account_sid or not auth_token:
        return _failure_result("sms-twilio", "Twilio account SID and auth token are required.")
    if not sender:
        return _failure_result("sms-twilio", "Set the SMS sender ID or phone number before using Twilio.")

    try:
        response = requests.post(
            f"{TWILIO_BASE_URL}/{account_sid}/Messages.json",
            auth=(account_sid, auth_token),
            data={"To": phone, "From": sender, "Body": message},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return _failure_result("sms-twilio", f"Twilio request failed: {exc}")
    if response.status_code >= 400:
        return _failure_result("sms-twilio", f"Twilio rejected the request. {_response_error(response)}")

    payload = _provider_json(response)
    provider_id = str(payload.get("sid") or _dispatch_id("sms-twilio")).strip()
    status_text = str(payload.get("status") or "").lower()
    if status_text in {"failed", "undelivered", "canceled"}:
        return DispatchResult(
            status="Failed",
            provider_id=provider_id,
            failure_reason=str(payload.get("message") or "Twilio send failed."),
            cost=_coerce_decimal(payload.get("price")),
        )
    return DispatchResult(status="Sent", provider_id=provider_id, cost=_coerce_decimal(payload.get("price")))


def _send_sms_infobip(phone: str, message: str, config: dict) -> DispatchResult:
    api_key = config["api_key"]
    sender = config["sender_id"]
    if not api_key:
        return _failure_result("sms-infobip", "Infobip API key is not configured for this tenant.")
    if not sender:
        return _failure_result("sms-infobip", "Set the SMS sender ID before using Infobip.")

    try:
        response = requests.post(
            INFOBIP_SMS_URL,
            headers={
                "Authorization": f"App {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={"from": sender, "to": phone, "text": message},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return _failure_result("sms-infobip", f"Infobip request failed: {exc}")
    if response.status_code >= 400:
        return _failure_result("sms-infobip", f"Infobip rejected the request. {_response_error(response)}")

    payload = _provider_json(response)
    row = ((payload.get("messages") or [{}])[0]) if isinstance(payload.get("messages"), list) else {}
    provider_id = str(row.get("messageId") or _dispatch_id("sms-infobip")).strip()
    status_group = str(((row.get("status") or {}).get("groupName")) or "").lower()
    if "fail" in status_group or "reject" in status_group or "undeliver" in status_group:
        return DispatchResult(
            status="Failed",
            provider_id=provider_id,
            failure_reason=str(((row.get("status") or {}).get("description")) or "Infobip send failed."),
        )
    return DispatchResult(status="Sent", provider_id=provider_id)


def _send_sms_vonage(phone: str, message: str, config: dict) -> DispatchResult:
    api_key = config["username"]
    api_secret = config["api_key"]
    sender = config["sender_id"]
    if not api_key or not api_secret:
        return _failure_result("sms-vonage", "Vonage API key and secret are required.")
    if not sender:
        return _failure_result("sms-vonage", "Set the SMS sender ID before using Vonage.")

    try:
        response = requests.post(
            VONAGE_SMS_URL,
            data={"api_key": api_key, "api_secret": api_secret, "to": phone, "from": sender, "text": message},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return _failure_result("sms-vonage", f"Vonage request failed: {exc}")
    if response.status_code >= 400:
        return _failure_result("sms-vonage", f"Vonage rejected the request. {_response_error(response)}")

    payload = _provider_json(response)
    row = ((payload.get("messages") or [{}])[0]) if isinstance(payload.get("messages"), list) else {}
    provider_id = str(row.get("message-id") or row.get("message_id") or _dispatch_id("sms-vonage")).strip()
    status_code = str(row.get("status") or "").strip()
    if status_code not in {"0", ""}:
        return DispatchResult(
            status="Failed",
            provider_id=provider_id,
            failure_reason=str(row.get("error-text") or "Vonage send failed."),
            cost=_coerce_decimal(row.get("message-price")),
        )
    return DispatchResult(
        status="Sent",
        provider_id=provider_id,
        cost=_coerce_decimal(row.get("message-price")),
    )


def _send_whatsapp_cloud(phone: str, message: str, config: dict) -> DispatchResult:
    api_key = config["api_key"]
    phone_id = config["phone_id"]
    if not api_key:
        return _failure_result("wa-meta", "WhatsApp API key is not configured for this tenant.")
    if not phone_id:
        return _failure_result("wa-meta", "WhatsApp phone ID is not configured for this tenant.")

    try:
        response = requests.post(
            f"https://graph.facebook.com/{WHATSAPP_CLOUD_API_VERSION}/{phone_id}/messages",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": message},
            },
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return _failure_result("wa-meta", f"WhatsApp request failed: {exc}")
    if response.status_code >= 400:
        return _failure_result("wa-meta", f"WhatsApp rejected the request. {_response_error(response)}")

    payload = _provider_json(response)
    provider_id = str((((payload.get("messages") or [{}])[0]).get("id")) or _dispatch_id("wa-meta")).strip()
    return DispatchResult(status="Sent", provider_id=provider_id)


def _send_push_fcm(token: str, title: str, body: str, config: dict) -> DispatchResult:
    server_key = str(config.get("server_key") or "").strip()
    if not server_key:
        return _failure_result("push-fcm", "Push server key is not configured for this tenant.")

    try:
        response = requests.post(
            FCM_LEGACY_URL,
            headers={"Authorization": f"key={server_key}", "Content-Type": "application/json"},
            json={"to": token, "notification": {"title": title, "body": body}},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return _failure_result("push-fcm", f"Push notification request failed: {exc}")
    if response.status_code >= 400:
        return _failure_result("push-fcm", f"Push provider rejected the request. {_response_error(response)}")

    payload = _provider_json(response)
    result_row = ((payload.get("results") or [{}])[0]) if isinstance(payload.get("results"), list) else {}
    provider_id = str(result_row.get("message_id") or payload.get("message_id") or _dispatch_id("push-fcm")).strip()
    if result_row.get("error"):
        return DispatchResult(
            status="Failed",
            provider_id=provider_id,
            failure_reason=str(result_row.get("error") or "Push send failed."),
        )
    return DispatchResult(status="Sent", provider_id=provider_id)


def send_email_placeholder(subject: str, body: str, recipients: list[str], from_email: str | None = None) -> DispatchResult:
    sender = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@sms.local")
    try:
        send_mail(subject=subject, message=body or "", from_email=sender, recipient_list=recipients, fail_silently=False)
        return DispatchResult(status="Sent", provider_id=f"email-local-{uuid.uuid4().hex[:12]}")
    except Exception as exc:  # pragma: no cover
        return DispatchResult(status="Failed", provider_id="", failure_reason=str(exc))


def send_sms_placeholder(phone: str, message: str, channel: str = "SMS") -> DispatchResult:
    channel_name = str(channel or "SMS").strip()
    normalized_phone = str(phone or "").strip()
    normalized_message = str(message or "").strip()
    if not normalized_phone:
        return _failure_result(channel_name.lower(), "Recipient phone number is required.")
    if not normalized_message:
        return _failure_result(channel_name.lower(), "Message body is required.")

    if channel_name == "WhatsApp":
        result = _send_whatsapp_cloud(normalized_phone, normalized_message, _whatsapp_config())
        logger.info(
            "WhatsApp dispatch attempted | schema=%s status=%s provider_id=%s",
            _schema_label(),
            result.status,
            result.provider_id,
        )
        return result

    config = _sms_config()
    provider = config["provider"]
    if not provider:
        return _failure_result("sms", "SMS provider is not configured for this tenant.")

    dispatchers = {
        "africastalking": _send_sms_africas_talking,
        "twilio": _send_sms_twilio,
        "infobip": _send_sms_infobip,
        "vonage": _send_sms_vonage,
    }
    dispatcher = dispatchers.get(provider)
    if not dispatcher:
        return _failure_result("sms", f"Unsupported SMS provider: {provider}.")

    result = dispatcher(normalized_phone, normalized_message, config)
    logger.info(
        "SMS dispatch attempted | schema=%s provider=%s status=%s provider_id=%s",
        _schema_label(),
        provider,
        result.status,
        result.provider_id,
    )
    return result


def sms_balance_placeholder() -> dict:
    config = _sms_config()
    provider = config["provider"]
    if not provider:
        return {
            "provider": "",
            "provider_configured": False,
            "currency": "KES",
            "balance": "UNKNOWN",
            "note": "Configure an SMS provider and tenant secret before checking balance.",
        }
    if provider == "africastalking" and config["api_key"]:
        try:
            response = requests.get(
                AFRICAS_TALKING_BALANCE_URL,
                headers={"apiKey": config["api_key"], "Accept": "application/json"},
                params={"username": config["username"] or "sandbox"},
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            if response.status_code < 400:
                payload = _provider_json(response)
                user_data = payload.get("UserData") or {}
                return {
                    "provider": provider,
                    "provider_configured": True,
                    "currency": "KES",
                    "balance": str(user_data.get("balance") or "UNKNOWN"),
                    "note": "Live Africa's Talking balance lookup.",
                }
            return {
                "provider": provider,
                "provider_configured": True,
                "currency": "KES",
                "balance": "UNKNOWN",
                "note": f"Africa's Talking balance lookup failed. {_response_error(response)}",
            }
        except requests.RequestException as exc:
            return {
                "provider": provider,
                "provider_configured": True,
                "currency": "KES",
                "balance": "UNKNOWN",
                "note": f"Africa's Talking balance lookup failed: {exc}",
            }
    return {
        "provider": provider,
        "provider_configured": bool(config["api_key"]),
        "currency": "KES",
        "balance": "UNKNOWN",
        "note": f"Live balance lookup is not wired for provider '{provider}'.",
    }


def send_push_placeholder(token: str, title: str, body: str) -> DispatchResult:
    normalized_token = str(token or "").strip()
    normalized_title = str(title or "").strip()
    normalized_body = str(body or "").strip()
    if not normalized_token:
        return _failure_result("push", "Push device token is required.")
    if not normalized_title or not normalized_body:
        return _failure_result("push", "Push title and body are required.")

    config = _push_config()
    result = _send_push_fcm(normalized_token, normalized_title, normalized_body, config)
    logger.info(
        "Push dispatch attempted | schema=%s setting=%s status=%s provider_id=%s",
        _schema_label(),
        config.get("setting_key", ""),
        result.status,
        result.provider_id,
    )
    return result


def now_ts():
    return timezone.now()


def _header_value(headers: dict, *names: str) -> str:
    lowered = {str(key).lower(): value for key, value in (headers or {}).items()}
    for name in names:
        value = lowered.get(name.lower())
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def verify_webhook_request(raw_body: bytes, headers: dict) -> tuple[bool, str]:
    token = getattr(settings, "COMMUNICATION_WEBHOOK_TOKEN", "").strip()
    secret = getattr(settings, "COMMUNICATION_WEBHOOK_SHARED_SECRET", "").strip()
    require_timestamp = bool(getattr(settings, "COMMUNICATION_WEBHOOK_REQUIRE_TIMESTAMP", False))
    max_age_seconds = int(getattr(settings, "COMMUNICATION_WEBHOOK_MAX_AGE_SECONDS", 300))

    if not token and not secret:
        return False, "Webhook verification is not configured."

    provided_token = _header_value(headers, "X-Webhook-Token")
    if not provided_token:
        auth_header = _header_value(headers, "Authorization")
        if auth_header.lower().startswith("bearer "):
            provided_token = auth_header[7:].strip()
    if token and provided_token and hmac.compare_digest(provided_token, token):
        return True, ""

    provided_signature = _header_value(headers, "X-Webhook-Signature", "X-Signature")
    if secret and provided_signature:
        timestamp = _header_value(headers, "X-Webhook-Timestamp", "X-Timestamp")
        if require_timestamp and not timestamp:
            return False, "Missing webhook timestamp."
        if timestamp:
            try:
                ts_value = int(timestamp)
            except ValueError:
                return False, "Invalid webhook timestamp."
            now_epoch = int(timezone.now().timestamp())
            if abs(now_epoch - ts_value) > max_age_seconds:
                return False, "Webhook timestamp is outside the allowed window."

        digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        expected_variants = {digest, f"sha256={digest}"}
        if timestamp:
            signed_payload = f"{timestamp}.{raw_body.decode('utf-8', errors='ignore')}".encode("utf-8")
            ts_digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
            expected_variants.update({ts_digest, f"sha256={ts_digest}"})
        if any(hmac.compare_digest(provided_signature, value) for value in expected_variants):
            return True, ""

    return False, "Invalid webhook signature/token."
