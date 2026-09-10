import asyncio
import time
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Generic, Self, TypeVar
from uuid import uuid4

import httpx
import structlog
from pydantic import BaseModel, ValidationError

from app.auth import AuthStrategy
from app.errors import (
    ContractViolationError,
    ErrorContext,
    IntegrationError,
    UpstreamAuthenticationError,
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from app.metrics import OperationName, OutcomeName, ProviderName, observe_request
from app.resilience import AsyncTokenBucket, CircuitBreaker, RetryPolicy, Sleeper

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


@dataclass(frozen=True)
class ClientResult(Generic[ResponseModel]):
    correlation_id: str
    data: ResponseModel
    headers: Mapping[str, str]
    status_code: int


class IntegrationClient:
    def __init__(
        self,
        *,
        auth: AuthStrategy,
        base_url: str,
        operation_timeout: httpx.Timeout,
        provider: ProviderName,
        rate_limiter: AsyncTokenBucket,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sleeper: Sleeper = asyncio.sleep,
    ) -> None:
        self._auth = auth
        self._breaker = circuit_breaker or CircuitBreaker()
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=operation_timeout,
            transport=transport,
        )
        self._logger = structlog.get_logger("integration_client")
        self._provider = provider
        self._rate_limiter = rate_limiter
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleeper = sleeper

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        *,
        method: str,
        operation: OperationName,
        path: str,
        response_model: type[ResponseModel],
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
        json_body: object | None = None,
        params: Mapping[str, str | int] | None = None,
    ) -> ClientResult[ResponseModel]:
        request_correlation_id = correlation_id or str(uuid4())
        started_at = time.monotonic()

        try:
            result = await self._request_with_retries(
                correlation_id=request_correlation_id,
                idempotency_key=idempotency_key,
                json_body=json_body,
                method=method,
                operation=operation,
                params=params,
                path=path,
                response_model=response_model,
            )
        except IntegrationError as error:
            outcome = self._outcome_for_error(error)
            self._record(
                correlation_id=request_correlation_id,
                duration_seconds=time.monotonic() - started_at,
                method=method,
                operation=operation,
                outcome=outcome,
            )
            raise

        self._record(
            correlation_id=request_correlation_id,
            duration_seconds=time.monotonic() - started_at,
            method=method,
            operation=operation,
            outcome="success",
        )
        return result

    async def _request_with_retries(
        self,
        *,
        correlation_id: str,
        idempotency_key: str | None,
        json_body: object | None,
        method: str,
        operation: OperationName,
        params: Mapping[str, str | int] | None,
        path: str,
        response_model: type[ResponseModel],
    ) -> ClientResult[ResponseModel]:
        for attempt in range(1, self._retry_policy.max_attempts + 1):
            await self._rate_limiter.acquire()
            await self._breaker.before_request(self._provider, correlation_id)
            try:
                response = await self._send(
                    correlation_id=correlation_id,
                    idempotency_key=idempotency_key,
                    json_body=json_body,
                    method=method,
                    params=params,
                    path=path,
                )
            except httpx.TimeoutException as cause:
                await self._breaker.record_failure()
                timeout_error = UpstreamTimeoutError(
                    "The upstream request timed out",
                    self._context(
                        code="upstream_timeout",
                        correlation_id=correlation_id,
                        retryable=True,
                    ),
                )
                if attempt == self._retry_policy.max_attempts:
                    raise timeout_error from cause
                await self._wait(attempt)
                continue
            except httpx.RequestError as cause:
                await self._breaker.record_failure()
                unavailable_error = UpstreamUnavailableError(
                    "The upstream provider is unavailable",
                    self._context(
                        code="upstream_unavailable",
                        correlation_id=correlation_id,
                        retryable=True,
                    ),
                )
                if attempt == self._retry_policy.max_attempts:
                    raise unavailable_error from cause
                await self._wait(attempt)
                continue

            if response.status_code < 400:
                await self._breaker.record_success()
                return self._decode(response, response_model, correlation_id)

            response_error = await self._response_error(response, correlation_id)
            if response_error.context.retryable:
                await self._breaker.record_failure()
            else:
                await self._breaker.record_success()

            if (
                not response_error.context.retryable
                or attempt == self._retry_policy.max_attempts
            ):
                raise response_error

            retry_after = (
                response_error.retry_after_seconds
                if isinstance(response_error, UpstreamRateLimitError)
                else None
            )
            await self._wait(attempt, retry_after)

        raise RuntimeError("Retry loop exhausted without a result")

    async def _send(
        self,
        *,
        correlation_id: str,
        idempotency_key: str | None,
        json_body: object | None,
        method: str,
        params: Mapping[str, str | int] | None,
        path: str,
    ) -> httpx.Response:
        headers = await self._auth.headers(self._client)
        headers["Accept"] = "application/json"
        headers["X-Correlation-Id"] = correlation_id
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return await self._client.request(
            method,
            path,
            headers=headers,
            json=json_body,
            params=params,
        )

    async def _response_error(
        self,
        response: httpx.Response,
        correlation_id: str,
    ) -> IntegrationError:
        status_code = response.status_code
        if status_code in {401, 403}:
            return UpstreamAuthenticationError(
                "The upstream provider rejected authentication",
                self._context(
                    code="upstream_authentication_failed",
                    correlation_id=correlation_id,
                    retryable=False,
                    status_code=status_code,
                ),
            )
        if status_code == 429:
            return UpstreamRateLimitError(
                "The upstream provider rate limit was exceeded",
                self._context(
                    code="upstream_rate_limited",
                    correlation_id=correlation_id,
                    retryable=True,
                    status_code=status_code,
                ),
                retry_after_seconds=self._retry_after_seconds(response),
            )
        return UpstreamResponseError(
            "The upstream provider returned an unsuccessful response",
            self._context(
                code="upstream_response_error",
                correlation_id=correlation_id,
                retryable=status_code in self._retry_policy.retryable_status_codes,
                status_code=status_code,
            ),
        )

    def _decode(
        self,
        response: httpx.Response,
        response_model: type[ResponseModel],
        correlation_id: str,
    ) -> ClientResult[ResponseModel]:
        try:
            data = response_model.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise ContractViolationError(
                "The upstream response violated the expected contract",
                self._context(
                    code="contract_violation",
                    correlation_id=correlation_id,
                    retryable=False,
                    status_code=response.status_code,
                ),
            ) from error
        return ClientResult(
            correlation_id=correlation_id,
            data=data,
            headers=response.headers,
            status_code=response.status_code,
        )

    async def _wait(
        self,
        attempt: int,
        retry_after_seconds: float | None = None,
    ) -> None:
        await self._sleeper(
            self._retry_policy.delay_seconds(attempt, retry_after_seconds)
        )

    def _context(
        self,
        *,
        code: str,
        correlation_id: str,
        retryable: bool,
        status_code: int | None = None,
    ) -> ErrorContext:
        return ErrorContext(
            code=code,
            correlation_id=correlation_id,
            provider=self._provider,
            retryable=retryable,
            status_code=status_code,
        )

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _outcome_for_error(error: IntegrationError) -> OutcomeName:
        if isinstance(error, ContractViolationError):
            return "contract_error"
        if isinstance(error, UpstreamTimeoutError):
            return "timeout"
        if isinstance(error, UpstreamUnavailableError):
            return "unavailable"
        if error.context.code == "circuit_open":
            return "circuit_open"
        return "rejected"

    def _record(
        self,
        *,
        correlation_id: str,
        duration_seconds: float,
        method: str,
        operation: OperationName,
        outcome: OutcomeName,
    ) -> None:
        observe_request(self._provider, operation, outcome, duration_seconds)
        self._logger.info(
            "integration_request",
            correlation_id=correlation_id,
            duration_ms=round(duration_seconds * 1000, 2),
            method=method.upper(),
            operation=operation,
            outcome=outcome,
            provider=self._provider,
        )
