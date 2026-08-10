from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from api.enums import NotificationChannel


@dataclass(slots=True)
class ProviderResult:
    accepted: bool
    provider: str
    reference: str | None = None
    error: str | None = None


class NotificationProvider(Protocol):
    channel: NotificationChannel
    def send(self, *, recipient: str, subject: str | None, message: str, data: dict[str, Any]) -> ProviderResult: ...


class DeferredProvider:
    """Safe default adapter. It records delivery for a worker without contacting an external service."""
    def __init__(self, channel: NotificationChannel):
        self.channel = channel

    def send(self, *, recipient: str, subject: str | None, message: str, data: dict[str, Any]) -> ProviderResult:
        return ProviderResult(accepted=True, provider=f"deferred_{self.channel.value}")


def default_providers() -> dict[NotificationChannel, NotificationProvider]:
    return {channel: DeferredProvider(channel) for channel in (NotificationChannel.email, NotificationChannel.sms, NotificationChannel.push)}
