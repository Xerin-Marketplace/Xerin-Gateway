from typing import List
from api.config import settings

def send_sms(to: str, message: str) -> None:
    """
    Send SMS via Africa's Talking Python SDK.
    Required settings: AT_USERNAME, AT_API_KEY
    Install: pip install africastalking
    """
    try:
        import africastalking
    except ImportError as e:
        raise RuntimeError("africastalking package not installed. pip install africastalking") from e

    username = settings.AT_USERNAME
    api_key = settings.AT_API_KEY
    if not username or not api_key:
        raise RuntimeError("Africa's Talking credentials missing in settings (AT_USERNAME/AT_API_KEY)")

    africastalking.initialize(username, api_key)
    sms = africastalking.SMS
    # africastalking expects list of recipients
    recipients: List[str] = [to]
    # send (raises exception on failure)
    response = sms.send(message, recipients)
    # optionally inspect response for delivery info
    return response
