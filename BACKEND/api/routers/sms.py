from __future__ import annotations

import re
from typing import List

from api.config import settings


def normalize_phone_number(phone: str) -> str:
    """
    Convert common Tanzania phone formats to Africa's Talking E.164 format.

    Examples:
      255694021848  -> +255694021848
      0694021848    -> +255694021848
      +255694021848 -> +255694021848
      00255694021848 -> +255694021848
    """
    raw = (phone or "").strip()
    if not raw:
        raise ValueError("Phone number is required")

    # Keep only digits and an optional leading +
    raw = re.sub(r"[^\d+]", "", raw)

    if raw.startswith("00"):
        raw = f"+{raw[2:]}"

    if raw.startswith("+"):
        normalized = raw
    elif raw.startswith("255"):
        normalized = f"+{raw}"
    elif raw.startswith("0"):
        country_code = (
            getattr(settings, "SMS_DEFAULT_COUNTRY_CODE", "+255") or "+255"
        ).strip()
        if not country_code.startswith("+"):
            country_code = f"+{country_code}"
        normalized = f"{country_code}{raw[1:]}"
    else:
        country_code = (
            getattr(settings, "SMS_DEFAULT_COUNTRY_CODE", "+255") or "+255"
        ).strip()
        if not country_code.startswith("+"):
            country_code = f"+{country_code}"
        normalized = f"{country_code}{raw}"

    if not re.fullmatch(r"\+\d{10,15}", normalized):
        raise ValueError(f"Invalid phone number: {phone}")

    return normalized


def send_sms(to: str, message: str):
    try:
        import africastalking
    except ImportError as exc:
        raise RuntimeError("africastalking not installed") from exc

    username = settings.AT_USERNAME
    api_key = settings.AT_API_KEY

    if not username or not api_key:
        raise RuntimeError("Missing AT_USERNAME / AT_API_KEY")

    normalized_phone = normalize_phone_number(to)

    africastalking.initialize(username, api_key)

    sms = africastalking.SMS
    recipients: List[str] = [normalized_phone]

    sender_id = settings.AT_SENDER_ID

    response = sms.send(
        message,
        recipients,
        sender_id=sender_id if sender_id else None,
    )

    return response
