import asyncio
import hashlib
import hmac
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, SecretStr

Clock = Callable[[], float]


class WebhookVerificationError(Exception):
    pass


class VerifiedWebhook(BaseModel):
    event_id: str
    payload_sha256: str
    received_at: datetime


@dataclass
class ReplayGuard:
    retention_seconds: float = 300
    max_entries: int = 10_000
    clock: Clock = time.time
    _seen: dict[str, float] = field(default_factory=dict, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def register(self, replay_key: str) -> None:
        async with self._lock:
            now = self.clock()
            oldest_allowed = now - self.retention_seconds
            self._seen = {
                key: observed_at
                for key, observed_at in self._seen.items()
                if observed_at >= oldest_allowed
            }
            if replay_key in self._seen:
                raise WebhookVerificationError("Webhook replay detected")
            if len(self._seen) >= self.max_entries:
                raise WebhookVerificationError("Webhook replay cache is at capacity")
            self._seen[replay_key] = now


@dataclass
class WebhookVerifier:
    secret: SecretStr
    replay_guard: ReplayGuard
    tolerance_seconds: float = 300
    clock: Clock = time.time

    async def verify(
        self,
        *,
        body: bytes,
        signature_header: str | None,
        timestamp_header: str | None,
    ) -> VerifiedWebhook:
        if signature_header is None or timestamp_header is None:
            raise WebhookVerificationError("Webhook signature headers are required")

        try:
            timestamp = int(timestamp_header)
        except ValueError as error:
            raise WebhookVerificationError("Webhook timestamp is invalid") from error

        if abs(self.clock() - timestamp) > self.tolerance_seconds:
            raise WebhookVerificationError("Webhook timestamp is outside the tolerance")

        expected = hmac.new(
            self.secret.get_secret_value().encode(),
            timestamp_header.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        supplied = signature_header.removeprefix("sha256=")
        if not hmac.compare_digest(expected, supplied):
            raise WebhookVerificationError("Webhook signature is invalid")

        replay_key = hashlib.sha256(
            timestamp_header.encode() + b":" + supplied.encode()
        ).hexdigest()
        await self.replay_guard.register(replay_key)
        return VerifiedWebhook(
            event_id=str(uuid4()),
            payload_sha256=hashlib.sha256(body).hexdigest(),
            received_at=datetime.now(UTC),
        )
