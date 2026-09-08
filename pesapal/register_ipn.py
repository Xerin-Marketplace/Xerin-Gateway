import os
import requests
from dotenv import load_dotenv

load_dotenv()

ENV = os.getenv("PESAPAL_ENV", "sandbox").lower()
BASE_URL = (
    "https://pay.pesapal.com/v3"
    if ENV == "live"
    else "https://cybqa.pesapal.com/pesapalv3"
)

KEY = os.getenv("PESAPAL_CONSUMER_KEY", "").strip()
SECRET = os.getenv("PESAPAL_CONSUMER_SECRET", "").strip()
IPN_URL = os.getenv("PESAPAL_IPN_URL", "").strip()

if not KEY or not SECRET:
    raise SystemExit("Add PESAPAL_CONSUMER_KEY and PESAPAL_CONSUMER_SECRET to .env first.")

if not IPN_URL:
    raise SystemExit("Add a public HTTPS PESAPAL_IPN_URL to .env first.")

token_response = requests.post(
    f"{BASE_URL}/api/Auth/RequestToken",
    json={"consumer_key": KEY, "consumer_secret": SECRET},
    headers={"Accept": "application/json", "Content-Type": "application/json"},
    timeout=30,
)
token_response.raise_for_status()
token_data = token_response.json()
token = token_data.get("token")

if not token:
    raise SystemExit(f"Could not authenticate: {token_data}")

response = requests.post(
    f"{BASE_URL}/api/URLSetup/RegisterIPN",
    json={
        "url": IPN_URL,
        "ipn_notification_type": "GET",
    },
    headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    },
    timeout=30,
)
response.raise_for_status()

data = response.json()
print("\nPesapal IPN registration response:")
print(data)
print("\nCopy the returned ipn_id into PESAPAL_IPN_ID in your .env file.")
