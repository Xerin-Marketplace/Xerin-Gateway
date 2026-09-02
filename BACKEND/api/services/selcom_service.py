from __future__ import annotations

import base64
import hashlib
import hmac
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.parse import urljoin

import requests

from api.config import settings
from api.services.payment_gateway import (
    GatewayInitiationResult,
    GatewayPaymentStatus,
    GatewayStatusResult,
    PaymentGatewayAPIError,
    PaymentGatewayConfigurationError,
    PaymentProvider,
)


class SelcomConfigurationError(PaymentGatewayConfigurationError):
    pass


class SelcomAPIError(PaymentGatewayAPIError):
    pass


class SelcomClient:
    """Selcom Tanzania Checkout API client using API key + API secret (HS256)."""

    provider = PaymentProvider.SELCOM

    def __init__(self) -> None:
        self.timeout = settings.SELCOM_TIMEOUT_SECONDS

    def _ensure_configured(self, *, require_webhook: bool = False) -> None:
        missing: list[str] = []
        if not settings.SELCOM_API_KEY:
            missing.append("SELCOM_API_KEY")
        if not settings.SELCOM_API_SECRET:
            missing.append("SELCOM_API_SECRET")
        if not settings.SELCOM_VENDOR_ID:
            missing.append("SELCOM_VENDOR_ID")
        if require_webhook and not settings.SELCOM_WEBHOOK_URL:
            missing.append("SELCOM_WEBHOOK_URL")
        if missing:
            raise SelcomConfigurationError(
                f"Missing Selcom settings: {', '.join(missing)}"
            )

    @property
    def base_url(self) -> str:
        return settings.SELCOM_BASE_URL.rstrip("/") + "/"

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    @staticmethod
    def _timestamp() -> str:
        # Selcom examples use ISO-8601 timestamps with timezone.
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _headers(self, fields: Mapping[str, Any]) -> dict[str, str]:
        self._ensure_configured()
        timestamp = self._timestamp()
        signed_fields = ",".join(fields.keys())
        signing_string = "timestamp=" + timestamp
        if fields:
            signing_string += "&" + "&".join(
                f"{key}={value}" for key, value in fields.items()
            )
        digest = base64.b64encode(
            hmac.new(
                str(settings.SELCOM_API_SECRET).encode("utf-8"),
                signing_string.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("ascii")
        authorization = base64.b64encode(
            str(settings.SELCOM_API_KEY).encode("utf-8")
        ).decode("ascii")
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"SELCOM {authorization}",
            "Digest-Method": "HS256",
            "Digest": digest,
            "Timestamp": timestamp,
            "Signed-Fields": signed_fields,
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        fields: Mapping[str, Any],
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if method.upper() == "GET":
            kwargs["params"] = dict(fields)
        else:
            kwargs["json"] = dict(fields)
        try:
            response = requests.request(
                method,
                self._url(path),
                headers=self._headers(fields),
                timeout=self.timeout,
                **kwargs,
            )
        except requests.exceptions.Timeout as exc:
            raise SelcomAPIError(
                "Selcom request timed out. Please retry payment.",
                status_code=504,
                payload={"code": "provider_timeout"},
                retryable=True,
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise SelcomAPIError(
                "Selcom is temporarily unreachable. Please retry payment.",
                status_code=503,
                payload={"code": "provider_connection_error"},
                retryable=True,
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise SelcomAPIError(
                "Selcom communication failed. Please retry payment.",
                status_code=502,
                payload={"code": "provider_request_error"},
                retryable=True,
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise SelcomAPIError(
                "Selcom returned a non-JSON response",
                status_code=response.status_code,
            ) from exc
        if not isinstance(data, dict):
            raise SelcomAPIError(
                "Selcom returned an invalid response",
                status_code=response.status_code,
            )
        if not response.ok:
            raise SelcomAPIError(
                str(data.get("message") or "Selcom request failed"),
                status_code=response.status_code,
                payload=data,
                retryable=response.status_code >= 500,
            )
        return data

    @staticmethod
    def normalize_phone(value: str) -> str:
        digits = re.sub(r"\D", "", value or "")
        if digits.startswith("0") and len(digits) == 10:
            digits = "255" + digits[1:]
        elif digits.startswith("2550") and len(digits) == 13:
            digits = "255" + digits[4:]
        if len(digits) != 12 or not digits.startswith("255"):
            raise ValueError(
                "Selcom mobile number must be a Tanzanian number such as 2557XXXXXXXX"
            )
        return digits

    @staticmethod
    def normalize_status(value: Any) -> GatewayPaymentStatus:
        raw = str(value or "").strip().upper().replace(" ", "_")
        if raw in {"COMPLETED", "SUCCESS", "SUCCESSFUL", "PAID"}:
            return GatewayPaymentStatus.COMPLETED
        if raw in {"CANCELLED", "CANCELED", "USERCANCELLED", "USER_CANCELLED"}:
            return GatewayPaymentStatus.CANCELLED
        if raw in {"FAILED", "FAIL", "FAILURE", "REJECTED", "DECLINED", "EXPIRED"}:
            return GatewayPaymentStatus.FAILED
        if raw in {"PENDING", "PROCESSING", "INPROGRESS", "IN_PROGRESS", "AMBIGUOUS", "AMBIGOUS"}:
            return GatewayPaymentStatus.PENDING
        return GatewayPaymentStatus.UNKNOWN

    @staticmethod
    def _amount_tzs(value: Decimal) -> int:
        amount = Decimal(value)
        if amount != amount.to_integral_value():
            raise ValueError("Selcom TZS amount must be a whole number")
        integer = int(amount)
        if integer < 1 or integer > settings.SELCOM_MAX_AMOUNT_TZS:
            raise ValueError(
                f"Selcom amount must be between 1 and {settings.SELCOM_MAX_AMOUNT_TZS:,} TZS"
            )
        return integer

    @staticmethod
    def _encoded_url(value: str) -> str:
        return base64.b64encode(value.encode("utf-8")).decode("ascii")

    def initiate_mobile_money(
        self,
        *,
        external_order_id: str,
        buyer_email: str,
        buyer_name: str,
        buyer_phone: str,
        amount: Decimal,
        metadata: Mapping[str, Any] | None = None,
        webhook_url: str | None = None,
    ) -> GatewayInitiationResult:
        self._ensure_configured(require_webhook=webhook_url is None)
        order_id = str(external_order_id).strip()
        if not order_id or len(order_id) > 128:
            raise ValueError("Selcom order_id is required and must not exceed 128 characters")
        if not buyer_email or "@" not in buyer_email:
            raise ValueError("A valid buyer email is required by Selcom")
        if not buyer_name or not buyer_name.strip():
            raise ValueError("Buyer name is required by Selcom")
        phone = self.normalize_phone(buyer_phone)
        callback_url = webhook_url or settings.SELCOM_WEBHOOK_URL
        if callback_url and not callback_url.lower().startswith("https://"):
            raise ValueError("Selcom webhook URL must use HTTPS")

        create_fields: dict[str, Any] = {
            "vendor": str(settings.SELCOM_VENDOR_ID),
            "order_id": order_id,
            "buyer_email": buyer_email.strip(),
            "buyer_name": buyer_name.strip(),
            "buyer_phone": phone,
            "amount": self._amount_tzs(amount),
            "currency": "TZS",
        }
        if callback_url:
            create_fields["webhook"] = self._encoded_url(callback_url)
        create_fields.update(
            {
                "buyer_remarks": f"Xerin order {dict(metadata or {}).get('order_id', '')}".strip(),
                "merchant_remarks": f"Xerin payment {order_id}",
                "no_of_items": 1,
            }
        )
        created = self._request(
            "POST",
            settings.SELCOM_CREATE_ORDER_PATH,
            fields=create_fields,
        )
        if str(created.get("resultcode") or "") != "000" or str(
            created.get("result") or ""
        ).upper() != "SUCCESS":
            return GatewayInitiationResult(
                self.provider,
                False,
                order_id,
                str(created.get("reference")) if created.get("reference") else None,
                self.normalize_status(created.get("result")),
                str(created.get("message") or "Selcom order creation failed"),
                {"create_order": created},
            )

        transid = f"XRN{order_id.replace('-', '')[:24]}"
        wallet_fields: dict[str, Any] = {
            "transid": transid,
            "order_id": order_id,
            "msisdn": phone,
        }
        wallet = self._request(
            "POST",
            settings.SELCOM_WALLET_PAYMENT_PATH,
            fields=wallet_fields,
        )
        raw = {"create_order": created, "wallet_payment": wallet, "transid": transid}
        result_code = str(wallet.get("resultcode") or "").strip()
        result_name = str(wallet.get("result") or "").strip()
        status = self.normalize_status(
            wallet.get("payment_status") or result_name or wallet.get("message")
        )
        accepted = result_code in {"000", "111", "927", "999"} or status in {
            GatewayPaymentStatus.PENDING,
            GatewayPaymentStatus.COMPLETED,
        }
        if accepted and status is GatewayPaymentStatus.UNKNOWN:
            status = GatewayPaymentStatus.PENDING
        reference = wallet.get("reference") or created.get("reference") or transid
        return GatewayInitiationResult(
            self.provider,
            accepted,
            order_id,
            str(reference) if reference is not None else None,
            status,
            str(wallet.get("message") or created.get("message") or "") or None,
            raw,
        )

    def check_status(self, external_order_id: str) -> GatewayStatusResult:
        self._ensure_configured()
        order_id = str(external_order_id).strip()
        if not order_id:
            raise ValueError("Selcom order_id is required")

        data = self._request(
            "GET",
            settings.SELCOM_ORDER_STATUS_PATH,
            fields={"order_id": order_id},
        )
        if str(data.get("resultcode") or "") not in {"", "000"}:
            raise SelcomAPIError(
                str(data.get("message") or "Selcom order-status request failed"),
                payload=data,
            )
        rows = data.get("data")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise SelcomAPIError(
                "Selcom order-status response did not contain an order",
                payload=data,
            )
        order = rows[0]
        amount: Decimal | None = None
        if order.get("amount") is not None:
            try:
                amount = Decimal(str(order["amount"]))
            except InvalidOperation:
                amount = None
        raw_status = str(order.get("payment_status") or "").strip().upper()
        status = self.normalize_status(raw_status)
        reference = (
            order.get("transid")
            or order.get("reference")
            or data.get("reference")
        )
        return GatewayStatusResult(
            self.provider,
            str(order.get("order_id") or order_id),
            str(reference) if reference is not None else None,
            status,
            amount,
            str(order.get("channel")) if order.get("channel") is not None else None,
            str(order.get("msisdn") or order.get("phone"))
            if (order.get("msisdn") is not None or order.get("phone") is not None)
            else None,
            raw_status or None,
            data,
        )
