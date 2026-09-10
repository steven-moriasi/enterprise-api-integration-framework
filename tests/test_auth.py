import asyncio

import httpx
from pydantic import SecretStr

from app.auth import ApiKeyAuth, BearerTokenAuth, OAuthClientCredentialsAuth


def test_static_authentication_headers() -> None:
    async def exercise() -> None:
        async with httpx.AsyncClient() as client:
            api_key = await ApiKeyAuth(SecretStr("key")).headers(client)
            bearer = await BearerTokenAuth(SecretStr("token")).headers(client)

        assert api_key == {"X-API-Key": "key"}
        assert bearer == {"Authorization": "Bearer token"}

    asyncio.run(exercise())


def test_oauth_client_credentials_caches_token() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["authorization"].startswith("Basic ")
        assert request.content == b"grant_type=client_credentials&scope=users%3Aread"
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )

    async def exercise() -> None:
        auth = OAuthClientCredentialsAuth(
            client_id="client",
            client_secret=SecretStr("secret"),
            scope="users:read",
            token_url="https://identity.test/token",
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            first = await auth.headers(client)
            second = await auth.headers(client)

        assert first == {"Authorization": "Bearer access-token"}
        assert second == first

    asyncio.run(exercise())
    assert calls == 1
