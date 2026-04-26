"""
school/stripe.py
----------------
Lean Stripe Checkout helpers for the finance MVP.

Credentials are read per-tenant from TenantSettings with key ``integrations.stripe``:
    {
        "enabled": true,
        "publishable_key": "pk_test_...",
        "secret_key": "sk_test_...",
        "webhook_secret": "whsec_..."
    }
"""

from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import requests


STRIPE_API_BASE = "https://api.stripe.com/v1"
ZERO_DECIMAL_CURRENCIES = {
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "JPY",
    "KMF",
    "KRW",
    "MGA",
    "PYG",
    "RWF",
    "UGX",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
}


class StripeError(Exception):
    """Raised for all Stripe integration errors."""


def _friendly_stripe_error(status_code, response_body):
    error = response_body.get("error", {}) if isinstance(response_body, dict) else {}
    message = str(error.get("message") or "").strip()
    code = str(error.get("code") or "").strip()

    if status_code == 401 or code in {"invalid_api_key", "api_key_expired"}:
        return (
            "Invalid Stripe secret key. Update Settings -> Finance -> Stripe "
            "with a valid test or live secret key."
        )
    if status_code == 403:
        return (
            "Stripe rejected this request for the configured account. "
            "Check your API key permissions and dashboard access."
        )
    if status_code == 404:
        return (
            "Stripe could not find the requested resource. "
            "Check the account mode and webhook configuration."
        )
    if status_code == 429:
        return (
            "Stripe is rate limiting requests right now. "
            "Wait a moment and try again."
        )
    if status_code >= 500:
        return (
            "Stripe returned a server error. "
            "Try again in a few minutes."
        )
    if message:
        return f"Stripe rejected the request: {message}"
    return f"Stripe returned an unexpected error (HTTP {status_code})."


def _get_credentials():
    from .models import TenantSettings
    from .tenant_secrets import merge_tenant_setting_secrets

    setting = TenantSettings.objects.filter(key="integrations.stripe").first()
    raw_value = setting.value if setting else None
    cfg = merge_tenant_setting_secrets("integrations.stripe", raw_value) if isinstance(raw_value, dict) else raw_value
    if not setting or not cfg:
        raise StripeError(
            "Stripe is not configured for this school. "
            "Go to Settings -> Finance -> Stripe to add your API keys."
        )

    if cfg.get("enabled") is False:
        raise StripeError("Stripe integration is disabled for this school.")

    secret_key = str(cfg.get("secret_key") or "").strip()
    if not secret_key:
        raise StripeError(
            "Stripe secret key is missing. "
            "Update Settings -> Finance -> Stripe."
        )

    mode = ""
    if secret_key.startswith("sk_live_"):
        mode = "live"
    elif secret_key.startswith("sk_test_"):
        mode = "test"

    return {
        "publishable_key": str(cfg.get("publishable_key") or "").strip(),
        "secret_key": secret_key,
        "webhook_secret": str(cfg.get("webhook_secret") or "").strip(),
        "mode": mode,
    }


def _request(method, path, *, secret_key, data=None, timeout=20):
    try:
        response = requests.request(
            method=method.upper(),
            url=f"{STRIPE_API_BASE}{path}",
            headers={"Authorization": f"Bearer {secret_key}"},
            data=data or {},
            timeout=timeout,
        )
    except requests.exceptions.ConnectionError:
        raise StripeError(
            "Could not reach Stripe. Check your internet connection and try again."
        )
    except requests.exceptions.Timeout:
        raise StripeError(
            "The connection to Stripe timed out. Please try again."
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.status_code >= 400:
        raise StripeError(_friendly_stripe_error(response.status_code, payload))

    return payload if isinstance(payload, dict) else {}


def _to_minor_units(amount, currency):
    try:
        value = Decimal(str(amount))
    except InvalidOperation:
        raise StripeError("Invalid amount supplied for Stripe checkout.")

    code = str(currency or "KES").upper()
    if code in ZERO_DECIMAL_CURRENCIES:
        return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return int((value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def test_connection(config=None):
    cfg = config or _get_credentials()
    account = _request("GET", "/account", secret_key=cfg["secret_key"])
    profile = account.get("business_profile") or {}
    display_name = (
        profile.get("name")
        or account.get("email")
        or account.get("id")
        or "Stripe account"
    )
    livemode = bool(account.get("livemode"))
    return {
        "account_id": account.get("id") or "",
        "display_name": display_name,
        "livemode": livemode,
        "mode": "live" if livemode else "test",
    }


def create_checkout_session(
    *,
    amount,
    currency,
    description,
    success_url,
    cancel_url,
    metadata=None,
    client_reference_id="",
    customer_email="",
):
    cfg = _get_credentials()
    currency_code = str(currency or "KES").upper()
    unit_amount = _to_minor_units(amount, currency_code)
    if unit_amount <= 0:
        raise StripeError("Stripe checkout amount must be greater than zero.")

    payload = {
        "mode": "payment",
        "payment_method_types[0]": "card",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items[0][price_data][currency]": currency_code.lower(),
        "line_items[0][price_data][product_data][name]": (description or "School fee payment")[:120],
        "line_items[0][price_data][unit_amount]": str(unit_amount),
        "line_items[0][quantity]": "1",
        "billing_address_collection": "auto",
        "submit_type": "pay",
    }
    if client_reference_id:
        payload["client_reference_id"] = client_reference_id
    if customer_email:
        payload["customer_email"] = customer_email

    for key, value in (metadata or {}).items():
        if value in (None, ""):
            continue
        payload[f"metadata[{key}]"] = str(value)

    session = _request(
        "POST",
        "/checkout/sessions",
        secret_key=cfg["secret_key"],
        data=payload,
    )
    session["configured_mode"] = cfg["mode"] or ("live" if session.get("livemode") else "test")
    return session


def verify_webhook_signature(raw_body, signature_header, webhook_secret, tolerance=300):
    if not webhook_secret:
        return False, "Stripe webhook secret is not configured."
    if not signature_header:
        return False, "Missing Stripe-Signature header."

    parts = {}
    for part in str(signature_header).split(","):
        key, _, value = part.partition("=")
        key = key.strip()
        value = value.strip()
        if key and value:
            parts.setdefault(key, []).append(value)

    timestamp = parts.get("t", [None])[0]
    signatures = parts.get("v1", [])
    if not timestamp or not signatures:
        return False, "Malformed Stripe-Signature header."

    try:
        timestamp_value = int(timestamp)
    except (TypeError, ValueError):
        return False, "Invalid Stripe signature timestamp."

    if tolerance and abs(int(time.time()) - timestamp_value) > tolerance:
        return False, "Stripe signature timestamp is outside the allowed tolerance."

    payload_to_sign = f"{timestamp_value}.{raw_body.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(
        webhook_secret.encode("utf-8"),
        payload_to_sign,
        hashlib.sha256,
    ).hexdigest()

    if not any(hmac.compare_digest(candidate, expected) for candidate in signatures):
        return False, "Invalid Stripe webhook signature."

    return True, ""
