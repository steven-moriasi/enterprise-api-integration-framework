from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorContext:
    code: str
    correlation_id: str
    provider: str
    retryable: bool
    status_code: int | None = None


class IntegrationError(Exception):
    def __init__(self, message: str, context: ErrorContext) -> None:
        super().__init__(message)
        self.context = context

    def public_detail(self) -> dict[str, object]:
        return {
            "code": self.context.code,
            "correlationId": self.context.correlation_id,
            "message": str(self),
            "provider": self.context.provider,
            "retryable": self.context.retryable,
        }


class UpstreamAuthenticationError(IntegrationError):
    pass


class UpstreamRateLimitError(IntegrationError):
    def __init__(
        self,
        message: str,
        context: ErrorContext,
        retry_after_seconds: float | None,
    ) -> None:
        super().__init__(message, context)
        self.retry_after_seconds = retry_after_seconds


class UpstreamResponseError(IntegrationError):
    pass


class UpstreamTimeoutError(IntegrationError):
    pass


class UpstreamUnavailableError(IntegrationError):
    pass


class CircuitOpenError(IntegrationError):
    pass


class ContractViolationError(IntegrationError):
    pass
