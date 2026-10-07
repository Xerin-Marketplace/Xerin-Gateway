import smtplib
from email.message import EmailMessage
from typing import Optional
from api.config import settings

def send_email(to: str, subject: str, body: str, html: Optional[str] = None) -> None:
    """
    Simple SMTP sender using settings from api.config.settings.
    Required settings: EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FROM, EMAIL_USE_TLS (bool)
    """
    msg = EmailMessage()
    msg["From"] = getattr(settings, "EMAIL_FROM", settings.EMAIL_USER)
    msg["To"] = to
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
    use_tls = bool(getattr(settings, "EMAIL_USE_TLS", True))

    if use_tls:
        server = smtplib.SMTP(host, port, timeout=10)
        server.starttls()
    else:
        server = smtplib.SMTP(host, port, timeout=10)

    try:
        if user and password:
            server.login(user, password)
        server.send_message(msg)
    finally:
        server.quit()