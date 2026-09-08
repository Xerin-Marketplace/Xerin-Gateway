import os
import uuid
from typing import Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

def base_url() -> str:
    env = os.getenv("PESAPAL_ENV", "sandbox").strip().lower()

    if env == "live":
        return "https://pay.pesapal.com/v3"

    return "https://cybqa.pesapal.com/pesapalv3"


def callback_url() -> str:
    return os.getenv(
        "PESAPAL_CALLBACK_URL",
        "https://api.xerinmarketplace.com/pesapal-demo/",
    ).strip()


def ipn_id() -> str:
    value = os.getenv("PESAPAL_IPN_ID", "").strip()

    if not value:
        raise RuntimeError(
            "Missing PESAPAL_IPN_ID. "
            "Register the IPN URL and add the returned IPN ID to .env."
        )

    return value


# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------

def token() -> str:
    key = os.getenv("PESAPAL_CONSUMER_KEY", "").strip()
    secret = os.getenv("PESAPAL_CONSUMER_SECRET", "").strip()

    if not key or not secret:
        raise RuntimeError(
            "Missing PESAPAL_CONSUMER_KEY or PESAPAL_CONSUMER_SECRET."
        )

    response = requests.post(
        f"{base_url()}/api/Auth/RequestToken",
        json={
            "consumer_key": key,
            "consumer_secret": secret,
        },
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    access_token = data.get("token")

    if not access_token:
        raise RuntimeError(
            data.get("message")
            or f"Payment authentication failed: {data}"
        )

    return access_token


# ---------------------------------------------------------
# Create COLAB package subscription payment
# ---------------------------------------------------------

def submit_order(
    amount: float,
    package_name: str,
    email: str,
    first_name: str = "",
    last_name: str = "",
    phone_number: str = "",
    currency: str = "TZS",
    order_id: Optional[str] = None,
) -> dict[str, Any]:

    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    if not email:
        raise ValueError("Customer email is required.")

    package_name = package_name.strip() or "Package"

    # Customer-friendly COLAB reference
    if not order_id:
        order_id = f"COLAB-{uuid.uuid4().hex[:12].upper()}"

    # This is the merchant-controlled description sent with the payment.
    description = (
        f"COLAB {package_name} Package Subscription"
    )

    payload = {
        "id": order_id,
        "currency": currency,
        "amount": float(amount),

        # Customer-facing merchant description
        "description": description,

        "callback_url": callback_url(),

        # Required registered notification ID
        "notification_id": ipn_id(),

        "billing_address": {
            "email_address": email,
            "phone_number": phone_number,
            "country_code": "TZ",
            "first_name": first_name,
            "middle_name": "",
            "last_name": last_name,
            "line_1": "",
            "line_2": "",
            "city": "",
            "state": "",
            "postal_code": "",
            "zip_code": "",
        },
    }

    response = requests.post(
        f"{base_url()}/api/Transactions/SubmitOrderRequest",
        json=payload,
        headers={
            "Authorization": f"Bearer {token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("error"):
        raise RuntimeError(
            f"Could not create COLAB subscription payment: {data['error']}"
        )

    if not data.get("redirect_url"):
        raise RuntimeError(
            f"Payment provider did not return a checkout URL: {data}"
        )

    return data


# ---------------------------------------------------------
# Verify transaction
# ---------------------------------------------------------

def get_transaction_status(
    order_tracking_id: str,
) -> dict[str, Any]:

    if not order_tracking_id:
        raise ValueError("order_tracking_id is required.")

    response = requests.get(
        f"{base_url()}/api/Transactions/GetTransactionStatus",
        params={
            "orderTrackingId": order_tracking_id,
        },
        headers={
            "Authorization": f"Bearer {token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()