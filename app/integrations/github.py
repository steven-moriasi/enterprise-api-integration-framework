from urllib.parse import urlparse

from pydantic import BaseModel, Field, RootModel

from app.client import IntegrationClient
from app.pagination import next_link


class GitHubIssue(BaseModel):
    html_url: str
    id: int
    number: int
    state: str
    title: str


class GitHubIssueList(RootModel[list[GitHubIssue]]):
    pass


class CreateGitHubIssue(BaseModel):
    body: str = Field(min_length=1, max_length=65_536)
    title: str = Field(min_length=1, max_length=256)


class GitHubAdapter:
    def __init__(self, client: IntegrationClient, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client

    async def close(self) -> None:
        await self._client.close()

    async def create_issue(
        self,
        *,
        owner: str,
        repository: str,
        issue: CreateGitHubIssue,
        correlation_id: str | None = None,
    ) -> GitHubIssue:
        result = await self._client.request(
            correlation_id=correlation_id,
            json_body=issue.model_dump(),
            method="POST",
            operation="create_issue",
            path=f"repos/{owner}/{repository}/issues",
            response_model=GitHubIssue,
        )
        return result.data

    async def list_issues(
        self,
        *,
        owner: str,
        repository: str,
        max_pages: int = 5,
    ) -> list[GitHubIssue]:
        if max_pages < 1 or max_pages > 20:
            raise ValueError("max_pages must be between 1 and 20")

        path = f"repos/{owner}/{repository}/issues?per_page=2"
        expected_origin = self._origin()
        issues: list[GitHubIssue] = []
        for _ in range(max_pages):
            result = await self._client.request(
                method="GET",
                operation="list_issues",
                path=path,
                response_model=GitHubIssueList,
            )
            issues.extend(result.data.root)
            next_url = next_link(result.headers, expected_origin=expected_origin)
            if next_url is None:
                break
            path = next_url
        return issues

    def _origin(self) -> str:
        parsed = urlparse(self._base_url)
        return f"{parsed.scheme}://{parsed.netloc}"
