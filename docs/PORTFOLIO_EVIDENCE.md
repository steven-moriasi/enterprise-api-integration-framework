# Portfolio Evidence

| Capability | Inspectable evidence | Verification |
|---|---|---|
| typed clients | provider Pydantic models and adapters | provider contract tests |
| authentication | API key, bearer, OAuth client credentials | auth tests |
| retries and timeouts | shared transport policy | transient failure tests |
| circuit breaking | closed/open/half-open state machine | recovery and probe tests |
| rate limiting | async token bucket | deterministic refill test |
| structured errors | integration error hierarchy | body-leak and status tests |
| correlation IDs | outbound header and safe error context | transport tests |
| pagination | page-number, safe links, opaque cursor model | pagination and adapter tests |
| webhook handling | HMAC, timestamp, replay guard | webhook tests and Compose smoke |
| logging and metrics | structured request event and bounded labels | metrics API and smoke |
| containers and CI | pinned image, Compose, GitHub Actions | local build and smoke commands |

## Non-claims

This repository does not claim:

- that fifteen live integrations are included;
- that the adapters processed production traffic;
- a provider partnership or certification;
- measured throughput or availability;
- complete production gateway security.

It demonstrates reusable engineering mechanisms consistent with safely integrating many APIs.
