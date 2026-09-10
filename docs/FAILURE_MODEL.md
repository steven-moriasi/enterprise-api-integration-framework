# Failure Model

| Failure | Classification | Behavior |
|---|---|---|
| connect/read/write timeout | retryable | bounded retry, then `504` |
| connection or DNS error | retryable | bounded retry, then `502` |
| `401` / `403` | permanent | no retry; safe authentication error |
| `408`, `425`, `429`, selected `5xx` | retryable | bounded retry; `Retry-After` capped |
| other `4xx` | permanent | no retry; structured provider error |
| contract validation failure | permanent | fail closed; no partial model |
| open circuit | retryable later | immediate `503`, no network call |
| local rate exhaustion | delayed | async admission waits for refill |
| invalid webhook signature | permanent | `401` |
| stale webhook timestamp | permanent | `401` |
| webhook replay | permanent | `401` |

## Retry safety

Retries are opt-in per operation and are safe only when the provider operation is idempotent or
carries a provider-supported idempotency key. Directory and issue reads permit retries. The
notification adapter permits retries because it supplies an idempotency key. Issue creation uses
the safe default of one attempt because the sample contract does not claim provider-supported
idempotency.

## Error hygiene

Public errors contain provider name, stable code, retryability, and correlation ID. They exclude:

- raw provider response bodies;
- authorization headers;
- API keys and OAuth client secrets;
- full request payloads;
- internal exception strings.
