from typing import List
from api.config import settings

def send_sms(to: str, message: str):
    try:
        import africastalking
    except ImportError as e:
        raise RuntimeError("africastalking not installed") from e

    username = settings.AT_USERNAME
    api_key = settings.AT_API_KEY

    if not username or not api_key:
        raise RuntimeError("Missing AT_USERNAME / AT_API_KEY")

    africastalking.initialize(username, api_key)

    sms = africastalking.SMS
    recipients: List[str] = [to]
    
    sender_id = settings.AT_SENDER_ID

    response = sms.send(
        message,
        recipients,
        sender_id=sender_id if sender_id else None
)

    print("AFRICASTALKING RESPONSE:", response)

    return response