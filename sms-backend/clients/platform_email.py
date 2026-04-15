"""
clients/platform_email.py
--------------------------
Platform-level transactional email service for the Super Admin layer.

Covers the 7 email types defined in the SmartCampus Super Admin Spec §7:
  1.  welcome              — new tenant provisioned
  2.  trial_warning        — trial ends in N days
  3.  trial_expired        — trial period ended, account suspended
  4.  suspension           — tenant manually suspended by operator
  5.  reactivation         — tenant reactivated
  6.  invoice_issued       — new invoice generated
  7.  payment_receipt      — payment confirmed
  8.  password_reset       — operator-triggered admin password reset

Design rules (from spec):
  • Email failure MUST NOT raise to callers — log only, never break the request flow.
  • All emails are non-blocking (called after the DB transaction commits).
  • All emails use a consistent branded HTML template.
  • Resend is used when RESEND_API_KEY is set; falls back to Django's email backend.
  • Every call is logged at INFO level for auditability.

Usage:
  from clients.platform_email import platform_email
  platform_email.welcome(tenant, admin_email)
  platform_email.trial_warning(tenant, days_left=5)
  platform_email.trial_expired(tenant)
  platform_email.suspension(tenant, reason="Non-payment")
  platform_email.reactivation(tenant)
  platform_email.invoice_issued(tenant, invoice)
  platform_email.payment_receipt(tenant, invoice, receipt_number="MP-12345")
  platform_email.password_reset(admin_user, reset_url)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


# ── HTML template helpers ─────────────────────────────────────────────────────

_BRAND_COLOR = "#10b981"
_BRAND_NAME  = "SmartCampus"

def _html(title: str, body: str) -> str:
    """Minimal branded HTML email wrapper."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;">
    <tr><td align="center" style="padding:32px 16px;">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:8px;overflow:hidden;">
        <!-- Header -->
        <tr><td style="background:{_BRAND_COLOR};padding:24px 32px;">
          <span style="color:#fff;font-size:22px;font-weight:700;">{_BRAND_NAME}</span>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding:32px;color:#374151;font-size:15px;line-height:1.6;">
          {body}
        </td></tr>
        <!-- Footer -->
        <tr><td style="background:#f9fafb;padding:16px 32px;color:#9ca3af;font-size:12px;">
          &copy; {_BRAND_NAME} · This is an automated platform notification.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _btn(text: str, url: str) -> str:
    return (
        f'<p style="margin:24px 0 0;">'
        f'<a href="{url}" style="background:{_BRAND_COLOR};color:#fff;'
        f'padding:12px 24px;border-radius:6px;text-decoration:none;'
        f'font-weight:600;display:inline-block;">{text}</a></p>'
    )


def _portal_url(tenant) -> str:
    subdomain = getattr(tenant, "subdomain", "")
    base = os.environ.get("APP_URL", "https://rynatyschool.app")
    if subdomain:
        return f"https://{subdomain}.rynatyschool.app"
    return base


# ── Transport layer ───────────────────────────────────────────────────────────

def _send(to: str, subject: str, html: str) -> None:
    """
    Send a transactional email.
    Tries Resend first (if RESEND_API_KEY is set), falls back to Django email.
    Never raises — logs failures only.
    """
    from_name = os.environ.get("EMAIL_FROM_NAME", _BRAND_NAME)
    from_addr = os.environ.get(
        "EMAIL_FROM",
        os.environ.get("DEFAULT_FROM_EMAIL", f"noreply@rynatyschool.app"),
    )
    sender = f"{from_name} <{from_addr}>"

    # ── Try Resend ────────────────────────────────────────────────────────────
    resend_key = os.environ.get("RESEND_API_KEY", "")
    if resend_key:
        try:
            import resend as _resend
            _resend.api_key = resend_key
            _resend.Emails.send({
                "from": sender,
                "to": [to],
                "subject": subject,
                "html": html,
            })
            logger.info("[platform_email] Sent via Resend to=%s subject=%r", to, subject)
            return
        except Exception as exc:
            logger.warning("[platform_email] Resend failed, falling back: %s", exc)

    # ── Fallback: Django email backend ────────────────────────────────────────
    try:
        from django.core.mail import send_mail
        from django.utils.html import strip_tags
        send_mail(
            subject=subject,
            message=strip_tags(html),
            from_email=sender,
            recipient_list=[to],
            html_message=html,
            fail_silently=False,
        )
        logger.info("[platform_email] Sent via Django backend to=%s subject=%r", to, subject)
    except Exception as exc:
        logger.error(
            "[platform_email] FAILED to=%s subject=%r error=%s",
            to, subject, exc,
        )


# ── Email types ───────────────────────────────────────────────────────────────

class PlatformEmailService:
    """Provides the 7+ platform email types defined in the spec."""

    # 1. Welcome email — sent after new tenant is provisioned
    def welcome(self, tenant, admin_email: str, temp_password: str = "") -> None:
        portal = _portal_url(tenant)
        creds = ""
        if temp_password:
            creds = (
                f"<p><strong>Your temporary password:</strong> "
                f"<code style='background:#f3f4f6;padding:2px 6px;border-radius:4px;'>"
                f"{temp_password}</code><br>"
                f"<small style='color:#6b7280;'>Change this immediately after first login.</small></p>"
            )
        body = f"""
<h2 style="margin:0 0 16px;color:#111827;">Welcome to {_BRAND_NAME}, {tenant.name}!</h2>
<p>Your school management portal is ready. You have a <strong>14-day free trial</strong>
with full access to all modules.</p>
{creds}
<p>Login with: <code style='background:#f3f4f6;padding:2px 6px;border-radius:4px;'>{admin_email}</code></p>
{_btn("Access Your Portal →", portal)}
<p style="margin-top:24px;color:#6b7280;font-size:13px;">
  If you have any questions, reply to this email or contact support.
</p>"""
        subject = f"Welcome to {_BRAND_NAME} — Your school portal is ready"
        _send(admin_email, subject, _html(subject, body))

    # 2. Trial warning — sent when trial has N days left
    def trial_warning(self, tenant, days_left: int) -> None:
        if not getattr(tenant, "contact_email", ""):
            logger.warning("[platform_email] trial_warning: no contact_email for %s", tenant)
            return
        portal = _portal_url(tenant)
        trial_end = getattr(tenant, "trial_end", None)
        end_str = trial_end.strftime("%d %B %Y") if trial_end else "soon"
        body = f"""
<h2 style="margin:0 0 16px;color:#b45309;">Your trial ends in {days_left} day{"s" if days_left != 1 else ""}</h2>
<p>Your SmartCampus trial for <strong>{tenant.name}</strong> ends on <strong>{end_str}</strong>.</p>
<p>After your trial ends, your account will be suspended and you will lose access to all data.
Contact us now to upgrade and continue without interruption.</p>
{_btn("Upgrade Now →", portal + "/billing")}
<p style="color:#6b7280;font-size:13px;">
  To upgrade, contact your SmartCampus administrator or reply to this email.
</p>"""
        subject = f"Your {_BRAND_NAME} trial ends in {days_left} day{'s' if days_left != 1 else ''}"
        _send(tenant.contact_email, subject, _html(subject, body))

    # 3. Trial expired — sent when trial period ends and account is suspended
    def trial_expired(self, tenant) -> None:
        if not getattr(tenant, "contact_email", ""):
            return
        body = f"""
<h2 style="margin:0 0 16px;color:#dc2626;">Your trial has ended</h2>
<p>The 14-day free trial for <strong>{tenant.name}</strong> has ended and your account
has been <strong>suspended</strong>.</p>
<p>Your data is safely preserved. To restore access, contact us to subscribe to a paid plan.</p>
<p style="background:#fef2f2;border-left:4px solid #dc2626;padding:12px 16px;margin:16px 0;">
  <strong>Data retention:</strong> Your data will be retained for 30 days. After that it may be
  permanently deleted.
</p>
<p>Contact us immediately to avoid data loss: 
<a href="mailto:support@rynatyschool.app">support@rynatyschool.app</a></p>"""
        subject = f"Your {_BRAND_NAME} trial has ended — action required"
        _send(tenant.contact_email, subject, _html(subject, body))

    # 4. Suspension — sent when tenant is manually suspended by operator
    def suspension(self, tenant, reason: str = "") -> None:
        if not getattr(tenant, "contact_email", ""):
            return
        reason_html = ""
        if reason:
            reason_html = (
                f"<p><strong>Reason:</strong> {reason}</p>"
            )
        body = f"""
<h2 style="margin:0 0 16px;color:#dc2626;">Your account has been suspended</h2>
<p>Your {_BRAND_NAME} account for <strong>{tenant.name}</strong> has been suspended.</p>
{reason_html}
<p>To resolve this and restore access, please contact our support team:</p>
<p><a href="mailto:support@rynatyschool.app">support@rynatyschool.app</a></p>
<p style="color:#6b7280;font-size:13px;">
  Your data is safely preserved while your account is suspended.
</p>"""
        subject = f"Your {_BRAND_NAME} account has been suspended"
        _send(tenant.contact_email, subject, _html(subject, body))

    # 5. Reactivation — sent when a suspended tenant is restored
    def reactivation(self, tenant) -> None:
        if not getattr(tenant, "contact_email", ""):
            return
        portal = _portal_url(tenant)
        body = f"""
<h2 style="margin:0 0 16px;color:#059669;">Your account has been reactivated</h2>
<p>Great news! Your {_BRAND_NAME} account for <strong>{tenant.name}</strong> has been
reactivated and is fully operational.</p>
{_btn("Access Your Portal →", portal)}"""
        subject = f"Your {_BRAND_NAME} account is reactivated"
        _send(tenant.contact_email, subject, _html(subject, body))

    # 6. Invoice issued — sent when a new invoice is generated
    def invoice_issued(self, tenant, invoice) -> None:
        if not getattr(tenant, "contact_email", ""):
            return
        amount   = getattr(invoice, "total_amount", 0)
        inv_num  = getattr(invoice, "invoice_number", "—")
        due_date = getattr(invoice, "due_date", None)
        due_str  = due_date.strftime("%d %B %Y") if due_date else "—"
        currency = getattr(invoice, "currency", "KES")
        body = f"""
<h2 style="margin:0 0 16px;color:#111827;">Invoice {inv_num}</h2>
<p>A new invoice has been issued for your {_BRAND_NAME} subscription.</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0;">
  <tr style="border-bottom:1px solid #e5e7eb;">
    <td style="padding:8px 0;color:#6b7280;">Invoice number</td>
    <td style="padding:8px 0;font-weight:600;">{inv_num}</td>
  </tr>
  <tr style="border-bottom:1px solid #e5e7eb;">
    <td style="padding:8px 0;color:#6b7280;">Amount due</td>
    <td style="padding:8px 0;font-weight:600;">{currency} {amount:,.2f}</td>
  </tr>
  <tr>
    <td style="padding:8px 0;color:#6b7280;">Due date</td>
    <td style="padding:8px 0;font-weight:600;">{due_str}</td>
  </tr>
</table>
<p>Payment can be made via M-Pesa or bank transfer. Contact us for payment details.</p>"""
        subject = f"Invoice {inv_num} — {currency} {amount:,.2f} due {due_str}"
        _send(tenant.contact_email, subject, _html(subject, body))

    # 7. Payment receipt — sent when payment is confirmed
    def payment_receipt(
        self, tenant, invoice, receipt_number: str = "", method: str = "M-Pesa"
    ) -> None:
        if not getattr(tenant, "contact_email", ""):
            return
        amount   = getattr(invoice, "total_amount", 0)
        inv_num  = getattr(invoice, "invoice_number", "—")
        currency = getattr(invoice, "currency", "KES")
        receipt_html = ""
        if receipt_number:
            receipt_html = (
                f"<tr><td style='padding:8px 0;color:#6b7280;'>Receipt number</td>"
                f"<td style='padding:8px 0;font-weight:600;'>{receipt_number}</td></tr>"
            )
        body = f"""
<h2 style="margin:0 0 16px;color:#059669;">Payment confirmed ✓</h2>
<p>We have received your payment for {_BRAND_NAME} subscription.</p>
<table style="width:100%;border-collapse:collapse;margin:16px 0;">
  <tr style="border-bottom:1px solid #e5e7eb;">
    <td style="padding:8px 0;color:#6b7280;">Invoice</td>
    <td style="padding:8px 0;font-weight:600;">{inv_num}</td>
  </tr>
  <tr style="border-bottom:1px solid #e5e7eb;">
    <td style="padding:8px 0;color:#6b7280;">Amount paid</td>
    <td style="padding:8px 0;font-weight:600;">{currency} {amount:,.2f}</td>
  </tr>
  <tr style="border-bottom:1px solid #e5e7eb;">
    <td style="padding:8px 0;color:#6b7280;">Payment method</td>
    <td style="padding:8px 0;font-weight:600;">{method}</td>
  </tr>
  {receipt_html}
</table>
<p style="color:#059669;font-weight:600;">Your subscription is active. Thank you!</p>"""
        subject = f"Payment receipt — {inv_num} — {currency} {amount:,.2f}"
        _send(tenant.contact_email, subject, _html(subject, body))

    # 8. Password reset (operator-triggered — sends email, never sets directly)
    def password_reset(self, admin_user, reset_url: str) -> None:
        email = getattr(admin_user, "email", "") or getattr(admin_user, "work_email", "")
        if not email:
            logger.warning("[platform_email] password_reset: no email for user %s", admin_user)
            return
        username = getattr(admin_user, "username", str(admin_user))
        body = f"""
<h2 style="margin:0 0 16px;color:#111827;">Password reset request</h2>
<p>A password reset was requested for your {_BRAND_NAME} account
(<code style='background:#f3f4f6;padding:2px 6px;border-radius:4px;'>{username}</code>).</p>
<p>Click the button below to set a new password. This link is valid for <strong>1 hour</strong>.</p>
{_btn("Reset Password →", reset_url)}
<p style="color:#6b7280;font-size:13px;margin-top:24px;">
  If you did not request this reset, please contact your administrator immediately.
  This link will expire automatically.
</p>"""
        subject = f"Reset your {_BRAND_NAME} password"
        _send(email, subject, _html(subject, body))


# Singleton — import this everywhere
platform_email = PlatformEmailService()
