from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping, Protocol, runtime_checkable


class PaymentProvider(StrEnum):
    AZAMPAY = "azampay"
    ZENOPAY = "zenopay"


class GatewayPaymentStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class PaymentGatewayConfigurationError(RuntimeError):
    """Raised when the selected gateway is missing required configuration."""


class PaymentGatewayAPIError(RuntimeError):
    """A safe, provider-neutral error suitable for the payment router."""

    def __init__(self, message: str, *, status_code: int | None = None,
                 payload: Mapping[str, Any] | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = dict(payload or {})
        self.retryable = retryable


@dataclass(frozen=True)
class GatewayInitiationResult:
    provider: PaymentProvider
    accepted: bool
    external_order_id: str
    provider_reference: str | None
    status: GatewayPaymentStatus
    message: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class GatewayStatusResult:
    provider: PaymentProvider
    external_order_id: str
    provider_reference: str | None
    status: GatewayPaymentStatus
    amount: Decimal | None
    channel: str | None
    msisdn: str | None
    raw_status: str | None
    raw: dict[str, Any]


@runtime_checkable
class MobileMoneyGateway(Protocol):
    provider: PaymentProvider

    def initiate_mobile_money(self, *, external_order_id: str, buyer_email: str,
                              buyer_name: str, buyer_phone: str, amount: Decimal,
                              metadata: Mapping[str, Any] | None = None,
                              webhook_url: str | None = None) -> GatewayInitiationResult: ...

    def check_status(self, external_order_id: str) -> GatewayStatusResult: ...
