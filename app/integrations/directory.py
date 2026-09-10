from pydantic import BaseModel, Field

from app.client import IntegrationClient
from app.pagination import next_page_number


class DirectoryUser(BaseModel):
    display_name: str
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    id: str


class DirectoryPage(BaseModel):
    page: int = Field(ge=1)
    total_pages: int = Field(ge=1)
    users: list[DirectoryUser]


class DirectoryAdapter:
    def __init__(self, client: IntegrationClient) -> None:
        self._client = client

    async def close(self) -> None:
        await self._client.close()

    async def get_user(self, user_id: str) -> DirectoryUser:
        result = await self._client.request(
            method="GET",
            operation="get_user",
            path=f"users/{user_id}",
            response_model=DirectoryUser,
        )
        return result.data

    async def list_users(self, max_pages: int = 5) -> list[DirectoryUser]:
        if max_pages < 1 or max_pages > 20:
            raise ValueError("max_pages must be between 1 and 20")

        page = 1
        users: list[DirectoryUser] = []
        for _ in range(max_pages):
            result = await self._client.request(
                method="GET",
                operation="list_users",
                params={"page": page, "per_page": 2},
                path="users",
                response_model=DirectoryPage,
            )
            users.extend(result.data.users)
            next_page = next_page_number(
                result.data.page,
                result.data.total_pages,
            )
            if next_page is None:
                break
            page = next_page
        return users
