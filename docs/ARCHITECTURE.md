# Architecture

## Boundary model

The framework separates provider contracts from cross-cutting transport policy:

```text
FastAPI route
  └─ provider adapter
       ├─ typed request/response models
       ├─ provider path and pagination semantics
       └─ IntegrationClient
            ├─ authentication strategy
            ├─ token-bucket admission
            ├─ circuit breaker
            ├─ timeout and bounded retry policy
            ├─ contract validation
            └─ logs and metrics
```

Provider adapters do not own retry loops or logging policy. The shared client does not understand
provider payloads. This keeps policy consistent without collapsing provider-specific semantics into
an unsafe universal abstraction.

## Outbound request sequence

1. The route validates the inbound request.
2. The adapter selects an operation and typed response model.
3. The local token bucket admits the call.
4. The circuit breaker rejects unhealthy providers before network work.
5. The authentication strategy supplies headers without exposing secrets to logs.
6. The client adds a correlation ID and optional idempotency key.
7. HTTPX applies connect, pool, read, write, and total operation timeouts.
8. Operations that explicitly permit retries use bounded backoff for retryable transport failures,
   `429`, and selected `5xx` responses.
9. Successful JSON is validated against the provider contract.
10. The adapter returns domain data; failures return a structured safe error.

## Circuit semantics

Closed circuits count retryable failures. At the threshold, the circuit opens. After the recovery
timeout, one half-open probe is admitted; concurrent probes fail fast. Success closes the circuit,
while another retryable failure reopens it.

The process-local circuit is deliberately simple. A horizontally scaled deployment needs a
decision on whether provider health is local to each replica or coordinated through shared state.

## Pagination safety

- Page-number adapters enforce page and maximum-page bounds.
- Link pagination follows only `rel="next"`.
- Absolute next links must retain the configured provider origin, preventing a provider response
  from redirecting authenticated pagination traffic to another host.
- Opaque cursor pages are modeled without interpreting provider cursor contents.

## Webhook boundary

Webhook signatures cover `timestamp + "." + raw_body`. Verification uses constant-time HMAC
comparison, a timestamp tolerance, and one-time replay registration. Payload hashes are returned;
the raw payload is not logged.
