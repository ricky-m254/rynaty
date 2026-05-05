"""
school/mpesa.py
---------------
Thin wrapper around Safaricom's Daraja 2.0 API for M-Pesa STK Push (Lipa Na MPesa Online).

Credentials are read per-tenant from TenantSettings with key ``integrations.mpesa``:
    {
        "enabled": true,
        "consumer_key": "...",
        "consumer_secret": "...",
        "shortcode": "174379",
        "passkey": "...",
        "environment": "sandbox"   // or "production"
    }

All methods raise ``MpesaError`` on failure so callers can handle cleanly.
Never raises unexpected exceptions that would break unrelated flows.
"""
import base64
import logging
from datetime import datetime
from decimal import Decimal

import requests

logger = logging.getLogger(__name__)

SANDBOX_BASE = "https://sandbox.safaricom.co.ke"
PRODUCTION_BASE = "https://api.safaricom.co.ke"


class MpesaError(Exception):
    """Raised for all MPesa/Daraja errors."""


def _get_credentials():
    """
    Load M-Pesa credentials from TenantSettings.
    Returns a dict with keys: consumer_key, consumer_secret, shortcode, passkey, base_url.
    Raises MpesaError if credentials are missing or disabled.
    """
    from .models import TenantSettings
    from .tenant_secrets import (
        merge_tenant_setting_secrets,
        tenant_secret_exists,
        tenant_setting_secret_key,
    )

    setting = TenantSettings.objects.filter(key="integrations.mpesa").first()
    raw_value = setting.value if setting else None
    cfg = merge_tenant_setting_secrets("integrations.mpesa", raw_value) if isinstance(raw_value, dict) else raw_value
    if not setting or not cfg:
        raise MpesaError(
            "M-Pesa is not configured for this school. "
            "Go to Settings → Integrations → M-Pesa to add credentials."
        )
    if not cfg.get("enabled", True) is True and cfg.get("enabled") is not None:
        # Only block if explicitly set to False
        if cfg.get("enabled") is False:
            raise MpesaError("M-Pesa integration is disabled for this school.")

    required = ["consumer_key", "consumer_secret", "shortcode", "passkey"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        unreadable_secret_rows = [
            field_name
            for field_name in missing
            if tenant_secret_exists(
                tenant_setting_secret_key("integrations.mpesa", field_name)
            )
        ]
        if unreadable_secret_rows:
            raise MpesaError(
                "Stored M-Pesa credentials could not be decrypted in this deployment. "
                "Verify DJANGO_TENANT_SECRET_KEYS includes the original encryption key, "
                "or keep DJANGO_SECRET_KEY consistent across deployments before retrying."
            )
        raise MpesaError(
            f"M-Pesa credentials incomplete. Missing: {', '.join(missing)}. "
            "Please update Settings → Integrations → M-Pesa."
        )

    env = str(cfg.get("environment", "sandbox")).lower()
    base_url = PRODUCTION_BASE if env == "production" else SANDBOX_BASE

    return {
        "consumer_key": cfg["consumer_key"],
        "consumer_secret": cfg["consumer_secret"],
        "shortcode": str(cfg["shortcode"]),
        "passkey": cfg["passkey"],
        "base_url": base_url,
        "environment": env,
    }


def _friendly_stk_result_code(result_code: int, raw_desc: str = "") -> str:
    """
    Convert a Daraja STK Push ResultCode (from callback or query) into a
    plain-English message suitable for display to finance staff or students.

    Common codes from Safaricom's STK Push documentation:
        0    — Success (payment confirmed)
        1    — Insufficient funds in customer account
        17   — Risk limit exceeded; customer must try again later
        20   — Exceeds transaction limit set by customer
        26   — Safaricom system is temporarily busy
        1001 — Wrong M-Pesa PIN entered; payment rejected
        1019 — STK push timed out — customer did not respond in time
        1032 — Customer cancelled the payment request on their phone
        1037 — Customer's phone could not be reached (switched off / no signal)
    """
    messages = {
        0: "Payment confirmed successfully.",
        1: (
            "The customer's M-Pesa account has insufficient funds. "
            "Please ask the customer to top up and try again."
        ),
        17: (
            "This transaction has been flagged by Safaricom's risk controls. "
            "The customer should try again later or contact Safaricom."
        ),
        20: (
            "The amount exceeds the customer's M-Pesa transaction limit. "
            "The customer may need to increase their limit or pay in smaller amounts."
        ),
        26: (
            "Safaricom's M-Pesa service is temporarily busy. "
            "Please wait a minute and try again."
        ),
        1001: (
            "The customer entered the wrong M-Pesa PIN. "
            "Please ask the customer to try again with the correct PIN."
        ),
        1019: (
            "The payment request timed out — the customer did not respond on their phone. "
            "Please send a new payment request."
        ),
        1032: (
            "The customer cancelled the payment request on their phone. "
            "Please ask the customer to try again if this was a mistake."
        ),
        1037: (
            "The customer's phone could not be reached (it may be switched off or out of network). "
            "Please ask the customer to check their phone and try again."
        ),
    }
    friendly = messages.get(result_code)
    if friendly:
        return friendly
    if raw_desc:
        return f"Payment was not completed: {raw_desc} (code {result_code})."
    return f"Payment was not completed (Safaricom code {result_code}). Please try again or contact support."


def _friendly_stk_push_response_code(response_code: str, description: str, environment: str) -> str:
    """
    Convert a Daraja STK Push initiation ResponseCode (from processrequest) into
    a plain-English message.  ResponseCode "0" means success; any other value
    means the push was rejected before it reached the customer's phone.

    Common ResponseCode values:
        "0"  — Success (push sent to customer's phone)
        "1"  — Request rejected by Daraja (wrong shortcode, passkey, or payload)
    """
    if response_code == "1":
        return (
            "Daraja rejected the payment push request. "
            "This usually means your Business Short Code or PassKey is incorrect. "
            "Please check Settings → Integrations → M-Pesa and verify your credentials."
        )
    if response_code in ("400.002.02", "400.002.03", "404.001.03"):
        opposite = "Production" if environment == "sandbox" else "Sandbox"
        return (
            f"Daraja could not process the request — you may be using {opposite} credentials "
            f"in the '{environment}' environment. "
            "Please check Settings → Integrations → M-Pesa and ensure the environment matches your credentials."
        )
    if description:
        return (
            f"Daraja rejected the payment push (code {response_code}): {description}. "
            "Please check your M-Pesa settings and try again."
        )
    return (
        f"Daraja rejected the payment push (code {response_code}). "
        "Please check your M-Pesa settings and try again."
    )


def _mask_value(value, keep_start=3, keep_end=2):
    """Mask sensitive values before writing them to logs."""
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= keep_start + keep_end:
        return "*" * len(text)
    masked_len = max(len(text) - keep_start - keep_end, 1)
    return f"{text[:keep_start]}{'*' * masked_len}{text[-keep_end:]}"


def _mask_phone(value):
    return _mask_value(value, keep_start=6, keep_end=2)


def _sanitise_daraja_data(value):
    """Recursively mask secrets in Daraja request/response payloads."""
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            lowered = str(key or "").lower()
            if lowered in {
                "password",
                "passkey",
                "consumer_secret",
                "authorization",
                "access_token",
                "securitycredential",
            }:
                redacted[key] = "***redacted***"
            elif lowered in {"phone", "phonenumber", "partya"}:
                redacted[key] = _mask_phone(item)
            elif lowered in {"consumer_key"}:
                redacted[key] = _mask_value(item, keep_start=4, keep_end=2)
            else:
                redacted[key] = _sanitise_daraja_data(item)
        return redacted
    if isinstance(value, list):
        return [_sanitise_daraja_data(item) for item in value]
    return value


def _safe_response_body(resp):
    try:
        return _sanitise_daraja_data(resp.json())
    except Exception:
        raw = str(getattr(resp, "text", "") or "").strip()
        return {"raw": raw[:500]} if raw else {}


def _friendly_daraja_error(status_code, response_body, environment):
    """
    Convert a Daraja HTTP error response into a plain-English message that a
    school admin can act on.  ``response_body`` is the parsed JSON dict (or
    empty dict if parsing failed).
    """
    error_code = str(response_body.get("errorCode", "") or "").strip()
    error_msg = str(
        response_body.get("errorMessage", "")
        or response_body.get("ResponseDescription", "")
        or response_body.get("error_description", "")
        or ""
    ).strip()
    detail_blob = f"{error_code} {error_msg}".lower()

    # --- clearly invalid callback URL / public URL problems ---
    if "callback" in detail_blob and (
        "url" in detail_blob or "https" in detail_blob or "host" in detail_blob or "valid" in detail_blob
    ):
        return (
            "Daraja rejected the callback URL. Confirm the public callback URL is correct, "
            "HTTPS, and reachable from Safaricom, then test again."
            + (f" Daraja said: {error_msg}" if error_msg else "")
        )
        return (
            "Invalid consumer key or secret — double-check your Daraja app "
            "credentials. Make sure you copied them from the correct Daraja "
            "app and haven't included extra spaces."
        )

    # --- shortcode / PartyB / receiving account problems ---
    if (
        "shortcode" in detail_blob
        or "short code" in detail_blob
        or "partyb" in detail_blob
        or "paybill" in detail_blob
        or "till" in detail_blob
        or "businessshortcode" in detail_blob
    ):
        return (
            "Daraja rejected the Business Short Code / PartyB receiving account. "
            "Confirm the shortcode is correct for this tenant and matches the selected environment."
            + (f" Daraja said: {error_msg}" if error_msg else "")
        )

    # --- passkey / generated password problems ---
    if "passkey" in detail_blob or "password" in detail_blob:
        return (
            "Daraja rejected the passkey for this shortcode. "
            "Confirm the Daraja passkey matches the Business Short Code and environment."
            + (f" Daraja said: {error_msg}" if error_msg else "")
        )

    # --- credential / auth problems ---
    if (
        status_code == 401
        or "consumer key" in detail_blob
        or "consumer secret" in detail_blob
        or "access token" in detail_blob
        or "oauth" in detail_blob
        or error_code.startswith("401")
    ):
        return (
            "Daraja rejected the consumer key or secret. Double-check the Daraja app "
            "credentials, make sure they match the selected environment, and confirm "
            "you have not included extra spaces."
        )

    # --- wrong environment (sandbox key vs production URL or vice-versa) ---
    if status_code == 404 or error_code.startswith("404"):
        opposite = "Production" if environment == "sandbox" else "Sandbox"
        return (
            f"Daraja could not find the requested resource. "
            f"You selected the '{environment}' environment — if your credentials "
            f"belong to the {opposite} app, please switch the environment setting "
            "to match."
        )

    # --- server-side / rate-limit issues ---
    if status_code == 429:
        return (
            "Daraja is temporarily rate-limiting requests. "
            "Wait a few minutes before testing again."
        )

    if status_code >= 500:
        return (
            "Safaricom's Daraja service returned a server error. "
            "This is on Safaricom's side — try again in a few minutes."
        )

    # --- generic request validation problems ---
    if status_code == 400 or error_code.startswith("400.002"):
        return (
            "Daraja rejected the STK request before it reached the phone. "
            "Check the selected environment, Business Short Code, PassKey, and callback URL, then test again."
            + (f" Daraja said: {error_msg}" if error_msg else "")
        )

    # --- fallback: include the Daraja error code if available ---
    if error_code and error_msg:
        return f"Daraja rejected the request (code {error_code}): {error_msg}"

    return (
        f"Daraja returned an unexpected error (HTTP {status_code}). "
        "Check that your credentials and environment setting are correct."
    )


def _get_access_token(creds):
    """
    Fetch a short-lived OAuth access token from Daraja.
    Returns the token string.
    Raises MpesaError with a plain-English message on any failure.
    """
    url = f"{creds['base_url']}/oauth/v1/generate?grant_type=client_credentials"
    raw = f"{creds['consumer_key']}:{creds['consumer_secret']}"
    b64 = base64.b64encode(raw.encode()).decode()
    logger.debug(
        "M-Pesa OAuth token request | env=%s url=%s consumer_key=%s shortcode=%s",
        creds.get("environment", "sandbox"),
        url,
        _mask_value(creds.get("consumer_key"), keep_start=4, keep_end=2),
        creds.get("shortcode", ""),
    )

    try:
        resp = requests.get(url, headers={"Authorization": f"Basic {b64}"}, timeout=15)
    except requests.exceptions.ConnectionError:
        raise MpesaError(
            "Could not reach Safaricom's Daraja service. "
            "Check your internet connection and try again."
        )
    except requests.exceptions.Timeout:
        raise MpesaError(
            "The connection to Daraja timed out. "
            "Safaricom's servers may be slow — try again in a moment."
        )
    except requests.exceptions.RequestException:
        raise MpesaError(
            "An unexpected network error occurred while contacting Daraja. "
            "Check your internet connection and try again."
        )

    logger.debug(
        "M-Pesa OAuth token response | env=%s status=%s body=%s",
        creds.get("environment", "sandbox"),
        resp.status_code,
        _safe_response_body(resp),
    )

    if not resp.ok:
        try:
            body = resp.json()
        except Exception:
            body = {}
        if resp.status_code in (400, 401):
            msg = (
                "Daraja rejected the consumer key or secret. Double-check the Daraja app "
                "credentials, make sure they match the selected environment, and confirm "
                "you have not included extra spaces."
            )
        else:
            msg = _friendly_daraja_error(resp.status_code, body, creds.get("environment", "sandbox"))
        raise MpesaError(msg)

    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise MpesaError(
            "Daraja connected but did not return an access token. "
            "This may indicate a Daraja app configuration issue — "
            "ensure your app is active and the OAuth grant type is enabled."
        )
    return token


def _normalise_phone(phone: str) -> str:
    """
    Convert a Kenyan phone number to the 254XXXXXXXXX format Daraja requires.
    Accepts: 07XXXXXXXX, +2547XXXXXXXX, 2547XXXXXXXX
    """
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    if not phone.startswith("254") or len(phone) != 12:
        raise MpesaError(
            f"Invalid phone number '{phone}'. "
            "Please enter a valid Kenyan number e.g. 0712345678."
        )
    return phone


def initiate_stk_push(phone: str, amount: Decimal, account_ref: str, callback_url: str,
                      description: str = "School Fees") -> dict:
    """
    Initiate an MPesa Express (STK Push) request.

    Parameters
    ----------
    phone        : customer's phone number (07xx, +2547xx, 2547xx)
    amount       : amount in KES (must be positive integer in practice; decimals rounded up)
    account_ref  : bill account reference shown on the customer's phone (max 12 chars)
    callback_url : HTTPS URL Daraja will POST the result to
    description  : transaction description shown to customer (max 13 chars)

    Returns
    -------
    dict with keys:
        checkout_request_id  — unique ID to poll/match the transaction
        merchant_request_id  — Safaricom's internal ID
        response_description — human-readable status from Safaricom
        customer_message     — message shown to customer
        environment          — sandbox | production
    """
    creds = _get_credentials()
    token = _get_access_token(creds)
    phone = _normalise_phone(phone)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    raw_password = f"{creds['shortcode']}{creds['passkey']}{timestamp}"
    password = base64.b64encode(raw_password.encode()).decode()

    # Daraja requires integer amounts
    int_amount = int(Decimal(str(amount)).to_integral_value())
    if int_amount < 1:
        raise MpesaError("Amount must be at least KES 1.")

    payload = {
        "BusinessShortCode": creds["shortcode"],
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int_amount,
        "PartyA": phone,
        "PartyB": creds["shortcode"],
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": account_ref[:20],
        "TransactionDesc": description[:13],
    }

    url = f"{creds['base_url']}/mpesa/stkpush/v1/processrequest"
    logger.debug(
        "M-Pesa STK push request | env=%s url=%s shortcode=%s party_b=%s callback_url=%s payload=%s",
        creds.get("environment", "sandbox"),
        url,
        creds["shortcode"],
        payload["PartyB"],
        callback_url,
        _sanitise_daraja_data(payload),
    )
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=20,
        )
    except requests.exceptions.ConnectionError:
        raise MpesaError(
            "Could not reach Safaricom's Daraja service to send the payment request. "
            "Check your internet connection and try again."
        )
    except requests.exceptions.Timeout:
        raise MpesaError(
            "The payment request to Daraja timed out. "
            "Safaricom's servers may be slow — please try again in a moment."
        )
    except requests.exceptions.RequestException as exc:
        raise MpesaError(
            "An unexpected network error occurred while sending the payment request. "
            "Check your internet connection and try again."
        ) from exc

    logger.debug(
        "M-Pesa STK push response | env=%s status=%s body=%s",
        creds.get("environment", "sandbox"),
        resp.status_code,
        _safe_response_body(resp),
    )

    if not resp.ok:
        try:
            body = resp.json()
        except Exception:
            body = {}
        msg = _friendly_daraja_error(resp.status_code, body, creds.get("environment", "sandbox"))
        raise MpesaError(msg)

    data = resp.json()
    response_code = str(data.get("ResponseCode", ""))
    if response_code != "0":
        desc = data.get("ResponseDescription", "")
        friendly = _friendly_stk_push_response_code(response_code, desc, creds.get("environment", "sandbox"))
        raise MpesaError(friendly)

    return {
        "checkout_request_id": data["CheckoutRequestID"],
        "merchant_request_id": data["MerchantRequestID"],
        "response_description": data.get("ResponseDescription", ""),
        "customer_message": data.get("CustomerMessage", ""),
        "environment": creds["environment"],
    }


def query_stk_status(checkout_request_id: str) -> dict:
    """
    Query the status of a previously initiated STK Push transaction using the
    Daraja STK Push Query API (POST /mpesa/stkpushquery/v1/query).

    Parameters
    ----------
    checkout_request_id : the CheckoutRequestID returned by initiate_stk_push

    Returns
    -------
    dict with keys:
        success            : bool  (True = payment confirmed by Safaricom)
        result_code        : int
        result_desc        : str
        mpesa_receipt      : str | None
        amount             : Decimal | None
        checkout_request_id: str
    Raises MpesaError if credentials are missing or the network call fails.
    """
    creds = _get_credentials()
    token = _get_access_token(creds)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    raw_password = f"{creds['shortcode']}{creds['passkey']}{timestamp}"
    password = base64.b64encode(raw_password.encode()).decode()

    payload = {
        "BusinessShortCode": creds["shortcode"],
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }

    url = f"{creds['base_url']}/mpesa/stkpushquery/v1/query"
    logger.debug(
        "M-Pesa STK query request | env=%s url=%s shortcode=%s checkout_request_id=%s payload=%s",
        creds.get("environment", "sandbox"),
        url,
        creds["shortcode"],
        _mask_value(checkout_request_id, keep_start=8, keep_end=4),
        _sanitise_daraja_data(payload),
    )
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=20,
        )
    except requests.exceptions.ConnectionError:
        raise MpesaError(
            "Could not reach Safaricom's Daraja service while querying transaction status."
        )
    except requests.exceptions.Timeout:
        raise MpesaError(
            "The connection to Daraja timed out while querying transaction status."
        )
    except requests.exceptions.RequestException as exc:
        raise MpesaError(f"STK query request failed: {exc}") from exc

    logger.debug(
        "M-Pesa STK query response | env=%s status=%s checkout_request_id=%s body=%s",
        creds.get("environment", "sandbox"),
        resp.status_code,
        _mask_value(checkout_request_id, keep_start=8, keep_end=4),
        _safe_response_body(resp),
    )

    if not resp.ok:
        try:
            body = resp.json()
        except Exception:
            body = {}
        msg = _friendly_daraja_error(resp.status_code, body, creds.get("environment", "sandbox"))
        raise MpesaError(f"STK query failed: {msg}")

    data = resp.json()
    result_code_raw = data.get("ResultCode", data.get("errorCode", ""))
    try:
        result_code = int(result_code_raw)
    except (TypeError, ValueError):
        result_code = -1

    result_desc = data.get("ResultDesc", data.get("errorMessage", ""))
    success = result_code == 0
    friendly_message = _friendly_stk_result_code(result_code, result_desc)

    mpesa_receipt = data.get("MpesaReceiptNumber") or None
    amount_raw = data.get("Amount")
    amount = Decimal(str(amount_raw)) if amount_raw is not None else None

    return {
        "success": success,
        "result_code": result_code,
        "result_desc": result_desc,
        "friendly_message": friendly_message,
        "mpesa_receipt": mpesa_receipt,
        "amount": amount,
        "checkout_request_id": checkout_request_id,
    }


def parse_stk_callback(payload: dict) -> dict:
    """
    Parse the STK push callback payload sent by Daraja to the callback URL.

    Returns a normalised dict:
        success          : bool
        checkout_request_id
        merchant_request_id
        result_code      : int
        result_desc      : str
        amount           : Decimal | None
        mpesa_receipt    : str | None  (M-Pesa transaction ID)
        phone            : str | None
        transaction_date : str | None
    """
    try:
        body = payload.get("Body", {}).get("stkCallback", {})
        checkout_id = body.get("CheckoutRequestID", "")
        merchant_id = body.get("MerchantRequestID", "")
        result_code = int(body.get("ResultCode", -1))
        result_desc = body.get("ResultDesc", "")
        friendly_message = _friendly_stk_result_code(result_code, result_desc)

        amount = None
        mpesa_receipt = None
        phone = None
        transaction_date = None

        if result_code == 0:
            items = body.get("CallbackMetadata", {}).get("Item", [])
            meta = {item["Name"]: item.get("Value") for item in items}
            amount = Decimal(str(meta.get("Amount", 0)))
            mpesa_receipt = str(meta.get("MpesaReceiptNumber", ""))
            phone = str(meta.get("PhoneNumber", ""))
            transaction_date = str(meta.get("TransactionDate", ""))

        return {
            "success": result_code == 0,
            "checkout_request_id": checkout_id,
            "merchant_request_id": merchant_id,
            "result_code": result_code,
            "result_desc": result_desc,
            "friendly_message": friendly_message,
            "amount": amount,
            "mpesa_receipt": mpesa_receipt,
            "phone": phone,
            "transaction_date": transaction_date,
        }
    except Exception as exc:
        logger.error("Error parsing STK callback: %s | payload: %s", exc, payload)
        return {
            "success": False,
            "checkout_request_id": "",
            "merchant_request_id": "",
            "result_code": -1,
            "result_desc": str(exc),
            "friendly_message": "An unexpected error occurred while processing the payment callback.",
            "amount": None,
            "mpesa_receipt": None,
            "phone": None,
            "transaction_date": None,
        }
