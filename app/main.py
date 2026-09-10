from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

from app.config import get_settings
from app.dependencies import (
    directory_adapter,
    github_adapter,
    notification_adapter,
)
from app.errors import (
    CircuitOpenError,
    IntegrationError,
    UpstreamRateLimitError,
    UpstreamTimeoutError,
)
from app.integrations.directory import DirectoryAdapter, DirectoryUser
from app.integrations.github import CreateGitHubIssue, GitHubAdapter, GitHubIssue
from app.integrations.notification import (
    NotificationAdapter,
    NotificationReceipt,
    NotificationRequest,
)
from app.logging import configure_logging
from app.metrics import render_metrics
from app.webhooks import (
    ReplayGuard,
    VerifiedWebhook,
    WebhookVerificationError,
    WebhookVerifier,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


app = FastAPI(
    title="Enterprise API Integration Framework",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(IntegrationError)
async def integration_error_handler(
    _: Request,
    error: IntegrationError,
) -> JSONResponse:
    status_code = 502
    if isinstance(error, CircuitOpenError | UpstreamRateLimitError):
        status_code = 503
    elif isinstance(error, UpstreamTimeoutError):
        status_code = 504
    return JSONResponse(
        error.public_detail(),
        headers={"X-Correlation-Id": error.context.correlation_id},
        status_code=status_code,
    )


@app.get("/health", tags=["operations"])
async def health() -> dict[str, str]:
    return {"service": get_settings().service_name, "status": "healthy"}


@app.get("/ready", tags=["operations"])
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(
        content=render_metrics(),
        media_type="text/plain; version=0.0.4",
    )


@app.get("/integrations/directory/users", tags=["integrations"])
async def list_directory_users(
    adapter: Annotated[DirectoryAdapter, Depends(directory_adapter)],
    max_pages: int = Query(default=5, ge=1, le=20),
) -> list[DirectoryUser]:
    return await adapter.list_users(max_pages)


@app.get("/integrations/directory/users/{user_id}", tags=["integrations"])
async def get_directory_user(
    user_id: str,
    adapter: Annotated[DirectoryAdapter, Depends(directory_adapter)],
) -> DirectoryUser:
    return await adapter.get_user(user_id)


@app.get("/integrations/github/{owner}/{repository}/issues", tags=["integrations"])
async def list_github_issues(
    owner: str,
    repository: str,
    adapter: Annotated[GitHubAdapter, Depends(github_adapter)],
    max_pages: int = Query(default=5, ge=1, le=20),
) -> list[GitHubIssue]:
    return await adapter.list_issues(
        owner=owner,
        repository=repository,
        max_pages=max_pages,
    )


@app.post(
    "/integrations/github/{owner}/{repository}/issues",
    response_model=GitHubIssue,
    status_code=201,
    tags=["integrations"],
)
async def create_github_issue(
    owner: str,
    repository: str,
    issue: CreateGitHubIssue,
    adapter: Annotated[GitHubAdapter, Depends(github_adapter)],
    correlation_id: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
) -> GitHubIssue:
    return await adapter.create_issue(
        correlation_id=correlation_id,
        issue=issue,
        owner=owner,
        repository=repository,
    )


@app.post(
    "/integrations/notifications",
    response_model=NotificationReceipt,
    status_code=202,
    tags=["integrations"],
)
async def send_notification(
    notification: NotificationRequest,
    adapter: Annotated[NotificationAdapter, Depends(notification_adapter)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> NotificationReceipt:
    return await adapter.send(
        notification,
        idempotency_key=idempotency_key,
    )


@lru_cache
def webhook_verifier() -> WebhookVerifier:
    return WebhookVerifier(
        secret=get_settings().webhook_secret,
        replay_guard=ReplayGuard(),
    )


@app.post("/webhooks/billing", tags=["webhooks"])
async def receive_billing_webhook(
    request: Request,
    signature: Annotated[str | None, Header(alias="X-Webhook-Signature")] = None,
    timestamp: Annotated[str | None, Header(alias="X-Webhook-Timestamp")] = None,
) -> VerifiedWebhook:
    try:
        return await webhook_verifier().verify(
            body=await request.body(),
            signature_header=signature,
            timestamp_header=timestamp,
        )
    except WebhookVerificationError as error:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_webhook", "message": str(error)},
        ) from error
