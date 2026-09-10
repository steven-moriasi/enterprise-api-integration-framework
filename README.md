# Enterprise API Integration Framework

A portfolio/reference implementation for integrating third-party HTTP APIs through a consistent
typed, observable, and failure-aware boundary.

The framework demonstrates:

- provider-specific typed adapters over a shared transport;
- API-key, bearer-token, and OAuth 2.0 client-credentials authentication;
- explicit timeouts, bounded retries, rate limiting, and circuit breaking;
- structured errors that do not leak provider bodies or credentials;
- correlation IDs, bounded-cardinality metrics, and structured logs;
- cursor, link, and page-number pagination;
- signed webhook verification and replay detection;
- contract tests and containerized integration smoke tests.

The included providers are mock/public API shapes. They do not claim production tenancy,
partnership, or certification with the named vendors.

## Quick start

```bash
cp .env.example .env
docker compose up -d --build --wait
curl --fail http://localhost:8003/health
```

## Local verification

```bash
ruff check app tests
mypy app tests
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
docker compose config --quiet
docker build .
```
