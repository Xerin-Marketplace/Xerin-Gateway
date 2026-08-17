from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import requests

from api.config import settings


class AzamPayConfigurationError(RuntimeError):
    pass


class AzamPayAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: dict[str, Any] | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}
        self.retryable = retryable


@dataclass(frozen=True)
class AzamPayResult:
    success: bool
    transaction_id: str | None
    message: str | None
    checkout_url: str | None
    raw: dict[str, Any]


class AzamPayClient:
    """Small AzamPay client for MNO push checkout and hosted card checkout.

    Card details never pass through Xerin. Card payment uses AzamPay's hosted
    checkout URL, which keeps cardholder data outside this backend.
    """

    _token: str | None = None
    _token_expires_at: float = 0
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.timeout = settings.AZAMPAY_TIMEOUT_SECONDS

    def _ensure_configured(self) -> None:
        missing = [
            name
            for name, value in {
                "AZAMPAY_APP_NAME": settings.AZAMPAY_APP_NAME,
                "AZAMPAY_CLIENT_ID": settings.AZAMPAY_CLIENT_ID,
                "AZAMPAY_CLIENT_SECRET": settings.AZAMPAY_CLIENT_SECRET,
            }.items()
            if not value
        ]
        if settings.AZAMPAY_SANDBOX and not settings.AZAMPAY_API_KEY:
            missing.append("AZAMPAY_API_KEY")
        if missing:
            raise AzamPayConfigurationError(f"Missing AzamPay settings: {', '.join(missing)}")

    @property
    def auth_url(self) -> str:
        return (
            settings.AZAMPAY_SANDBOX_AUTH_URL
            if settings.AZAMPAY_SANDBOX
            else settings.AZAMPAY_LIVE_AUTH_URL
        )

    @property
    def base_url(self) -> str:
        return (
            settings.AZAMPAY_SANDBOX_BASE_URL
            if settings.AZAMPAY_SANDBOX
            else settings.AZAMPAY_LIVE_BASE_URL
        ).rstrip("/")

    def _request(
        self,
        method: str,
        url: str,
        *,
        json_payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        try:
            return requests.request(
                method,
                url,
                json=json_payload,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise AzamPayAPIError(
                "AzamPay request timed out. Please retry payment.",
                status_code=504,
                payload={"code": "provider_timeout"},
                retryable=True,
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise AzamPayAPIError(
                "AzamPay is temporarily unreachable. Please retry payment.",
                status_code=503,
                payload={"code": "provider_connection_error"},
                retryable=True,
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise AzamPayAPIError(
                "AzamPay communication failed. Please retry payment.",
                status_code=502,
                payload={"code": "provider_request_error"},
                retryable=True,
            ) from exc

    def _json_response(self, response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise AzamPayAPIError(
                "AzamPay returned a non-JSON response",
                status_code=response.status_code,
            ) from exc
        if not isinstance(data, dict):
            raise AzamPayAPIError("AzamPay returned an invalid response", status_code=response.status_code)
        return data

    def get_token(self, *, force_refresh: bool = False) -> str:
        self._ensure_configured()
        now = time.time()
        if not force_refresh and self.__class__._token and now < self.__class__._token_expires_at:
            return self.__class__._token

        with self.__class__._lock:
            now = time.time()
            if not force_refresh and self.__class__._token and now < self.__class__._token_expires_at:
                return self.__class__._token

            response = self._request(
                "POST",
                self.auth_url,
                json_payload={
                    "appName": settings.AZAMPAY_APP_NAME,
                    "clientId": settings.AZAMPAY_CLIENT_ID,
                    "clientSecret": settings.AZAMPAY_CLIENT_SECRET,
                },
            )
            data = self._json_response(response)
            if not response.ok:
                raise AzamPayAPIError(
                    data.get("message") or "AzamPay authentication failed",
                    status_code=response.status_code,
                    payload=data,
                )

            token = data.get("data", {}).get("accessToken") or data.get("accessToken")
            if not token:
                raise AzamPayAPIError("AzamPay authentication response did not contain an access token", payload=data)

            # AzamPay returns an expiry value in different formats across API versions.
            # Cache conservatively for 45 minutes and refresh once after a 401.
            self.__class__._token = str(token)
            self.__class__._token_expires_at = time.time() + 45 * 60
            return str(token)

    def _headers(self, token: str) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if settings.AZAMPAY_API_KEY:
            headers["X-API-Key"] = settings.AZAMPAY_API_KEY
        return headers

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = self.get_token()
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = self._request(
            "POST",
            url,
            json_payload=payload,
            headers=self._headers(token),
        )
        if response.status_code == 401:
            token = self.get_token(force_refresh=True)
            response = self._request(
                "POST",
                url,
                json_payload=payload,
                headers=self._headers(token),
            )
        data = self._json_response(response)
        if not response.ok or data.get("success") is False:
            raise AzamPayAPIError(
                data.get("message") or data.get("msg") or "AzamPay request failed",
                status_code=response.status_code,
                payload=data,
                retryable=response.status_code >= 500,
            )
        return data

    def _get(self, path: str) -> requests.Response:
        token = self.get_token()
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = self._request(
            "GET",
            url,
            headers=self._headers(token),
        )
        if response.status_code == 401:
            token = self.get_token(force_refresh=True)
            response = self._request(
                "GET",
                url,
                headers=self._headers(token),
            )
        return response

    def payment_partners(self) -> list[dict[str, Any]]:
        """Return payment partners registered for the authenticated merchant."""
        response = self._get(settings.AZAMPAY_PAYMENT_PARTNERS_PATH)

        try:
            data = response.json()
        except ValueError as exc:
            raise AzamPayAPIError(
                "AzamPay payment-partners endpoint returned a non-JSON response",
                status_code=response.status_code,
            ) from exc

        if not response.ok:
            message = "AzamPay payment-partners request failed"
            payload: dict[str, Any] = {}
            if isinstance(data, dict):
                payload = data
                message = (
                    data.get("message")
                    or data.get("msg")
                    or message
                )
            raise AzamPayAPIError(
                message,
                status_code=response.status_code,
                payload=payload,
                retryable=response.status_code >= 500,
            )

        if not isinstance(data, list):
            raise AzamPayAPIError(
                "AzamPay payment-partners response was not a list",
                status_code=response.status_code,
            )

        safe_rows: list[dict[str, Any]] = []
        for row in data:
            if not isinstance(row, dict):
                continue
            safe_rows.append(
                {
                    "logoUrl": row.get("logoUrl"),
                    "partnerName": row.get("partnerName"),
                    "provider": row.get("provider"),
                    "vendorName": row.get("vendorName"),
                    "paymentVendorId": row.get("paymentVendorId"),
                    "paymentPartnerId": row.get("paymentPartnerId"),
                    "currency": row.get("currency"),
                }
            )
        return safe_rows

    @staticmethod
    def normalize_mno(provider: str) -> str:
        normalized = provider.lower().replace(" ", "").replace("_", "").replace("-", "")
        mapping = {
            "airtel": "Airtel",
            "airtelmoney": "Airtel",
            "tigo": "Tigo",
            "tigopesa": "Tigo",
            "mixx": "Tigo",
            "mixxbyyas": "Tigo",
            "halopesa": "Halopesa",
            "halo": "Halopesa",
            "azampesa": "Azampesa",
            "azam": "Azampesa",
            "mpesa": "Mpesa",
            "vodacom": "Mpesa",
        }
        if normalized not in mapping:
            raise ValueError("Unsupported AzamPay MNO. Use Airtel, Tigo/Mixx, Halopesa, Azampesa, or Mpesa/Vodacom")
        return mapping[normalized]

    @staticmethod
    def normalize_msisdn(phone_number: str) -> str:
        """Return an AzamPay-friendly MSISDN containing digits only."""
        value = (phone_number or "").strip().replace(" ", "").replace("-", "")
        if value.startswith("+"):
            value = value[1:]
        if not value.isdigit() or not 7 <= len(value) <= 15:
            raise ValueError("Mobile-money phone number must contain 7 to 15 digits")
        return value

    @staticmethod
    def _json_number(amount: Decimal) -> int | float:
        """AzamPay documents MNO amount as a JSON number, not a JSON string."""
        value = Decimal(amount)
        if not value.is_finite():
            raise ValueError("Payment amount must be a finite number")
        if value < 0 or value > Decimal("5000000"):
            raise ValueError("AzamPay MNO amount must be between 0 and 5,000,000")
        if value == value.to_integral_value():
            return int(value)
        return float(value)

    @staticmethod
    def _validate_additional_properties(value: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(encoded) > 4096:
            raise ValueError("AzamPay additionalProperties must not exceed 4096 bytes")
        return value

    def mobile_checkout(
        self,
        *,
        amount: Decimal,
        currency: str,
        phone_number: str,
        provider: str,
        external_id: str,
        additional_properties: dict[str, Any] | None = None,
    ) -> AzamPayResult:
        normalized_currency = (currency or "").strip().upper()
        if not normalized_currency or len(normalized_currency) > 32:
            raise ValueError("AzamPay currency is required and must not exceed 32 characters")

        normalized_external_id = (external_id or "").strip()
        if not normalized_external_id:
            raise ValueError("AzamPay externalId is required")
        if len(normalized_external_id) > 128:
            raise ValueError("AzamPay externalId must not exceed 128 characters")

        properties = self._validate_additional_properties(additional_properties or {})

        data = self._post(
            settings.AZAMPAY_MNO_CHECKOUT_PATH,
            {
                "accountNumber": self.normalize_msisdn(phone_number),
                "amount": self._json_number(amount),
                "currency": normalized_currency,
                "externalId": normalized_external_id,
                "provider": self.normalize_mno(provider),
                "additionalProperties": properties,
            },
        )
        return AzamPayResult(
            success=bool(data.get("success", True)),
            transaction_id=data.get("transactionId"),
            message=data.get("message"),
            checkout_url=None,
            raw=data,
        )

    def card_checkout(
        self,
        *,
        amount: Decimal,
        currency: str,
        external_id: str,
        success_url: str,
        failure_url: str,
        cart: dict[str, Any],
    ) -> AzamPayResult:
        if not settings.AZAMPAY_VENDOR_ID:
            raise AzamPayConfigurationError("AZAMPAY_VENDOR_ID is required for hosted card checkout")
        request_origin = settings.AZAMPAY_REQUEST_ORIGIN or settings.PUBLIC_BASE_URL
        if not request_origin:
            raise AzamPayConfigurationError("AZAMPAY_REQUEST_ORIGIN or PUBLIC_BASE_URL is required for card checkout")

        data = self._post(
            settings.AZAMPAY_POST_CHECKOUT_PATH,
            {
                "appName": settings.AZAMPAY_APP_NAME,
                "clientId": settings.AZAMPAY_CLIENT_ID,
                "vendorId": settings.AZAMPAY_VENDOR_ID,
                "language": settings.AZAMPAY_LANGUAGE,
                "currency": currency,
                "externalId": external_id[:30],
                "requestOrigin": request_origin,
                "redirectFailURL": failure_url,
                "redirectSuccessURL": success_url,
                "vendorName": settings.AZAMPAY_VENDOR_NAME or settings.APP_NAME,
                "amount": format(amount, "f"),
                "cart": cart,
            },
        )
        checkout_url = data.get("data") or data.get("checkoutUrl") or data.get("url")
        if isinstance(checkout_url, dict):
            checkout_url = checkout_url.get("url") or checkout_url.get("checkoutUrl")
        if not checkout_url:
            raise AzamPayAPIError("AzamPay card checkout response did not contain a checkout URL", payload=data)
        return AzamPayResult(
            success=bool(data.get("success", True)),
            transaction_id=data.get("transactionId"),
            message=data.get("message"),
            checkout_url=str(checkout_url),
            raw=data,
        )
        
    def name_lookup(
        self,
        phone_number: str,
        provider: str,
    ) -> dict[str, Any]:
        """Resolve the account name for a supported mobile-money number."""
        token = self.get_token()
        url = f"{self.base_url}/{settings.AZAMPAY_NAME_LOOKUP_PATH.lstrip('/')}"
        payload = {
            "accountNumber": phone_number,
            "provider": provider.upper(),
        }
        response = self._request(
            "POST",
            url,
            json_payload=payload,
            headers=self._headers(token),
        )
        if response.status_code == 401:
            token = self.get_token(force_refresh=True)
            response = self._request(
                "POST",
                url,
                json_payload=payload,
                headers=self._headers(token),
            )
        data = self._json_response(response)
        if not response.ok or data.get("success") is False:
            raise AzamPayAPIError(
                data.get("message") or data.get("msg") or "AzamPay name lookup failed",
                status_code=response.status_code,
                payload=data,
            )
        return data
