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

    setting = TenantSettings.objects.filter(key="integrations.mpesa").first()
    if not setting or not setting.value:
        raise MpesaError(
            "M-Pesa is not configured for this school. "
            "Go to Settings → Integrations → M-Pesa to add credentials."
        )

    cfg = setting.value
    if not cfg.get("enabled", True) is True and cfg.get("enabled") is not None:
        # Only block if explicitly set to False
        if cfg.get("enabled") is False:
            raise MpesaError("M-Pesa integration is disabled for this school.")

    required = ["consumer_key", "consumer_secret", "shortcode", "passkey"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
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


def _friendly_daraja_error(status_code, response_body, environment):
    """
    Convert a Daraja HTTP error response into a plain-English message that a
    school admin can act on.  ``response_body`` is the parsed JSON dict (or
    empty dict if parsing failed).
    """
    error_code = response_body.get("errorCode", "")
    error_msg = response_body.get("errorMessage", "")

    # --- credential / auth problems ---
    if status_code in (400, 401) or error_code.startswith("400.002"):
        return (
            "Invalid consumer key or secret — double-check your Daraja app "
            "credentials. Make sure you copied them from the correct Daraja "
            "app and haven't included extra spaces."
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

    if not resp.ok:
        try:
            body = resp.json()
        except Exception:
            body = {}
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
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise MpesaError(f"STK push request failed: {exc}") from exc

    data = resp.json()
    response_code = str(data.get("ResponseCode", ""))
    if response_code != "0":
        raise MpesaError(
            f"Daraja rejected the STK push. "
            f"Code: {response_code} | Description: {data.get('ResponseDescription', data)}"
        )

    return {
        "checkout_request_id": data["CheckoutRequestID"],
        "merchant_request_id": data["MerchantRequestID"],
        "response_description": data.get("ResponseDescription", ""),
        "customer_message": data.get("CustomerMessage", ""),
        "environment": creds["environment"],
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
            "amount": None,
            "mpesa_receipt": None,
            "phone": None,
            "transaction_date": None,
        }
