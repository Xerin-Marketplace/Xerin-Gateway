import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


def base_url() -> str:
    env = os.getenv("PESAPAL_ENV", "sandbox").strip().lower()
    return "https://pay.pesapal.com/v3" if env == "live" else "https://cybqa.pesapal.com/pesapalv3"


def token() -> str:
    key = os.getenv("PESAPAL_CONSUMER_KEY", "").strip()
    secret = os.getenv("PESAPAL_CONSUMER_SECRET", "").strip()
    if not key or not secret:
        raise RuntimeError("Missing PESAPAL_CONSUMER_KEY or PESAPAL_CONSUMER_SECRET.")

    response = requests.post(
        f"{base_url()}/api/Auth/RequestToken",
        json={"consumer_key": key, "consumer_secret": secret},
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    access_token = data.get("token")
    if not access_token:
        raise RuntimeError(data.get("message") or f"Pesapal authentication failed: {data}")
    return access_token


def get_transaction_status(order_tracking_id: str) -> dict[str, Any]:
    response = requests.get(
        f"{base_url()}/api/Transactions/GetTransactionStatus",
        params={"orderTrackingId": order_tracking_id},
        headers={
            "Authorization": f"Bearer {token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
