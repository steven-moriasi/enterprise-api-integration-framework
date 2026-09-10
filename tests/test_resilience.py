import asyncio

import pytest

from app.errors import CircuitOpenError
from app.resilience import AsyncTokenBucket, CircuitBreaker, CircuitState, RetryPolicy


def test_retry_policy_bounds_provider_and_exponential_delays() -> None:
    policy = RetryPolicy(base_delay_seconds=0.5, max_delay_seconds=2)

    assert policy.delay_seconds(1) == 0.5
    assert policy.delay_seconds(4) == 2
    assert policy.delay_seconds(1, retry_after_seconds=10) == 2
    assert policy.delay_seconds(1, retry_after_seconds=-1) == 0


def test_token_bucket_waits_for_refill() -> None:
    current_time = [0.0]
    delays: list[float] = []

    async def sleeper(delay: float) -> None:
        delays.append(delay)
        current_time[0] += delay
        await asyncio.sleep(0)

    async def exercise() -> None:
        bucket = AsyncTokenBucket(
            capacity=1,
            refill_per_second=2,
            clock=lambda: current_time[0],
            sleeper=sleeper,
        )
        await bucket.acquire()
        await bucket.acquire()

    asyncio.run(exercise())
    assert delays == [0.5]


def test_circuit_breaker_opens_and_recovers_with_one_probe() -> None:
    current_time = [0.0]

    async def exercise() -> None:
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout_seconds=10,
            clock=lambda: current_time[0],
        )
        await breaker.before_request("github", "correlation")
        await breaker.record_failure()
        await breaker.before_request("github", "correlation")
        await breaker.record_failure()
        assert breaker.state.value == CircuitState.OPEN.value

        with pytest.raises(CircuitOpenError):
            await breaker.before_request("github", "correlation")

        current_time[0] = 11
        await breaker.before_request("github", "correlation")
        assert breaker.state.value == CircuitState.HALF_OPEN.value
        with pytest.raises(CircuitOpenError):
            await breaker.before_request("github", "correlation")
        await breaker.record_success()
        assert breaker.state.value == CircuitState.CLOSED.value

    asyncio.run(exercise())
