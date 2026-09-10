import asyncio
import hashlib
import hmac

import httpx

from app.main import app, webhook_verifier


def test_operational_routes_and_webhook_boundary() -> None:
    body = b'{"type":"invoice.paid"}'
    timestamp = "1000"
    signature = hmac.new(
        b"local-development-webhook-secret",
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    verifier = webhook_verifier()
    verifier.clock = lambda: 1_000
    verifier.replay_guard.clock = lambda: 1_000

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://framework",
        ) as client:
            health = await client.get("/health")
            ready = await client.get("/ready")
            metrics = await client.get("/metrics")
            webhook = await client.post(
                "/webhooks/billing",
                content=body,
                headers={
                    "X-Webhook-Signature": f"sha256={signature}",
                    "X-Webhook-Timestamp": timestamp,
                },
            )
            replay = await client.post(
                "/webhooks/billing",
                content=body,
                headers={
                    "X-Webhook-Signature": f"sha256={signature}",
                    "X-Webhook-Timestamp": timestamp,
                },
            )

        assert health.json()["status"] == "healthy"
        assert ready.json() == {"status": "ready"}
        assert "integration_framework_requests_total" in metrics.text
        assert webhook.status_code == 200
        assert replay.status_code == 401

    asyncio.run(exercise())
