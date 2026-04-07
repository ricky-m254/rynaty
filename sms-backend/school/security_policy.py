from __future__ import annotations

from typing import Any

from .models import InstitutionSecurityPolicy


SECURITY_POLICY_FIELDS = (
    "session_timeout_minutes",
    "max_login_attempts",
    "lockout_duration_minutes",
    "min_password_length",
    "require_uppercase",
    "require_numbers",
    "require_special_characters",
    "password_expiry_days",
    "mfa_mode",
    "mfa_method",
    "ip_whitelist_enabled",
    "allowed_ip_ranges",
    "audit_log_retention_days",
)


def normalize_allowed_ip_ranges(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = value.replace(",", "\n").splitlines()
        return [entry.strip() for entry in candidates if entry.strip()]
    if isinstance(value, (list, tuple)):
        normalized: list[str] = []
        for entry in value:
            text = str(entry).strip()
            if text:
                normalized.append(text)
        return normalized
    return []


def get_or_create_security_policy() -> InstitutionSecurityPolicy:
    policy, created = InstitutionSecurityPolicy.objects.get_or_create(pk=1)
    if created:
        return policy

    changed_fields: list[str] = []
    normalized_ranges = normalize_allowed_ip_ranges(policy.allowed_ip_ranges)
    if normalized_ranges != (policy.allowed_ip_ranges or []):
        policy.allowed_ip_ranges = normalized_ranges
        changed_fields.append("allowed_ip_ranges")
    if changed_fields:
        policy.save(update_fields=changed_fields + ["updated_at"])
    return policy


def update_security_policy_from_payload(
    policy: InstitutionSecurityPolicy,
    payload: dict[str, Any],
    *,
    user=None,
) -> InstitutionSecurityPolicy:
    changed_fields: list[str] = []
    for field in SECURITY_POLICY_FIELDS:
        if field not in payload:
            continue
        value = payload[field]
        if field == "allowed_ip_ranges":
            value = normalize_allowed_ip_ranges(value)
        if getattr(policy, field) != value:
            setattr(policy, field, value)
            changed_fields.append(field)

    if user is not None and policy.updated_by_id != getattr(user, "id", None):
        policy.updated_by = user
        changed_fields.append("updated_by")

    if changed_fields:
        policy.save(update_fields=changed_fields + ["updated_at"])
    return policy


def extract_security_policy_payload(raw_payload: Any) -> dict[str, Any]:
    if not isinstance(raw_payload, dict):
        return {}

    extracted: dict[str, Any] = {}
    for field in SECURITY_POLICY_FIELDS:
        if field in raw_payload:
            extracted[field] = raw_payload[field]
    legacy_field_map = {
        "session_timeout": "session_timeout_minutes",
        "lockout_duration": "lockout_duration_minutes",
        "require_special": "require_special_characters",
        "password_expire_days": "password_expiry_days",
    }
    for legacy_field, canonical_field in legacy_field_map.items():
        if legacy_field in raw_payload and canonical_field not in extracted:
            extracted[canonical_field] = raw_payload[legacy_field]
    if "allowed_ips" in raw_payload and "allowed_ip_ranges" not in extracted:
        extracted["allowed_ip_ranges"] = raw_payload["allowed_ips"]
    if "two_factor_enabled" in raw_payload and "mfa_mode" not in extracted:
        extracted["mfa_mode"] = "ADMIN_ONLY" if raw_payload["two_factor_enabled"] else "DISABLED"
    if "two_factor_method" in raw_payload and "mfa_method" not in extracted:
        extracted["mfa_method"] = str(raw_payload["two_factor_method"]).upper()
    if "mfa_mode" in extracted:
        extracted["mfa_mode"] = str(extracted["mfa_mode"]).upper()
    if "mfa_method" in extracted:
        extracted["mfa_method"] = str(extracted["mfa_method"]).upper()
    if "allowed_ip_ranges" in extracted:
        extracted["allowed_ip_ranges"] = normalize_allowed_ip_ranges(extracted["allowed_ip_ranges"])
    return extracted
