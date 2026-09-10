from pydantic import BaseModel, Field

from app.client import IntegrationClient


class NotificationRequest(BaseModel):
    channel: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4_000)


class NotificationReceipt(BaseModel):
    accepted: bool
    message_id: str


class NotificationAdapter:
    def __init__(self, client: IntegrationClient) -> None:
        self._client = client

    async def close(self) -> None:
        await self._client.close()

    async def send(
        self,
        notification: NotificationRequest,
        *,
        idempotency_key: str,
    ) -> NotificationReceipt:
        result = await self._client.request(
            idempotency_key=idempotency_key,
            json_body=notification.model_dump(),
            method="POST",
            operation="send_notification",
            path="messages",
            response_model=NotificationReceipt,
        )
        return result.data
