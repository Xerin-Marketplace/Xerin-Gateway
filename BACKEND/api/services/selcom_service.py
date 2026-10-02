"""Selcom API gateway client (checkout orders, USSD-push wallet pull, webhooks).

Docs: https://developers.selcommobile.com — every request is signed with
HMAC-SHA256 (Digest header) over `timestamp=<ts>&<signed fields>` using the
API secret; the API key is sent base64-encoded in `Authorization: SELCOM`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from api.config import settings

logger = logging.getLogger(__name__)


class SelcomConfigurationError(RuntimeError):
    pass


class SelcomAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True)
class SelcomResult:
    reference: str | None
    result: str | None
    resultcode: str | None
    message: str | None
    payment_gateway_url: str | None
    raw: dict[str, Any]


def normalize_msisdn(phone: str) -> str:
    """Selcom expects local/international digits like 255712345678."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if digits.startswith("00255"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = "255" + digits[1:]
    if not digits.startswith("255") or len(digits) < 12:
        raise ValueError("Provide a valid Tanzanian phone number (e.g. 0712345678)")
    return digits[:12]


def _b64(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


class SelcomClient:
    def __init__(self) -> None:
        self.base_url = settings.SELCOM_BASE_URL.rstrip("/")
        self.api_key = settings.SELCOM_API_KEY or ""
        self.api_secret = settings.SELCOM_API_SECRET or ""
        self.vendor = settings.selcom_vendor

    def _ensure_configured(self) -> None:
        if not self.api_key or not self.api_secret or not self.vendor:
            raise SelcomConfigurationError(
                "Selcom is not configured. Set SELCOM_API_KEY, SELCOM_API_SECRET and SELCOM_VENDOR_ID."
            )

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    @classmethod
    def compute_digest(cls, api_secret: str, timestamp: str, payload: dict[str, Any], signed_fields: list[str]) -> str:
        sign_data = f"timestamp={timestamp}" + "".join(f"&{f}={payload.get(f, '')}" for f in signed_fields)
        return base64.b64encode(
            hmac.new(api_secret.encode(), sign_data.encode(), hashlib.sha256).digest()
        ).decode()

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._ensure_configured()
        payload = payload or {}
        signed_fields = list(payload.keys())
        timestamp = self._timestamp()
        digest = self.compute_digest(self.api_secret, timestamp, payload, signed_fields)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"SELCOM {_b64(self.api_key)}",
            "Digest-Method": "HS256",
            "Digest": digest,
            "Timestamp": timestamp,
            "Signed-Fields": ",".join(signed_fields),
        }
        url = f"{self.base_url}{path}"
        try:
            if method == "GET":
                resp = requests.get(url, params=payload, headers=headers, timeout=settings.SELCOM_TIMEOUT_SECONDS)
            else:
                resp = requests.post(url, json=payload, headers=headers, timeout=settings.SELCOM_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise SelcomAPIError(f"Selcom request failed: {exc}") from exc

        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}

        if not resp.ok:
            raise SelcomAPIError(
                data.get("message") or f"Selcom HTTP {resp.status_code}",
                status_code=resp.status_code,
                payload=data,
            )
        result = str(data.get("result", "")).upper()
        if result == "FAIL":
            raise SelcomAPIError(data.get("message") or "Selcom transaction failed", status_code=resp.status_code, payload=data)
        return data

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------
    def create_order_minimal(
        self,
        *,
        order_id: str,
        amount: int | float | str,
        currency: str,
        buyer_email: str,
        buyer_name: str,
        buyer_phone: str,
        no_of_items: int = 1,
        merchant_remarks: str | None = None,
    ) -> SelcomResult:
        payload: dict[str, Any] = {
            "vendor": self.vendor,
            "order_id": order_id,
            "buyer_email": buyer_email or "customer@xerinmarketplace.com",
            "buyer_name": buyer_name or "Customer",
            "buyer_phone": normalize_msisdn(buyer_phone) if buyer_phone else "",
            "amount": str(int(float(amount))),
            "currency": currency or "TZS",
            "no_of_items": str(no_of_items or 1),
        }
        if settings.SELCOM_REDIRECT_URL:
            payload["redirect_url"] = _b64(settings.SELCOM_REDIRECT_URL)
        if settings.SELCOM_CANCEL_URL:
            payload["cancel_url"] = _b64(settings.SELCOM_CANCEL_URL)
        if settings.SELCOM_WEBHOOK_URL:
            payload["webhook"] = _b64(settings.SELCOM_WEBHOOK_URL)
        if merchant_remarks:
            payload["merchant_remarks"] = merchant_remarks
        payload["expiry"] = str(settings.SELCOM_ORDER_EXPIRY_MINUTES)

        data = self._request("POST", settings.SELCOM_CREATE_ORDER_PATH, payload)
        gateway_url = None
        try:
            first = (data.get("data") or [{}])[0]
            raw_url = first.get("payment_gateway_url")
            if raw_url:
                gateway_url = base64.b64decode(raw_url).decode()
        except Exception:
            gateway_url = None
        return SelcomResult(
            reference=data.get("reference"),
            result=data.get("result"),
            resultcode=data.get("resultcode"),
            message=data.get("message"),
            payment_gateway_url=gateway_url,
            raw=data,
        )

    def wallet_pull(self, *, transid: str, order_id: str, msisdn: str) -> SelcomResult:
        """Trigger a USSD push to the customer's mobile wallet (M-Pesa, Tigo, etc.)."""
        data = self._request(
            "POST",
            settings.SELCOM_WALLET_PAYMENT_PATH,
            {"transid": transid, "order_id": order_id, "msisdn": normalize_msisdn(msisdn)},
        )
        return SelcomResult(
            reference=data.get("reference"),
            result=data.get("result"),
            resultcode=data.get("resultcode"),
            message=data.get("message"),
            payment_gateway_url=None,
            raw=data,
        )

    def order_status(self, order_id: str) -> dict[str, Any]:
        """Poll a Selcom order status — needed because the webhook only fires on success."""
        return self._request("GET", settings.SELCOM_ORDER_STATUS_PATH, {"order_id": order_id})

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------
    def verify_webhook(self, *, timestamp: str | None, digest: str | None, signed_fields: str | None, payload: dict[str, Any]) -> bool:
        if not timestamp or not digest or not signed_fields:
            return False
        fields = [f.strip() for f in signed_fields.split(",") if f.strip()]
        expected = self.compute_digest(self.api_secret, timestamp, payload, fields)
        return hmac.compare_digest(expected, digest)
