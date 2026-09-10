import hashlib
import hmac
import http.client
import json
import time

HOST = "localhost"
PORT = 8003


def request(
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    outgoing_headers = {"Accept": "application/json"}
    if headers:
        outgoing_headers.update(headers)
    connection = http.client.HTTPConnection(HOST, PORT, timeout=5)
    try:
        connection.request(method, path, body=body, headers=outgoing_headers)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def json_body(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


def main() -> None:
    assert request("GET", "/health")[0] == 200
    assert request("GET", "/ready")[0] == 200

    _, directory_body = request("GET", "/integrations/directory/users")
    assert len(json.loads(directory_body)) == 3

    _, issue_list_body = request(
        "GET",
        "/integrations/github/astra/automation/issues",
    )
    assert len(json.loads(issue_list_body)) == 3

    issue_body = json_body({"title": "Compose contract", "body": "Smoke verification"})
    _, created_issue = request(
        "POST",
        "/integrations/github/astra/automation/issues",
        body=issue_body,
        headers={
            "Content-Type": "application/json",
            "X-Correlation-Id": "compose-smoke",
        },
    )
    assert json.loads(created_issue)["number"] == 101

    notification_body = json_body(
        {"channel": "operations", "message": "Compose smoke passed"}
    )
    _, notification = request(
        "POST",
        "/integrations/notifications",
        body=notification_body,
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": "compose-smoke-notification",
        },
    )
    assert json.loads(notification)["accepted"] is True

    webhook_body = json_body({"type": "invoice.paid"})
    timestamp = str(int(time.time()))
    signature = hmac.new(
        b"local-development-webhook-secret",
        timestamp.encode() + b"." + webhook_body,
        hashlib.sha256,
    ).hexdigest()
    webhook_headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": f"sha256={signature}",
        "X-Webhook-Timestamp": timestamp,
    }
    assert request(
        "POST",
        "/webhooks/billing",
        body=webhook_body,
        headers=webhook_headers,
    )[0] == 200
    replay_status, _ = request(
        "POST",
        "/webhooks/billing",
        body=webhook_body,
        headers=webhook_headers,
    )
    assert replay_status == 401

    _, metrics = request("GET", "/metrics")
    assert b"integration_framework_requests_total" in metrics


if __name__ == "__main__":
    main()
