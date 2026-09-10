from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, status

from app.integrations.directory import DirectoryPage, DirectoryUser
from app.integrations.github import CreateGitHubIssue, GitHubIssue
from app.integrations.notification import NotificationReceipt, NotificationRequest

app = FastAPI(title="Synthetic local integration contract provider")

SYNTHETIC_USERS = [
    DirectoryUser(
        id="user-1",
        display_name="Sample User One",
        email="user1@example.test",
    ),
    DirectoryUser(
        id="user-2",
        display_name="Sample User Two",
        email="user2@example.test",
    ),
    DirectoryUser(
        id="user-3",
        display_name="Sample User Three",
        email="user3@example.test",
    ),
]


def _require_bearer(authorization: str | None) -> None:
    if authorization != "Bearer local-development-token":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/github/repos/{owner}/{repository}/issues", status_code=201)
async def create_issue(
    owner: str,
    repository: str,
    issue: CreateGitHubIssue,
    authorization: str | None = Header(default=None),
) -> GitHubIssue:
    _require_bearer(authorization)
    return GitHubIssue(
        html_url=f"https://github.example/{owner}/{repository}/issues/101",
        id=101,
        number=101,
        state="open",
        title=issue.title,
    )


@app.get("/github/repos/{owner}/{repository}/issues")
async def list_issues(
    owner: str,
    repository: str,
    request: Request,
    response: Response,
    page: int = Query(default=1, ge=1, le=2),
    authorization: str | None = Header(default=None),
) -> list[GitHubIssue]:
    _require_bearer(authorization)
    if page == 1:
        origin = str(request.base_url).rstrip("/")
        response.headers["Link"] = (
            f'<{origin}/github/repos/{owner}/{repository}'
            '/issues?per_page=2&page=2>; rel="next"'
        )
    return [
        GitHubIssue(
            html_url=f"https://github.example/{owner}/{repository}/issues/{number}",
            id=number,
            number=number,
            state="open",
            title=f"Contract fixture {number}",
        )
        for number in ([1, 2] if page == 1 else [3])
    ]


@app.get("/directory/users")
async def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=2, ge=1, le=100),
    x_api_key: str | None = Header(default=None),
) -> DirectoryPage:
    if x_api_key != "local-development-key":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    start = (page - 1) * per_page
    total_pages = max(1, (len(SYNTHETIC_USERS) + per_page - 1) // per_page)
    return DirectoryPage(
        page=page,
        total_pages=total_pages,
        users=SYNTHETIC_USERS[start : start + per_page],
    )


@app.get("/directory/users/{user_id}")
async def get_user(
    user_id: str,
    x_api_key: str | None = Header(default=None),
) -> DirectoryUser:
    if x_api_key != "local-development-key":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    for user in SYNTHETIC_USERS:
        if user.id == user_id:
            return user
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@app.post("/notifications/messages", status_code=202)
async def send_notification(
    notification: NotificationRequest,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
) -> NotificationReceipt:
    _require_bearer(authorization)
    if idempotency_key is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    return NotificationReceipt(
        accepted=bool(notification.channel and notification.message),
        message_id="message-001",
    )
