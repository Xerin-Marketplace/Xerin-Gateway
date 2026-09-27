import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

from api.config import settings


def send_email(to: str, subject: str, body: str, html: Optional[str] = None) -> None:
    """SMTP sender honoring EMAIL_USE_SSL (465) and EMAIL_USE_TLS (587).

    Required settings: EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD,
    EMAIL_FROM, plus one of EMAIL_USE_SSL / EMAIL_USE_TLS.
    """
    from_addr = getattr(settings, "EMAIL_FROM", None) or settings.EMAIL_USER
    from_name = getattr(settings, "EMAIL_FROM_NAME", None)

    msg = EmailMessage()
    msg["From"] = formataddr((from_name, from_addr)) if from_name else from_addr
    msg["To"] = to
    reply_to = getattr(settings, "EMAIL_REPLY_TO", None)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["Subject"] = subject
    if html:
        msg.set_content(body)
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(body)

    host = settings.EMAIL_HOST
    port = int(getattr(settings, "EMAIL_PORT", 587))
    user = getattr(settings, "EMAIL_USER", None)
    password = getattr(settings, "EMAIL_PASSWORD", None)
    use_ssl = bool(getattr(settings, "EMAIL_USE_SSL", False))
    use_tls = bool(getattr(settings, "EMAIL_USE_TLS", True)) and not use_ssl

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=10)
    else:
        server = smtplib.SMTP(host, port, timeout=10)
        if use_tls:
            server.starttls()

    try:
        if user and password:
            server.login(user, password)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            server.close()
