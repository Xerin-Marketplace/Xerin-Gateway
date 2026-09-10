from __future__ import annotations

import html as html_lib
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

from api.config import settings


def _clean_secret(value: str | None) -> str | None:
    """
    Gmail App Passwords are often copied with spaces for readability.
    SMTP expects the 16-character value without spaces.
    """
    if value is None:
        return None
    return value.strip().replace(" ", "")


def _require_email_settings() -> tuple[str, int, str | None, str | None]:
    host = (settings.EMAIL_HOST or "").strip()
    if not host:
        raise RuntimeError("EMAIL_HOST is not configured")

    port = int(settings.EMAIL_PORT)
    user = (settings.EMAIL_USER or "").strip() or None
    password = _clean_secret(settings.EMAIL_PASSWORD)

    if user and not password:
        raise RuntimeError("EMAIL_PASSWORD is not configured")

    return host, port, user, password


def send_email(
    to: str,
    subject: str,
    body: str,
    html: Optional[str] = None,
) -> None:
    """
    Send an email through the configured SMTP service.

    Supports:
    - STARTTLS, normally port 587
    - SMTP over SSL, normally port 465
    - Friendly From name such as "Xerin Market <no-reply@...>"
    """
    host, port, user, password = _require_email_settings()

    sender_email = (settings.EMAIL_FROM or user or "").strip()
    if not sender_email:
        raise RuntimeError("EMAIL_FROM or EMAIL_USER must be configured")

    sender_name = (getattr(settings, "EMAIL_FROM_NAME", None) or "Xerin Market").strip()

    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, sender_email))
    msg["To"] = to.strip()
    msg["Subject"] = subject
    msg["X-Auto-Response-Suppress"] = "OOF, AutoReply"

    reply_to = (getattr(settings, "EMAIL_REPLY_TO", None) or "").strip()
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.set_content(body)

    if html:
        msg.add_alternative(html, subtype="html")

    use_ssl = bool(getattr(settings, "EMAIL_USE_SSL", False))
    use_tls = bool(getattr(settings, "EMAIL_USE_TLS", True))

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=15)
    else:
        server = smtplib.SMTP(host, port, timeout=15)

    try:
        server.ehlo()

        if use_tls and not use_ssl:
            server.starttls()
            server.ehlo()

        if user and password:
            server.login(user, password)

        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            server.close()


def build_otp_email(
    *,
    otp: str,
    recipient_name: str | None = None,
    purpose: str = "account_verification",
    expires_minutes: int = 5,
) -> tuple[str, str, str]:
    """
    Return (subject, plain_text_body, html_body) for Xerin OTP messages.
    """
    safe_name = (recipient_name or "").strip()
    greeting_name = html_lib.escape(safe_name) if safe_name else "there"
    plain_greeting = safe_name or "there"
    otp_safe = html_lib.escape(str(otp))

    if purpose == "password_reset":
        subject = "Reset your Xerin Market password"
        title = "Password reset request"
        intro = (
            "We received a request to reset the password for your Xerin Market account."
        )
        action = "Use the verification code below to continue with your password reset."
    elif purpose == "register_seller":
        subject = "Verify your Xerin Market seller account"
        title = "Welcome to Xerin Market"
        intro = (
            "Thank you for registering as a seller with Xerin Market. "
            "We are pleased to have you with us."
        )
        action = (
            "Please use the verification code below to confirm your account "
            "and continue with seller onboarding."
        )
    else:
        subject = "Verify your Xerin Market account"
        title = "Welcome to Xerin Market"
        intro = (
            "Thank you for creating your Xerin Market account. "
            "We are glad to have you with us."
        )
        action = (
            "Please use the verification code below to confirm your account "
            "and complete your registration."
        )

    plain = f"""Hello {plain_greeting},

{intro}

{action}

Verification code: {otp}

This code will expire in {expires_minutes} minutes.

For your security, please do not share this code with anyone. If you did not request this code, you can safely ignore this email.

Warm regards,
Xerin Market Team
"""

    html_body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_lib.escape(subject)}</title>
</head>
<body style="margin:0;padding:0;background:#f6f7f9;font-family:Arial,Helvetica,sans-serif;color:#20242a;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f7f9;padding:32px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border:1px solid #eceff3;border-radius:18px;overflow:hidden;">
          <tr>
            <td style="background:#20242a;padding:24px 30px;">
              <div style="font-size:24px;font-weight:700;color:#ffffff;">
                <span style="color:#f47524;">Xerin</span> Market
              </div>
              <div style="margin-top:5px;font-size:12px;color:#c8cdd5;">Trusted marketplace experience</div>
            </td>
          </tr>

          <tr>
            <td style="padding:34px 30px 12px;">
              <div style="font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#f47524;">Account security</div>
              <h1 style="margin:8px 0 0;font-size:24px;line-height:1.3;color:#20242a;">{html_lib.escape(title)}</h1>
            </td>
          </tr>

          <tr>
            <td style="padding:8px 30px 0;font-size:15px;line-height:1.7;color:#555f6d;">
              <p style="margin:0 0 14px;">Hello {greeting_name},</p>
              <p style="margin:0 0 14px;">{html_lib.escape(intro)}</p>
              <p style="margin:0;">{html_lib.escape(action)}</p>
            </td>
          </tr>

          <tr>
            <td align="center" style="padding:26px 30px;">
              <div style="display:inline-block;min-width:220px;background:#fff7f0;border:1px solid #ffd9bb;border-radius:14px;padding:18px 24px;">
                <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#8b929d;">Verification code</div>
                <div style="margin-top:8px;font-size:34px;font-weight:800;letter-spacing:8px;color:#f47524;">{otp_safe}</div>
                <div style="margin-top:8px;font-size:12px;color:#7a838f;">Expires in {expires_minutes} minutes</div>
              </div>
            </td>
          </tr>

          <tr>
            <td style="padding:0 30px 30px;font-size:13px;line-height:1.7;color:#7a838f;">
              <div style="background:#f8fafc;border-radius:12px;padding:15px 16px;">
                For your security, please do not share this verification code with anyone.
                If you did not request it, you can safely ignore this email.
              </div>
            </td>
          </tr>

          <tr>
            <td style="border-top:1px solid #eceff3;padding:22px 30px;font-size:12px;line-height:1.6;color:#9aa2ad;">
              Warm regards,<br>
              <strong style="color:#59616d;">Xerin Market Team</strong>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return subject, plain, html_body


def send_otp_email(
    *,
    to: str,
    otp: str,
    recipient_name: str | None = None,
    purpose: str = "account_verification",
    expires_minutes: int = 5,
) -> None:
    subject, body, html = build_otp_email(
        otp=otp,
        recipient_name=recipient_name,
        purpose=purpose,
        expires_minutes=expires_minutes,
    )
    send_email(to=to, subject=subject, body=body, html=html)


def build_order_cancelled_payment_timeout_email(
    *,
    order_id: str,
    recipient_name: str | None,
    total: str,
    currency: str,
    timeout_minutes: int,
) -> tuple[str, str, str]:
    """Build the customer email sent after an unpaid checkout expires."""
    safe_name = (recipient_name or "").strip() or "Customer"
    subject = f"Order cancelled — payment not completed ({order_id[:8].upper()})"
    plain = f"""Hello {safe_name},

Your Xerin Market order {order_id} was automatically cancelled because payment was not confirmed within {timeout_minutes} minutes.

Order total: {currency} {total}
Order status: Cancelled
Payment status: Not completed

Any inventory reserved for this checkout has been released so the products can be purchased again.

If you still want these items, please return to Xerin Market and place a new order. You will never be charged by Xerin for an order unless the payment provider confirms the payment successfully.

Regards,
Xerin Market Team
"""
    html_body = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html_lib.escape(subject)}</title></head>
<body style="margin:0;background:#f6f7f9;font-family:Arial,Helvetica,sans-serif;color:#20242a;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:30px 12px;background:#f6f7f9;">
<tr><td align="center">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:620px;background:#fff;border:1px solid #eceff3;border-radius:18px;overflow:hidden;">
<tr><td style="background:#20242a;padding:22px 28px;color:#fff;font-size:24px;font-weight:700;"><span style="color:#f47524;">Xerin</span> Market</td></tr>
<tr><td style="padding:30px 28px 8px;">
<div style="font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#f47524;">Order update</div>
<h1 style="margin:8px 0 0;font-size:24px;">Order cancelled</h1>
</td></tr>
<tr><td style="padding:8px 28px 4px;font-size:15px;line-height:1.7;color:#59616d;">
<p>Hello {html_lib.escape(safe_name)},</p>
<p>Your order <strong>{html_lib.escape(order_id)}</strong> was automatically cancelled because payment was not confirmed within <strong>{timeout_minutes} minutes</strong>.</p>
</td></tr>
<tr><td style="padding:14px 28px;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#fff7f0;border:1px solid #ffd9bb;border-radius:12px;">
<tr><td style="padding:14px 16px;color:#7a838f;">Order total</td><td align="right" style="padding:14px 16px;font-weight:700;">{html_lib.escape(currency)} {html_lib.escape(total)}</td></tr>
<tr><td style="padding:0 16px 14px;color:#7a838f;">Status</td><td align="right" style="padding:0 16px 14px;font-weight:700;color:#b45309;">Cancelled</td></tr>
</table>
</td></tr>
<tr><td style="padding:8px 28px 28px;font-size:14px;line-height:1.7;color:#59616d;">
<p>The stock reserved for this checkout has been released. If you still want the products, please place a new order.</p>
<p style="margin-bottom:0;">Xerin only treats an online payment as successful after verified confirmation from the payment provider.</p>
</td></tr>
<tr><td style="border-top:1px solid #eceff3;padding:20px 28px;font-size:12px;color:#9aa2ad;">Regards,<br><strong>Xerin Market Team</strong></td></tr>
</table>
</td></tr></table>
</body></html>"""
    return subject, plain, html_body


def send_order_cancelled_payment_timeout_email(
    *,
    to: str,
    order_id: str,
    recipient_name: str | None,
    total: str,
    currency: str,
    timeout_minutes: int,
) -> None:
    subject, body, html = build_order_cancelled_payment_timeout_email(
        order_id=order_id,
        recipient_name=recipient_name,
        total=total,
        currency=currency,
        timeout_minutes=timeout_minutes,
    )
    send_email(to=to, subject=subject, body=body, html=html)
