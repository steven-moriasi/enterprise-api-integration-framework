import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from app.errors import CircuitOpenError, ErrorContext

Clock = Callable[[], float]
Sleeper = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.1
    max_delay_seconds: float = 2
    retryable_status_codes: frozenset[int] = frozenset(
        {408, 425, 429, 500, 502, 503, 504}
    )

    def delay_seconds(
        self,
        attempt: int,
        retry_after_seconds: float | None = None,
    ) -> float:
        if retry_after_seconds is not None:
            return float(
                min(max(0, retry_after_seconds), self.max_delay_seconds)
            )
        delay = self.base_delay_seconds * float(2 ** max(0, attempt - 1))
        if delay > self.max_delay_seconds:
            return self.max_delay_seconds
        return delay


@dataclass
class AsyncTokenBucket:
    capacity: float
    refill_per_second: float
    clock: Clock = time.monotonic
    sleeper: Sleeper = asyncio.sleep
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self) -> None:
        if self.capacity <= 0 or self.refill_per_second <= 0:
            raise ValueError("Rate-limit capacity and refill rate must be positive")
        self._tokens = self.capacity
        self._last_refill = self.clock()

    async def acquire(self) -> None:
        while True:
            wait_seconds = 0.0
            async with self._lock:
                now = self.clock()
                elapsed = max(0, now - self._last_refill)
                self._tokens = min(
                    self.capacity,
                    self._tokens + elapsed * self.refill_per_second,
                )
                self._last_refill = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                wait_seconds = (1 - self._tokens) / self.refill_per_second
            await self.sleeper(wait_seconds)


class CircuitState(StrEnum):
    CLOSED = "closed"
    HALF_OPEN = "half_open"
    OPEN = "open"


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30
    clock: Clock = time.monotonic
    _consecutive_failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _probe_in_flight: bool = field(default=False, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        return self._state

    async def before_request(self, provider: str, correlation_id: str) -> None:
        async with self._lock:
            if self._state is CircuitState.CLOSED:
                return

            if self._state is CircuitState.OPEN:
                opened_at = (
                    self._opened_at
                    if self._opened_at is not None
                    else self.clock()
                )
                if self.clock() - opened_at >= self.recovery_timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise self._open_error(provider, correlation_id)

            if self._probe_in_flight:
                raise self._open_error(provider, correlation_id)
            self._probe_in_flight = True

    async def record_success(self) -> None:
        async with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None
            self._probe_in_flight = False
            self._state = CircuitState.CLOSED

    async def record_failure(self) -> None:
        async with self._lock:
            self._consecutive_failures += 1
            self._probe_in_flight = False
            if (
                self._state is CircuitState.HALF_OPEN
                or self._consecutive_failures >= self.failure_threshold
            ):
                self._state = CircuitState.OPEN
                self._opened_at = self.clock()

    @staticmethod
    def _open_error(provider: str, correlation_id: str) -> CircuitOpenError:
        return CircuitOpenError(
            "The upstream circuit is open",
            ErrorContext(
                code="circuit_open",
                correlation_id=correlation_id,
                provider=provider,
                retryable=True,
            ),
        )
