import asyncio
import hashlib
import hmac

import pytest
from pydantic import SecretStr

from app.webhooks import ReplayGuard, WebhookVerificationError, WebhookVerifier


def test_webhook_signature_timestamp_and_replay_protection() -> None:
    timestamp = "1_000"
    body = b'{"event":"invoice.paid"}'
    secret = "secret"
    signature = hmac.new(
        secret.encode(),
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()

    async def exercise() -> None:
        verifier = WebhookVerifier(
            secret=SecretStr(secret),
            replay_guard=ReplayGuard(clock=lambda: 1_000),
            clock=lambda: 1_000,
        )
        verified = await verifier.verify(
            body=body,
            signature_header=f"sha256={signature}",
            timestamp_header=timestamp,
        )
        assert verified.payload_sha256 == hashlib.sha256(body).hexdigest()

        with pytest.raises(WebhookVerificationError, match="replay"):
            await verifier.verify(
                body=body,
                signature_header=f"sha256={signature}",
                timestamp_header=timestamp,
            )

    asyncio.run(exercise())


def test_webhook_rejects_missing_stale_and_invalid_signatures() -> None:
    async def exercise() -> None:
        verifier = WebhookVerifier(
            secret=SecretStr("secret"),
            replay_guard=ReplayGuard(clock=lambda: 1_000),
            tolerance_seconds=10,
            clock=lambda: 1_000,
        )
        with pytest.raises(WebhookVerificationError, match="required"):
            await verifier.verify(
                body=b"{}",
                signature_header=None,
                timestamp_header=None,
            )
        with pytest.raises(WebhookVerificationError, match="tolerance"):
            await verifier.verify(
                body=b"{}",
                signature_header="sha256=invalid",
                timestamp_header="1",
            )
        with pytest.raises(WebhookVerificationError, match="signature"):
            await verifier.verify(
                body=b"{}",
                signature_header="sha256=invalid",
                timestamp_header="1000",
            )

    asyncio.run(exercise())
