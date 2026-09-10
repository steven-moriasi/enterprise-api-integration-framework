from collections.abc import AsyncIterator

import httpx

from app.auth import ApiKeyAuth, BearerTokenAuth
from app.client import IntegrationClient
from app.config import get_settings
from app.integrations.directory import DirectoryAdapter
from app.integrations.github import GitHubAdapter
from app.integrations.notification import NotificationAdapter
from app.resilience import AsyncTokenBucket


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(5, connect=2, pool=2, read=5, write=5)


async def directory_adapter() -> AsyncIterator[DirectoryAdapter]:
    settings = get_settings()
    client = IntegrationClient(
        auth=ApiKeyAuth(settings.directory_api_key),
        base_url=str(settings.directory_base_url),
        operation_timeout=_timeout(),
        provider="directory",
        rate_limiter=AsyncTokenBucket(capacity=10, refill_per_second=5),
    )
    adapter = DirectoryAdapter(client)
    try:
        yield adapter
    finally:
        await adapter.close()


async def github_adapter() -> AsyncIterator[GitHubAdapter]:
    settings = get_settings()
    base_url = str(settings.github_base_url)
    client = IntegrationClient(
        auth=BearerTokenAuth(settings.github_token),
        base_url=base_url,
        operation_timeout=_timeout(),
        provider="github",
        rate_limiter=AsyncTokenBucket(capacity=10, refill_per_second=5),
    )
    adapter = GitHubAdapter(client, base_url)
    try:
        yield adapter
    finally:
        await adapter.close()


async def notification_adapter() -> AsyncIterator[NotificationAdapter]:
    settings = get_settings()
    client = IntegrationClient(
        auth=BearerTokenAuth(settings.notification_bearer_token),
        base_url=str(settings.notification_base_url),
        operation_timeout=_timeout(),
        provider="notification",
        rate_limiter=AsyncTokenBucket(capacity=10, refill_per_second=5),
    )
    adapter = NotificationAdapter(client)
    try:
        yield adapter
    finally:
        await adapter.close()
