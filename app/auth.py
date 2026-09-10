import asyncio
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx
from pydantic import BaseModel, Field, SecretStr


class AuthStrategy(Protocol):
    async def headers(self, client: httpx.AsyncClient) -> dict[str, str]: ...


@dataclass(frozen=True)
class ApiKeyAuth:
    api_key: SecretStr
    header_name: str = "X-API-Key"

    async def headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        del client
        return {self.header_name: self.api_key.get_secret_value()}


@dataclass(frozen=True)
class BearerTokenAuth:
    token: SecretStr

    async def headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        del client
        return {"Authorization": f"Bearer {self.token.get_secret_value()}"}


class OAuthTokenResponse(BaseModel):
    access_token: SecretStr
    expires_in: int = Field(gt=0)
    token_type: str


@dataclass
class OAuthClientCredentialsAuth:
    client_id: str
    client_secret: SecretStr
    scope: str
    token_url: str
    refresh_skew_seconds: float = 30
    _access_token: SecretStr | None = field(default=None, init=False)
    _expires_at: float = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        async with self._lock:
            now = time.monotonic()
            if self._access_token is None or now >= self._expires_at:
                response = await client.post(
                    self.token_url,
                    auth=(self.client_id, self.client_secret.get_secret_value()),
                    data={"grant_type": "client_credentials", "scope": self.scope},
                )
                response.raise_for_status()
                token = OAuthTokenResponse.model_validate(response.json())
                if token.token_type.lower() != "bearer":
                    raise ValueError("OAuth token type must be Bearer")
                self._access_token = token.access_token
                self._expires_at = (
                    now + max(0, token.expires_in - self.refresh_skew_seconds)
                )

            return {
                "Authorization": f"Bearer {self._access_token.get_secret_value()}"
            }
