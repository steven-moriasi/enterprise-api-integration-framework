# Roadmap

## Operation safety

- make retry permission and idempotency explicit in operation descriptors;
- support provider-specific `Retry-After` dates and quota-reset headers;
- add request deadlines propagated from callers;
- add bulkhead concurrency limits per provider.

## Distributed deployment

- evaluate Redis-backed token buckets and circuit observations;
- persist webhook replay keys with atomic expiry;
- coordinate OAuth refresh without creating a token-endpoint stampede;
- expose per-replica and aggregated provider health.

## Security

- add OIDC inbound authentication and scoped authorization;
- enforce provider host allow-lists at network and application layers;
- integrate workload identity and automated secret rotation;
- add payload classification and provider-specific redaction.

## Assurance

- run provider sandbox contract suites;
- add fault-proxy tests for latency, resets, malformed TLS, and truncated bodies;
- benchmark connection-pool and rate-limit behavior reproducibly;
- add OpenTelemetry traces with governed attributes.
