import asyncio

import httpx
import pytest
from pydantic import BaseModel, SecretStr

from app.auth import BearerTokenAuth
from app.client import IntegrationClient
from app.errors import (
    CircuitOpenError,
    ContractViolationError,
    UpstreamAuthenticationError,
    UpstreamResponseError,
)
from app.resilience import AsyncTokenBucket, CircuitBreaker, RetryPolicy


class Payload(BaseModel):
    value: str


async def no_sleep(_: float) -> None:
    await asyncio.sleep(0)


def client_for(
    handler: httpx.MockTransport,
    *,
    breaker: CircuitBreaker | None = None,
    attempts: int = 3,
) -> IntegrationClient:
    return IntegrationClient(
        auth=BearerTokenAuth(SecretStr("secret")),
        base_url="https://provider.test/api",
        circuit_breaker=breaker,
        operation_timeout=httpx.Timeout(1),
        provider="github",
        rate_limiter=AsyncTokenBucket(capacity=100, refill_per_second=100),
        retry_policy=RetryPolicy(
            max_attempts=attempts,
            base_delay_seconds=0,
            max_delay_seconds=0,
        ),
        sleeper=no_sleep,
        transport=handler,
    )


def test_client_applies_headers_and_decodes_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://provider.test/api/resource"
        assert request.headers["authorization"] == "Bearer secret"
        assert request.headers["x-correlation-id"] == "correlation"
        assert request.headers["idempotency-key"] == "request-1"
        return httpx.Response(200, json={"value": "ok"})

    async def exercise() -> None:
        async with client_for(httpx.MockTransport(handler)) as client:
            result = await client.request(
                correlation_id="correlation",
                idempotency_key="request-1",
                method="POST",
                operation="create_issue",
                path="resource",
                response_model=Payload,
            )
        assert result.data.value == "ok"
        assert result.status_code == 200

    asyncio.run(exercise())


def test_client_retries_transient_status_and_honors_final_contract() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"value": "recovered"})

    async def exercise() -> None:
        async with client_for(httpx.MockTransport(handler)) as client:
            result = await client.request(
                allow_retries=True,
                method="GET",
                operation="list_issues",
                path="resource",
                response_model=Payload,
            )
        assert result.data.value == "recovered"

    asyncio.run(exercise())
    assert calls == 2


def test_client_exposes_safe_authentication_and_response_errors() -> None:
    responses = iter([401, 400])

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(next(responses), text="sensitive provider body")

    async def exercise() -> None:
        async with client_for(httpx.MockTransport(handler), attempts=1) as client:
            with pytest.raises(UpstreamAuthenticationError) as authentication:
                await client.request(
                    allow_retries=True,
                    method="GET",
                    operation="list_issues",
                    path="resource",
                    response_model=Payload,
                )
            with pytest.raises(UpstreamResponseError) as response:
                await client.request(
                    method="GET",
                    operation="list_issues",
                    path="resource",
                    response_model=Payload,
                )

        assert "sensitive" not in str(authentication.value)
        assert authentication.value.context.status_code == 401
        assert response.value.context.retryable is False

    asyncio.run(exercise())


def test_client_rejects_contract_drift() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    async def exercise() -> None:
        async with client_for(httpx.MockTransport(handler)) as client:
            with pytest.raises(ContractViolationError):
                await client.request(
                    method="GET",
                    operation="list_issues",
                    path="resource",
                    response_model=Payload,
                )

    asyncio.run(exercise())


def test_client_opens_circuit_after_repeated_failures() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    async def exercise() -> None:
        breaker = CircuitBreaker(failure_threshold=2)
        async with client_for(
            httpx.MockTransport(handler),
            attempts=3,
            breaker=breaker,
        ) as client:
            with pytest.raises(CircuitOpenError):
                await client.request(
                    allow_retries=True,
                    method="GET",
                    operation="list_issues",
                    path="resource",
                    response_model=Payload,
                )

    asyncio.run(exercise())
    assert calls == 2


def test_client_does_not_retry_without_operation_permission() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    async def exercise() -> None:
        async with client_for(httpx.MockTransport(handler)) as client:
            with pytest.raises(UpstreamResponseError) as response:
                await client.request(
                    method="POST",
                    operation="create_issue",
                    path="resource",
                    response_model=Payload,
                )
        assert response.value.context.retryable is True

    asyncio.run(exercise())
    assert calls == 1
