from typing import Literal

from prometheus_client import Counter, Histogram, generate_latest

ProviderName = Literal["directory", "github", "notification", "oauth"]
OperationName = Literal[
    "create_issue",
    "get_user",
    "list_users",
    "send_notification",
    "token",
]
OutcomeName = Literal[
    "circuit_open",
    "contract_error",
    "rejected",
    "success",
    "timeout",
    "unavailable",
]

REQUESTS = Counter(
    "integration_framework_requests_total",
    "Outbound integration requests.",
    ("provider", "operation", "outcome"),
)
LATENCY = Histogram(
    "integration_framework_request_duration_seconds",
    "Outbound integration request duration.",
    ("provider", "operation"),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)


def observe_request(
    provider: ProviderName,
    operation: OperationName,
    outcome: OutcomeName,
    duration_seconds: float,
) -> None:
    REQUESTS.labels(provider=provider, operation=operation, outcome=outcome).inc()
    LATENCY.labels(provider=provider, operation=operation).observe(duration_seconds)


def render_metrics() -> bytes:
    return generate_latest()
