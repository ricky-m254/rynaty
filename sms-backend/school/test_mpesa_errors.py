"""
Tests for M-Pesa error-message mapping.

Covers:
  - _friendly_daraja_error: all branches (400, 401, 404, 429, 500+, fallback)
  - _get_access_token: end-to-end with mocked requests.get for every error
    scenario (HTTP errors, ConnectionError, Timeout, RequestException,
    missing token)
  - MpesaTestConnectionView POST: verifies that raw Daraja errors are
    surfaced as clear, actionable messages in the API response

Run with:
    python manage.py test school.test_mpesa_errors
"""
import unittest
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from school.mpesa import (
    MpesaError,
    SANDBOX_BASE,
    PRODUCTION_BASE,
    _friendly_daraja_error,
    _get_access_token,
    _normalise_phone,
    _sanitise_daraja_data,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sandbox_creds(**overrides):
    base = {
        "consumer_key": "test_key",
        "consumer_secret": "test_secret",
        "shortcode": "174379",
        "passkey": "test_passkey",
        "base_url": SANDBOX_BASE,
        "environment": "sandbox",
    }
    base.update(overrides)
    return base


def _prod_creds(**overrides):
    base = _sandbox_creds(base_url=PRODUCTION_BASE, environment="production")
    base.update(overrides)
    return base


def _make_response(status_code, json_body=None, raises=None):
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = status_code < 400
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.side_effect = ValueError("no body")
    return resp


# ===========================================================================
# 1. Pure unit tests for _friendly_daraja_error
# ===========================================================================

class TestFriendlyDarajaError(unittest.TestCase):
    """Direct unit tests for _friendly_daraja_error — no Django required."""

    # --- 400 Bad Request ---
    def test_400_returns_generic_request_validation_message(self):
        msg = _friendly_daraja_error(400, {}, "sandbox")
        self.assertIn("before it reached the phone", msg.lower())
        self.assertIn("callback url", msg.lower())

    def test_400_with_error_body_returns_generic_request_validation_message(self):
        body = {"errorCode": "400.002.02", "errorMessage": "Invalid credentials"}
        msg = _friendly_daraja_error(400, body, "sandbox")
        self.assertIn("before it reached the phone", msg.lower())
        self.assertIn("invalid credentials", msg.lower())

    def test_400_with_passkey_hint_returns_passkey_message(self):
        body = {"errorCode": "400.001.01", "errorMessage": "Invalid PassKey"}
        msg = _friendly_daraja_error(400, body, "sandbox")
        self.assertIn("passkey", msg.lower())
        self.assertIn("shortcode", msg.lower())

    def test_400_with_shortcode_hint_returns_shortcode_message(self):
        body = {"errorCode": "400.001.02", "errorMessage": "Invalid BusinessShortCode"}
        msg = _friendly_daraja_error(400, body, "sandbox")
        self.assertIn("partyb", msg.lower())
        self.assertIn("shortcode", msg.lower())

    def test_400_with_callback_hint_returns_callback_message(self):
        body = {"errorCode": "400.001.03", "errorMessage": "Invalid CallBackURL"}
        msg = _friendly_daraja_error(400, body, "sandbox")
        self.assertIn("callback url", msg.lower())
        self.assertIn("https", msg.lower())

    # --- 401 Unauthorized ---
    def test_401_returns_credential_message(self):
        msg = _friendly_daraja_error(401, {}, "sandbox")
        self.assertIn("consumer key or secret", msg.lower())

    def test_401_with_extra_spaces_hint(self):
        msg = _friendly_daraja_error(401, {}, "production")
        self.assertIn("extra spaces", msg.lower())

    # --- 400.002 error code on a non-400/401 status (edge case) ---
    def test_400002_error_code_triggers_generic_request_message(self):
        body = {"errorCode": "400.002.03", "errorMessage": "Bad request"}
        msg = _friendly_daraja_error(200, body, "sandbox")
        self.assertIn("before it reached the phone", msg.lower())

    # --- 404 Not Found ---
    def test_404_sandbox_suggests_production_switch(self):
        msg = _friendly_daraja_error(404, {}, "sandbox")
        self.assertIn("Production", msg)
        self.assertIn("sandbox", msg)

    def test_404_production_suggests_sandbox_switch(self):
        msg = _friendly_daraja_error(404, {}, "production")
        self.assertIn("Sandbox", msg)
        self.assertIn("production", msg)

    def test_404_error_code_prefix_triggers_same_message(self):
        body = {"errorCode": "404.001.04", "errorMessage": "Not found"}
        msg = _friendly_daraja_error(200, body, "sandbox")
        self.assertIn("resource", msg.lower())

    # --- 429 Rate Limit ---
    def test_429_rate_limit_message(self):
        msg = _friendly_daraja_error(429, {}, "sandbox")
        self.assertIn("rate-limiting", msg.lower())
        self.assertIn("wait", msg.lower())

    # --- 500+ Server Errors ---
    def test_500_returns_safaricom_server_error(self):
        msg = _friendly_daraja_error(500, {}, "sandbox")
        self.assertIn("server error", msg.lower())
        self.assertIn("safaricom", msg.lower())

    def test_503_also_treated_as_server_error(self):
        msg = _friendly_daraja_error(503, {}, "sandbox")
        self.assertIn("server error", msg.lower())

    def test_504_also_treated_as_server_error(self):
        msg = _friendly_daraja_error(504, {}, "production")
        self.assertIn("server error", msg.lower())

    # --- Fallback with Daraja error code ---
    def test_fallback_includes_error_code_and_message(self):
        body = {"errorCode": "999.001.01", "errorMessage": "Unknown error occurred"}
        msg = _friendly_daraja_error(422, body, "sandbox")
        self.assertIn("999.001.01", msg)
        self.assertIn("Unknown error occurred", msg)

    # --- Fallback without Daraja error code ---
    def test_fallback_without_error_code_includes_http_status(self):
        msg = _friendly_daraja_error(422, {}, "sandbox")
        self.assertIn("422", msg)
        self.assertIn("unexpected", msg.lower())

    def test_fallback_empty_error_code_only_includes_http_status(self):
        body = {"errorCode": "", "errorMessage": ""}
        msg = _friendly_daraja_error(418, body, "sandbox")
        self.assertIn("418", msg)


class TestDarajaPayloadSanitisation(unittest.TestCase):
    def test_sanitise_masks_password_token_and_phone_fields(self):
        payload = {
            "Password": "abc123",
            "PhoneNumber": "254700123456",
            "PartyA": "254700123456",
            "consumer_key": "consumer-key-123",
            "access_token": "token-xyz",
            "nested": {"passkey": "passkey-demo"},
        }
        result = _sanitise_daraja_data(payload)

        self.assertEqual(result["Password"], "***redacted***")
        self.assertEqual(result["access_token"], "***redacted***")
        self.assertEqual(result["nested"]["passkey"], "***redacted***")
        self.assertNotEqual(result["PhoneNumber"], payload["PhoneNumber"])
        self.assertNotEqual(result["PartyA"], payload["PartyA"])
        self.assertIn("*", result["consumer_key"])


class TestNormalisePhone(unittest.TestCase):
    def test_normalise_phone_accepts_local_kenyan_number(self):
        self.assertEqual(_normalise_phone("0712345678"), "254712345678")

    def test_normalise_phone_accepts_plus_254_format(self):
        self.assertEqual(_normalise_phone("+254712345678"), "254712345678")

    def test_normalise_phone_accepts_already_normalised_format(self):
        self.assertEqual(_normalise_phone("254712345678"), "254712345678")

    def test_normalise_phone_rejects_invalid_number(self):
        with self.assertRaises(MpesaError) as ctx:
            _normalise_phone("12345")
        self.assertIn("valid Kenyan number", str(ctx.exception))


# ===========================================================================
# 2. _get_access_token end-to-end with mocked requests.get
# ===========================================================================

class TestGetAccessTokenErrors(unittest.TestCase):
    """
    Mocks requests.get to verify that each Daraja error scenario produces
    a MpesaError with a clear, plain-English message.
    """

    def _call(self, creds=None):
        """Shortcut for calling _get_access_token with sandbox creds."""
        return _get_access_token(creds or _sandbox_creds())

    # --- successful token ---
    @patch("school.mpesa.requests.get")
    def test_success_returns_token(self, mock_get):
        mock_get.return_value = _make_response(200, {"access_token": "tok123"})
        token = self._call()
        self.assertEqual(token, "tok123")

    # --- HTTP 400 ---
    @patch("school.mpesa.requests.get")
    def test_400_raises_mpesa_error_with_credential_hint(self, mock_get):
        mock_get.return_value = _make_response(400, {})
        with self.assertRaises(MpesaError) as ctx:
            self._call()
        self.assertIn("consumer key or secret", str(ctx.exception).lower())

    # --- HTTP 401 ---
    @patch("school.mpesa.requests.get")
    def test_401_raises_mpesa_error_with_credential_hint(self, mock_get):
        mock_get.return_value = _make_response(401, {"errorCode": "401.001.01",
                                                      "errorMessage": "Unauthorized"})
        with self.assertRaises(MpesaError) as ctx:
            self._call()
        self.assertIn("consumer key or secret", str(ctx.exception).lower())

    # --- HTTP 404 (sandbox env) ---
    @patch("school.mpesa.requests.get")
    def test_404_sandbox_suggests_environment_switch(self, mock_get):
        mock_get.return_value = _make_response(404, {})
        with self.assertRaises(MpesaError) as ctx:
            self._call(_sandbox_creds())
        self.assertIn("Production", str(ctx.exception))

    # --- HTTP 404 (production env) ---
    @patch("school.mpesa.requests.get")
    def test_404_production_suggests_environment_switch(self, mock_get):
        mock_get.return_value = _make_response(404, {})
        with self.assertRaises(MpesaError) as ctx:
            self._call(_prod_creds())
        self.assertIn("Sandbox", str(ctx.exception))

    # --- HTTP 429 ---
    @patch("school.mpesa.requests.get")
    def test_429_raises_rate_limit_message(self, mock_get):
        mock_get.return_value = _make_response(429, {})
        with self.assertRaises(MpesaError) as ctx:
            self._call()
        self.assertIn("rate-limiting", str(ctx.exception).lower())

    # --- HTTP 500 ---
    @patch("school.mpesa.requests.get")
    def test_500_raises_server_error_message(self, mock_get):
        mock_get.return_value = _make_response(500, {})
        with self.assertRaises(MpesaError) as ctx:
            self._call()
        self.assertIn("server error", str(ctx.exception).lower())

    # --- HTTP 503 ---
    @patch("school.mpesa.requests.get")
    def test_503_raises_server_error_message(self, mock_get):
        mock_get.return_value = _make_response(503, {})
        with self.assertRaises(MpesaError) as ctx:
            self._call()
        self.assertIn("server error", str(ctx.exception).lower())

    # --- ConnectionError ---
    @patch("school.mpesa.requests.get")
    def test_connection_error_raises_reachability_message(self, mock_get):
        import requests as req_module
        mock_get.side_effect = req_module.exceptions.ConnectionError("Network unreachable")
        with self.assertRaises(MpesaError) as ctx:
            self._call()
        msg = str(ctx.exception).lower()
        self.assertIn("could not reach", msg)
        self.assertIn("internet", msg)

    # --- Timeout ---
    @patch("school.mpesa.requests.get")
    def test_timeout_raises_timeout_message(self, mock_get):
        import requests as req_module
        mock_get.side_effect = req_module.exceptions.Timeout("Read timed out")
        with self.assertRaises(MpesaError) as ctx:
            self._call()
        msg = str(ctx.exception).lower()
        self.assertIn("timed out", msg)

    # --- Generic RequestException ---
    @patch("school.mpesa.requests.get")
    def test_generic_request_exception_raises_network_message(self, mock_get):
        import requests as req_module
        mock_get.side_effect = req_module.exceptions.RequestException("SSL error")
        with self.assertRaises(MpesaError) as ctx:
            self._call()
        msg = str(ctx.exception).lower()
        self.assertIn("unexpected network error", msg)

    # --- 200 OK but access_token missing ---
    @patch("school.mpesa.requests.get")
    def test_missing_token_in_200_response_raises(self, mock_get):
        mock_get.return_value = _make_response(200, {"access_token": ""})
        with self.assertRaises(MpesaError) as ctx:
            self._call()
        msg = str(ctx.exception).lower()
        self.assertIn("did not return an access token", msg)

    # --- 200 OK but JSON is unparseable ---
    @patch("school.mpesa.requests.get")
    def test_unparseable_error_body_falls_back_to_http_status(self, mock_get):
        resp = MagicMock()
        resp.status_code = 401
        resp.ok = False
        resp.json.side_effect = ValueError("bad json")
        mock_get.return_value = resp
        with self.assertRaises(MpesaError) as ctx:
            self._call()
        self.assertIn("consumer key or secret", str(ctx.exception).lower())


# ===========================================================================
# 3. MpesaTestConnectionView: verifies plain-English errors reach the API
# ===========================================================================

class TestMpesaTestConnectionViewErrors(SimpleTestCase):
    """
    Exercises the MpesaTestConnectionView POST endpoint with mocked
    _get_access_token so we can verify:
      - error messages are surfaced in the JSON response
      - success=False is returned for every error branch
      - HTTP 400 is returned for all error cases
    """

    def setUp(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from rest_framework.permissions import AllowAny
        from django.contrib.auth import get_user_model
        from school.views import MpesaTestConnectionView

        User = get_user_model()
        self.factory = APIRequestFactory()
        self.user = User(pk=9999, username="mpesa_admin", is_active=True)

        self._orig_permission_classes = MpesaTestConnectionView.permission_classes
        self._orig_throttle_classes = MpesaTestConnectionView.throttle_classes
        MpesaTestConnectionView.permission_classes = [AllowAny]
        MpesaTestConnectionView.throttle_classes = []

    def tearDown(self):
        from school.views import MpesaTestConnectionView
        MpesaTestConnectionView.permission_classes = self._orig_permission_classes
        MpesaTestConnectionView.throttle_classes = self._orig_throttle_classes

    def _post(self, body=None):
        """POST to the view with full credential body and no cache."""
        from rest_framework.test import force_authenticate

        body = body or {
            "consumer_key": "key",
            "consumer_secret": "secret",
            "shortcode": "174379",
            "passkey": "passkey",
            "environment": "sandbox",
        }
        request = self.factory.post("/api/finance/mpesa/test-connection/", body, format="json")
        force_authenticate(request, user=self.user)
        request.tenant = MagicMock(schema_name="test_schema")
        return request

    def _call_view_with_token_mock(self, request, token_side_effect):
        from school.views import MpesaTestConnectionView
        from unittest.mock import patch

        with patch("django.core.cache.cache.get", return_value=None):
            with patch("django.core.cache.cache.set"):
                with patch("school.mpesa._get_access_token", side_effect=token_side_effect):
                    response = MpesaTestConnectionView.as_view()(request)
        return response

    def test_invalid_credentials_returns_400_with_credential_hint(self):
        err = MpesaError(
            "Invalid consumer key or secret — double-check your Daraja app "
            "credentials. Make sure you copied them from the correct Daraja "
            "app and haven't included extra spaces."
        )
        resp = self._call_view_with_token_mock(self._post(), err)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["success"])
        self.assertIn("consumer key or secret", resp.data["error"].lower())

    def test_connection_error_returns_400_with_reachability_message(self):
        err = MpesaError(
            "Could not reach Safaricom's Daraja service. "
            "Check your internet connection and try again."
        )
        resp = self._call_view_with_token_mock(self._post(), err)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["success"])
        self.assertIn("could not reach", resp.data["error"].lower())

    def test_timeout_returns_400_with_timeout_message(self):
        err = MpesaError(
            "The connection to Daraja timed out. "
            "Safaricom's servers may be slow — try again in a moment."
        )
        resp = self._call_view_with_token_mock(self._post(), err)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["success"])
        self.assertIn("timed out", resp.data["error"].lower())

    def test_rate_limit_returns_400_with_wait_message(self):
        err = MpesaError(
            "Daraja is temporarily rate-limiting requests. "
            "Wait a few minutes before testing again."
        )
        resp = self._call_view_with_token_mock(self._post(), err)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["success"])
        self.assertIn("rate-limiting", resp.data["error"].lower())

    def test_server_error_returns_400_with_safaricom_message(self):
        err = MpesaError(
            "Safaricom's Daraja service returned a server error. "
            "This is on Safaricom's side — try again in a few minutes."
        )
        resp = self._call_view_with_token_mock(self._post(), err)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["success"])
        self.assertIn("server error", resp.data["error"].lower())

    def test_environment_mismatch_returns_400_with_switch_hint(self):
        err = MpesaError(
            "Daraja could not find the requested resource. "
            "You selected the 'sandbox' environment — if your credentials "
            "belong to the Production app, please switch the environment "
            "setting to match."
        )
        resp = self._call_view_with_token_mock(self._post(), err)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["success"])
        self.assertIn("environment", resp.data["error"].lower())

    def test_successful_connection_returns_200_with_success_true(self):
        from school.views import MpesaTestConnectionView
        from unittest.mock import patch

        with patch("django.core.cache.cache.get", return_value=None):
            with patch("django.core.cache.cache.set"):
                with patch("school.mpesa._get_access_token", return_value="access_tok_ok"):
                    resp = MpesaTestConnectionView.as_view()(self._post())

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.assertIn("sandbox", resp.data["message"].lower())
