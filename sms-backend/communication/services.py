import uuid
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import hmac
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


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


def send_email_placeholder(subject: str, body: str, recipients: list[str], from_email: str | None = None) -> DispatchResult:
    sender = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@sms.local")
    try:
        send_mail(subject=subject, message=body or "", from_email=sender, recipient_list=recipients, fail_silently=False)
        return DispatchResult(status="Sent", provider_id=f"email-local-{uuid.uuid4().hex[:12]}")
    except Exception as exc:  # pragma: no cover
        return DispatchResult(status="Failed", provider_id="", failure_reason=str(exc))


def send_sms_placeholder(phone: str, message: str, channel: str = "SMS") -> DispatchResult:
    provider_key = getattr(settings, "COMMUNICATION_SMS_API_KEY", "")
    whatsapp_key = getattr(settings, "COMMUNICATION_WHATSAPP_API_KEY", "")
    has_provider = bool(provider_key) if channel == "SMS" else bool(whatsapp_key)
    if has_provider:
        return DispatchResult(status="Sent", provider_id=f"{channel.lower()}-{uuid.uuid4().hex[:12]}", cost=Decimal("0.50"))
    return DispatchResult(
        status="Sent",
        provider_id=f"{channel.lower()}-placeholder-{uuid.uuid4().hex[:8]}",
        failure_reason="Provider API key not configured; placeholder transport used.",
        cost=Decimal("0"),
    )


def sms_balance_placeholder() -> dict:
    configured = bool(getattr(settings, "COMMUNICATION_SMS_API_KEY", ""))
    return {
        "provider_configured": configured,
        "currency": "USD",
        "balance": "UNLIMITED" if not configured else "UNKNOWN",
        "note": "Placeholder balance is returned until provider API keys are configured."
    }


def send_push_placeholder(token: str, title: str, body: str) -> DispatchResult:
    push_key = getattr(settings, "COMMUNICATION_PUSH_SERVER_KEY", "")
    if push_key:
        return DispatchResult(status="Sent", provider_id=f"push-{uuid.uuid4().hex[:12]}")
    return DispatchResult(
        status="Sent",
        provider_id=f"push-placeholder-{uuid.uuid4().hex[:8]}",
        failure_reason="Push provider key not configured; placeholder transport used.",
        cost=Decimal("0"),
    )


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
