from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.parse import urljoin

import requests

from api.config import settings
from api.services.payment_gateway import (
    GatewayInitiationResult, GatewayPaymentStatus, GatewayStatusResult,
    PaymentGatewayAPIError, PaymentGatewayConfigurationError, PaymentProvider,
)


class ZenoPayConfigurationError(PaymentGatewayConfigurationError):
    pass


class ZenoPayAPIError(PaymentGatewayAPIError):
    pass


class ZenoPayClient:
    """ZenoPay Tanzania MNO client using the current zenoapi.com contract."""

    provider = PaymentProvider.ZENOPAY

    def __init__(self) -> None:
        self.timeout = settings.ZENOPAY_TIMEOUT_SECONDS

    def _ensure_configured(self, *, require_webhook: bool = False) -> None:
        missing: list[str] = []
        if not settings.ZENOPAY_API_KEY:
            missing.append("ZENOPAY_API_KEY")
        if require_webhook and not settings.ZENOPAY_WEBHOOK_URL:
            missing.append("ZENOPAY_WEBHOOK_URL")
        if missing:
            raise ZenoPayConfigurationError(f"Missing ZenoPay settings: {', '.join(missing)}")

    @property
    def base_url(self) -> str:
        return settings.ZENOPAY_BASE_URL.rstrip("/") + "/"

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    @property
    def headers(self) -> dict[str, str]:
        self._ensure_configured()
        return {"Accept": "application/json", "Content-Type": "application/json",
                "x-api-key": str(settings.ZENOPAY_API_KEY)}

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = requests.request(method, self._url(path), headers=self.headers,
                                        timeout=self.timeout, **kwargs)
        except requests.exceptions.Timeout as exc:
            raise ZenoPayAPIError("ZenoPay request timed out. Please retry payment.",
                                  status_code=504, payload={"code": "provider_timeout"},
                                  retryable=True) from exc
        except requests.exceptions.ConnectionError as exc:
            raise ZenoPayAPIError("ZenoPay is temporarily unreachable. Please retry payment.",
                                  status_code=503, payload={"code": "provider_connection_error"},
                                  retryable=True) from exc
        except requests.exceptions.RequestException as exc:
            raise ZenoPayAPIError("ZenoPay communication failed. Please retry payment.",
                                  status_code=502, payload={"code": "provider_request_error"},
                                  retryable=True) from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise ZenoPayAPIError("ZenoPay returned a non-JSON response",
                                  status_code=response.status_code) from exc
        if not isinstance(data, dict):
            raise ZenoPayAPIError("ZenoPay returned an invalid response", status_code=response.status_code)
        if not response.ok:
            raise ZenoPayAPIError(str(data.get("message") or "ZenoPay request failed"),
                                  status_code=response.status_code, payload=data,
                                  retryable=response.status_code >= 500)
        return data

    @staticmethod
    def normalize_phone(value: str) -> str:
        digits = re.sub(r"\D", "", value or "")
        if digits.startswith("255") and len(digits) == 12:
            digits = "0" + digits[3:]
        elif digits.startswith("2550") and len(digits) == 13:
            digits = digits[3:]
        if len(digits) != 10 or not digits.startswith(("06", "07")):
            raise ValueError("ZenoPay buyer phone must be a Tanzanian 06XXXXXXXX or 07XXXXXXXX number")
        return digits

    @staticmethod
    def normalize_status(value: Any) -> GatewayPaymentStatus:
        raw = str(value or "").strip()
        normalized = re.sub(r"[^A-Z0-9]+", "_", raw.upper()).strip("_")
        words = set(filter(None, normalized.split("_")))

        # Exact / positive terminal states first.
        if normalized in {"COMPLETED", "SUCCESS", "SUCCESSFUL", "PAID"}:
            return GatewayPaymentStatus.COMPLETED

        # Provider cancellation is distinct from payment failure.
        if normalized in {"CANCELLED", "CANCELED"} or words.intersection(
            {"CANCELLED", "CANCELED"}
        ):
            return GatewayPaymentStatus.CANCELLED

        # ZenoPay/MNO responses are not always a single canonical status token.
        # Examples can include:
        #   UNPAID
        #   FAILED - INSUFFICIENT FUNDS
        #   INSUFFICIENT BALANCE
        #   TRANSACTION DECLINED
        # These are terminal results and must never remain PROCESSING.
        failure_tokens = {
            "FAILED",
            "FAILURE",
            "REJECTED",
            "DECLINED",
            "EXPIRED",
            "UNPAID",
            "INSUFFICIENT",
            "DENIED",
            "ERROR",
            "INVALID",
        }
        failure_phrases = (
            "INSUFFICIENT FUNDS",
            "INSUFFICIENT FUND",
            "INSUFFICIENT BALANCE",
            "NOT ENOUGH FUNDS",
            "NOT ENOUGH BALANCE",
            "TRANSACTION FAILED",
            "PAYMENT FAILED",
            "TRANSACTION DECLINED",
            "PAYMENT DECLINED",
            "PAYMENT REJECTED",
        )
        raw_upper = raw.upper()
        if words.intersection(failure_tokens) or any(
            phrase in raw_upper for phrase in failure_phrases
        ):
            return GatewayPaymentStatus.FAILED

        # Only genuine non-terminal states remain pending.
        pending_tokens = {
            "PENDING",
            "PROCESSING",
            "INITIATED",
            "CREATED",
            "QUEUED",
            "PROGRESS",
            "WAITING",
        }
        pending_phrases = (
            "IN PROGRESS",
            "REQUEST IN PROGRESS",
            "AWAITING PAYMENT",
            "AWAITING CONFIRMATION",
            "WAITING FOR CALLBACK",
            "CALLBACK SHORTLY",
        )
        if words.intersection(pending_tokens) or any(
            phrase in raw_upper for phrase in pending_phrases
        ):
            return GatewayPaymentStatus.PENDING

        return GatewayPaymentStatus.UNKNOWN

    @staticmethod
    def _amount_tzs(value: Decimal) -> int:
        amount = Decimal(value)
        if amount != amount.to_integral_value():
            raise ValueError("ZenoPay TZS amount must be a whole number")
        integer = int(amount)
        if integer < 1 or integer > settings.ZENOPAY_MAX_AMOUNT_TZS:
            raise ValueError(f"ZenoPay amount must be between 1 and {settings.ZENOPAY_MAX_AMOUNT_TZS:,} TZS")
        return integer

    def initiate_mobile_money(self, *, external_order_id: str, buyer_email: str,
                              buyer_name: str, buyer_phone: str, amount: Decimal,
                              metadata: Mapping[str, Any] | None = None,
                              webhook_url: str | None = None) -> GatewayInitiationResult:
        self._ensure_configured(require_webhook=webhook_url is None)
        order_id = str(external_order_id).strip()
        if not order_id or len(order_id) > 128:
            raise ValueError("ZenoPay order_id is required and must not exceed 128 characters")
        if not buyer_email or "@" not in buyer_email:
            raise ValueError("A valid buyer email is required by ZenoPay")
        if not buyer_name or not buyer_name.strip():
            raise ValueError("Buyer name is required by ZenoPay")
        callback_url = webhook_url or settings.ZENOPAY_WEBHOOK_URL
        if not callback_url or not callback_url.lower().startswith("https://"):
            raise ValueError("ZenoPay webhook URL must use HTTPS")
        payload = {"order_id": order_id, "buyer_email": buyer_email.strip(),
                   "buyer_name": buyer_name.strip(), "buyer_phone": self.normalize_phone(buyer_phone),
                   "amount": self._amount_tzs(amount), "webhook_url": callback_url,
                   "metadata": dict(metadata or {})}
        data = self._request("POST", settings.ZENOPAY_MNO_PAYMENT_PATH, json=payload)
        result_code = str(data.get("resultcode") or data.get("result_code") or "").strip()
        status = self.normalize_status(data.get("payment_status") or data.get("status"))
        message = str(data.get("message") or "").strip()
        message_key = message.casefold()

        # ZenoPay mobile-money initiation is asynchronous. Some accepted requests
        # are described as "request in progress / callback shortly" before the
        # provider exposes a final payment status. A USSD push can therefore be
        # sent even though the first API response is not a final SUCCESS.
        #
        # Treat only explicit rejection/failure signals as rejected. A known
        # pending/completed status or an in-progress/callback message is an
        # accepted initiation and must remain PROCESSING in Xerin.
        explicitly_rejected = (
            data.get("success") is False
            or status in {GatewayPaymentStatus.FAILED, GatewayPaymentStatus.CANCELLED}
        )
        async_accepted_message = any(
            phrase in message_key
            for phrase in (
                "in progress",
                "callback shortly",
                "request accepted",
                "request received",
                "processing",
                "initiated",
            )
        )
        accepted = (
            not explicitly_rejected
            and (
                result_code in {"", "000"}
                or status in {GatewayPaymentStatus.PENDING, GatewayPaymentStatus.COMPLETED}
                or async_accepted_message
            )
        )
        if accepted and status is GatewayPaymentStatus.UNKNOWN:
            status = GatewayPaymentStatus.PENDING
        reference = data.get("reference") or data.get("transaction_id") or data.get("transactionId")
        return GatewayInitiationResult(self.provider, accepted, order_id,
                                       str(reference) if reference is not None else None,
                                       status, message or None,
                                       data)

    def check_status(self, external_order_id: str) -> GatewayStatusResult:
        order_id = str(external_order_id).strip()
        if not order_id:
            raise ValueError("ZenoPay order_id is required")
        data = self._request("GET", settings.ZENOPAY_ORDER_STATUS_PATH, params={"order_id": order_id})
        if str(data.get("resultcode") or "") not in {"", "000"}:
            raise ZenoPayAPIError(str(data.get("message") or "ZenoPay order-status request failed"), payload=data)
        rows = data.get("data")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise ZenoPayAPIError("ZenoPay order-status response did not contain an order", payload=data)
        order = rows[0]
        amount: Decimal | None = None
        if order.get("amount") is not None:
            try:
                amount = Decimal(str(order["amount"]))
            except InvalidOperation:
                amount = None
        raw_status = order.get("payment_status") or order.get("status")
        raw_message = (
            order.get("message")
            or order.get("status_message")
            or order.get("description")
            or data.get("message")
        )
        normalized_status = self.normalize_status(raw_status)
        if normalized_status is GatewayPaymentStatus.UNKNOWN and raw_message:
            normalized_status = self.normalize_status(raw_message)

        reference = order.get("reference")
        raw_status_text = str(raw_status) if raw_status is not None else None
        if raw_message and (
            not raw_status_text
            or self.normalize_status(raw_status_text) is GatewayPaymentStatus.UNKNOWN
        ):
            raw_status_text = f"{raw_status_text or 'UNKNOWN'}: {raw_message}"

        return GatewayStatusResult(self.provider, str(order.get("order_id") or order_id),
                                   str(reference) if reference is not None else None,
                                   normalized_status, amount,
                                   str(order["channel"]) if order.get("channel") is not None else None,
                                   str(order["msisdn"]) if order.get("msisdn") is not None else None,
                                   raw_status_text, data)
