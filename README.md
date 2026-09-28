# Enterprise API Integration Framework

A reference implementation for integrating third-party HTTP APIs through a consistent
typed, observable, and failure-aware boundary.

```text
gateway route
→ typed provider adapter
→ authentication strategy
→ local rate limiter
→ circuit gate
→ bounded retry loop
→ HTTP provider
→ contract validation
→ safe response or structured error
```

## Engineering evidence

- provider-specific typed adapters over a shared transport;
- API-key, bearer-token, and OAuth 2.0 client-credentials authentication;
- explicit timeouts, bounded retries, rate limiting, and circuit breaking;
- structured errors that do not leak provider bodies or credentials;
- correlation IDs, bounded-cardinality metrics, and structured logs;
- opaque-cursor models, origin-checked link pagination, and page-number pagination;
- signed webhook verification and replay detection;
- contract tests and containerized integration smoke tests.

The included providers are mock/public API shapes. They do not claim production tenancy,
partnership, or certification with the named vendors.

## Included integrations

| Adapter | Contract shape | Authentication | Pagination |
|---|---|---|---|
| GitHub issues | issue creation and listing | bearer token | RFC 8288 `Link` |
| Enterprise directory | user lookup and listing | API key | page number |
| Notification provider | idempotent message submission | bearer token | not applicable |
| Billing webhook | signed event delivery | HMAC SHA-256 | not applicable |

The local `mock-provider` implements deterministic provider contracts for tests and Compose smoke
verification. Production deployments should point each adapter at its real provider endpoint and
inject credentials through a secrets manager.

## API surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | process liveness |
| `GET` | `/ready` | process readiness |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/integrations/directory/users` | list directory users |
| `GET` | `/integrations/directory/users/{id}` | fetch one directory user |
| `GET` | `/integrations/github/{owner}/{repo}/issues` | list issues |
| `POST` | `/integrations/github/{owner}/{repo}/issues` | create an issue |
| `POST` | `/integrations/notifications` | submit an idempotent notification |
| `POST` | `/webhooks/billing` | verify and accept a signed webhook |

## Quick start

```bash
cp .env.example .env
docker compose up -d --build --wait
curl --fail http://localhost:8003/health
python scripts/compose_smoke.py
```

The values in `.env.example` are local-development fixtures, not production credentials.

## Local verification

```bash
ruff check app tests scripts
mypy app tests scripts
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
pip-audit
docker compose config --quiet
docker build .
```

## Design and operations

- [Architecture](docs/ARCHITECTURE.md)
- [Failure Model](docs/FAILURE_MODEL.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Operations Runbook](docs/OPERATIONS.md)
- [Roadmap](docs/ROADMAP.md)
- [Architecture decisions](docs/adr/)

## Explicit limitations

- Rate limits and circuit state are process-local; distributed coordination needs Redis or another
  shared store.
- OAuth token caching is process-local and does not implement token revocation callbacks.
- Webhook replay state is in memory and is lost on restart.
- The gateway has no inbound operator authentication because it is a transport demonstration, not
  a deployable enterprise edge service.
- No live third-party credentials, production traffic, availability result, or throughput claim is
  included.
