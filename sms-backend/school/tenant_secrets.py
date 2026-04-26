from __future__ import annotations

import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


SCHOOL_PROFILE_SECRET_FIELDS = {
    "smtp_password",
    "sms_api_key",
    "whatsapp_api_key",
}

TENANT_SETTING_SECRET_FIELDS = {
    "integrations.mpesa": {"consumer_key", "consumer_secret", "passkey"},
    "integrations.stripe": {"secret_key", "webhook_secret"},
    "integrations.africas_talking": {"api_key"},
    "integrations.sendgrid": {"api_key"},
    "integrations.google_workspace": {"client_secret", "refresh_token", "service_account_key"},
    "integrations.zoom": {"client_secret", "refresh_token"},
}

GENERIC_SECRET_FIELD_NAMES = {
    "access_token",
    "api_key",
    "client_secret",
    "consumer_key",
    "consumer_secret",
    "passkey",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "secret_key",
    "service_account_key",
    "smtp_password",
    "sms_api_key",
    "token",
    "webhook_secret",
    "whatsapp_api_key",
}
NON_SECRET_FIELD_EXCEPTIONS = {"publishable_key"}
SECRET_META_KEY = "__secret_meta__"


def _derive_fernet_key(source: str) -> bytes:
    digest = hashlib.sha256(str(source).encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _default_secret_source() -> str:
    return f"{settings.SECRET_KEY}:tenant-secret-store:v1"


@lru_cache(maxsize=1)
def _keyring():
    raw_sources = list(getattr(settings, "DJANGO_TENANT_SECRET_KEYS", []) or [])
    if not raw_sources:
        raw_sources = [_default_secret_source()]

    ring = []
    for source in raw_sources:
        normalized = str(source or "").strip()
        if not normalized:
            continue
        version = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        ring.append(
            {
                "version": version,
                "fernet": Fernet(_derive_fernet_key(normalized)),
            }
        )
    if not ring:
        fallback = _default_secret_source()
        ring.append(
            {
                "version": hashlib.sha256(fallback.encode("utf-8")).hexdigest()[:16],
                "fernet": Fernet(_derive_fernet_key(fallback)),
            }
        )
    return tuple(ring)


def reset_secret_keyring_cache():
    _keyring.cache_clear()


def _primary_key():
    return _keyring()[0]


def current_secret_key_version() -> str:
    return _primary_key()["version"]


def _secret_row_model():
    from .models import TenantSecret

    return TenantSecret


def log_tenant_secret_audit(*, action: str, object_id: str, details: str, user=None, model_name: str = "TenantSecret") -> bool:
    from .models import AuditLog

    try:
        AuditLog.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            action=str(action or "")[:50],
            model_name=str(model_name or "TenantSecret")[:100],
            object_id=str(object_id or "unknown")[:50],
            details=str(details or ""),
        )
        return True
    except Exception as exc:
        logger.warning("Non-fatal tenant secret audit log failure: %s", exc)
        return False


def _stringify_secret(value) -> str:
    return str(value or "").strip()


def _masked_secret_preview(raw_value) -> str:
    text = _stringify_secret(raw_value)
    if not text:
        return ""
    if len(text) <= 4:
        return "•" * len(text)
    if len(text) <= 8:
        return f"{text[:1]}{'•' * max(len(text) - 2, 1)}{text[-1:]}"
    return f"{text[:2]}{'•' * max(len(text) - 4, 4)}{text[-2:]}"


def encrypt_secret(raw_value: str) -> tuple[str, str]:
    primary = _primary_key()
    token = primary["fernet"].encrypt(raw_value.encode("utf-8")).decode("utf-8")
    return token, primary["version"]


def decrypt_secret(ciphertext: str, key_version: str = "") -> str:
    ring = list(_keyring())
    if key_version:
        ring.sort(key=lambda item: 0 if item["version"] == key_version else 1)
    for item in ring:
        try:
            return item["fernet"].decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            continue
    raise InvalidToken("Unable to decrypt tenant secret with available key ring.")


def secret_row_key(prefix: str, *parts: str) -> str:
    suffix = ":".join(str(part).strip() for part in parts if str(part).strip())
    return f"{prefix}:{suffix}" if suffix else prefix


def school_profile_secret_key(field_name: str) -> str:
    return secret_row_key("school_profile", field_name)


def tenant_setting_secret_key(setting_key: str, field_name: str) -> str:
    return secret_row_key("tenant_setting", setting_key, field_name)


def set_tenant_secret(secret_key: str, raw_value, *, updated_by=None, description: str = ""):
    TenantSecret = _secret_row_model()
    normalized = _stringify_secret(raw_value)
    if not normalized:
        TenantSecret.objects.filter(key=secret_key).delete()
        return None

    ciphertext, key_version = encrypt_secret(normalized)
    secret, _ = TenantSecret.objects.update_or_create(
        key=secret_key,
        defaults={
            "ciphertext": ciphertext,
            "key_version": key_version,
            "description": description,
            "updated_by": updated_by,
        },
    )
    return secret


def get_tenant_secret(secret_key: str, default=None):
    TenantSecret = _secret_row_model()
    secret = TenantSecret.objects.filter(key=secret_key).first()
    if not secret or not secret.ciphertext:
        return default
    return decrypt_secret(secret.ciphertext, secret.key_version)


def delete_tenant_secret(secret_key: str):
    TenantSecret = _secret_row_model()
    TenantSecret.objects.filter(key=secret_key).delete()


def delete_tenant_setting_secrets(setting_key: str):
    TenantSecret = _secret_row_model()
    TenantSecret.objects.filter(key__startswith=f"tenant_setting:{setting_key}:").delete()


def rotate_tenant_secret(secret):
    target_version = current_secret_key_version()
    if secret.key_version == target_version:
        return False

    plaintext = decrypt_secret(secret.ciphertext, secret.key_version)
    ciphertext, key_version = encrypt_secret(plaintext)
    secret.ciphertext = ciphertext
    secret.key_version = key_version
    secret.save(update_fields=["ciphertext", "key_version", "updated_at"])
    return True


def _detected_secret_fields(payload: dict) -> set[str]:
    detected = set()
    for field_name in payload.keys():
        normalized = str(field_name or "").strip().lower()
        if normalized in NON_SECRET_FIELD_EXCEPTIONS:
            continue
        if normalized in GENERIC_SECRET_FIELD_NAMES or normalized.endswith(("_secret", "_token", "_password", "_api_key")):
            detected.add(field_name)
    return detected


def tenant_setting_secret_fields(setting_key: str, payload: dict | None = None) -> set[str]:
    explicit = set(TENANT_SETTING_SECRET_FIELDS.get(setting_key, set()))
    if payload and isinstance(payload, dict):
        explicit |= _detected_secret_fields(payload)
    return explicit


def merge_tenant_setting_secrets(setting_key: str, value):
    if not isinstance(value, dict):
        return value

    merged = dict(value)
    for field_name in tenant_setting_secret_fields(setting_key, merged):
        secret_value = get_tenant_secret(tenant_setting_secret_key(setting_key, field_name), default=None)
        if secret_value not in (None, ""):
            merged[field_name] = secret_value
    return merged


def mask_tenant_setting_value_for_response(setting_key: str, value):
    if not isinstance(value, dict):
        return value

    masked = dict(value)
    secret_meta = {}
    for field_name in tenant_setting_secret_fields(setting_key, masked):
        secret_value = get_tenant_secret(tenant_setting_secret_key(setting_key, field_name), default=None)
        if secret_value in (None, ""):
            secret_value = masked.get(field_name)
        if secret_value in (None, ""):
            masked.pop(field_name, None)
            continue

        masked.pop(field_name, None)
        secret_meta[field_name] = {
            "configured": True,
            "masked_label": "Configured (hidden)",
            "preview": _masked_secret_preview(secret_value),
        }

    if secret_meta:
        masked[SECRET_META_KEY] = secret_meta
    return masked


def sanitize_tenant_setting_value_for_storage(setting_key: str, value, *, updated_by=None):
    if not isinstance(value, dict):
        return value

    sanitized = {
        field_name: field_value
        for field_name, field_value in dict(value).items()
        if not str(field_name or "").startswith("__")
    }
    explicit_fields = set(TENANT_SETTING_SECRET_FIELDS.get(setting_key, set()))
    discovered_fields = _detected_secret_fields(sanitized)

    if explicit_fields:
        for field_name in explicit_fields:
            if field_name not in sanitized:
                continue
            raw_value = sanitized.pop(field_name)
            if not _stringify_secret(raw_value):
                continue
            set_tenant_secret(
                tenant_setting_secret_key(setting_key, field_name),
                raw_value,
                updated_by=updated_by,
                description=f"{setting_key}.{field_name}",
            )

    for field_name in discovered_fields - explicit_fields:
        raw_value = sanitized.pop(field_name)
        if not _stringify_secret(raw_value):
            continue
        set_tenant_secret(
            tenant_setting_secret_key(setting_key, field_name),
            raw_value,
            updated_by=updated_by,
            description=f"{setting_key}.{field_name}",
        )

    return sanitized


def resolve_school_profile_secret(profile, field_name: str, default: str = "") -> str:
    secret_value = get_tenant_secret(school_profile_secret_key(field_name), default=None)
    if secret_value not in (None, ""):
        return secret_value
    return str(getattr(profile, field_name, "") or default)


def store_school_profile_secrets(profile, secret_values: dict, *, updated_by=None):
    changed = []
    for field_name, raw_value in secret_values.items():
        if field_name not in SCHOOL_PROFILE_SECRET_FIELDS:
            continue
        if raw_value is None:
            continue
        set_tenant_secret(
            school_profile_secret_key(field_name),
            raw_value,
            updated_by=updated_by,
            description=f"SchoolProfile.{field_name}",
        )
        if getattr(profile, field_name, ""):
            setattr(profile, field_name, "")
            changed.append(field_name)
    if changed:
        profile.save(update_fields=changed + ["updated_at"])
