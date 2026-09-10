import asyncio

import httpx
from pydantic import SecretStr

from app.auth import ApiKeyAuth, BearerTokenAuth
from app.client import IntegrationClient
from app.integrations.directory import DirectoryAdapter
from app.integrations.github import CreateGitHubIssue, GitHubAdapter
from app.integrations.notification import NotificationAdapter, NotificationRequest
from app.metrics import ProviderName
from app.mock_provider import app as mock_provider
from app.resilience import AsyncTokenBucket


def integration_client(
    *,
    auth: ApiKeyAuth | BearerTokenAuth,
    base_url: str,
    provider: ProviderName,
) -> IntegrationClient:
    return IntegrationClient(
        auth=auth,
        base_url=base_url,
        operation_timeout=httpx.Timeout(1),
        provider=provider,
        rate_limiter=AsyncTokenBucket(capacity=100, refill_per_second=100),
        transport=httpx.ASGITransport(app=mock_provider),
    )


def test_directory_contract_and_page_number_pagination() -> None:
    async def exercise() -> None:
        adapter = DirectoryAdapter(
            integration_client(
                auth=ApiKeyAuth(SecretStr("local-development-key")),
                base_url="http://mock/directory",
                provider="directory",
            )
        )
        try:
            users = await adapter.list_users()
            user = await adapter.get_user("user-1")
        finally:
            await adapter.close()

        assert [entry.id for entry in users] == ["user-1", "user-2", "user-3"]
        assert user.display_name == "Amina Yusuf"

    asyncio.run(exercise())


def test_github_contract_create_and_link_pagination() -> None:
    async def exercise() -> None:
        client = integration_client(
            auth=BearerTokenAuth(SecretStr("local-development-token")),
            base_url="http://mock/github",
            provider="github",
        )
        adapter = GitHubAdapter(client, "http://mock/github")
        try:
            issue = await adapter.create_issue(
                owner="astra",
                repository="automation",
                issue=CreateGitHubIssue(title="Investigate retry", body="Details"),
            )
            issues = await adapter.list_issues(
                owner="astra",
                repository="automation",
            )
        finally:
            await adapter.close()

        assert issue.number == 101
        assert [entry.number for entry in issues] == [1, 2, 3]

    asyncio.run(exercise())


def test_notification_contract_requires_idempotency() -> None:
    async def exercise() -> None:
        adapter = NotificationAdapter(
            integration_client(
                auth=BearerTokenAuth(SecretStr("local-development-token")),
                base_url="http://mock/notifications",
                provider="notification",
            )
        )
        try:
            receipt = await adapter.send(
                NotificationRequest(channel="operations", message="Completed"),
                idempotency_key="notification-1",
            )
        finally:
            await adapter.close()

        assert receipt.accepted is True
        assert receipt.message_id == "message-001"

    asyncio.run(exercise())
