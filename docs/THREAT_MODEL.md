# Threat Model

## Assets

- provider API keys, bearer tokens, and OAuth client secrets;
- outbound authorization scope;
- customer and operational payloads;
- webhook authenticity;
- integration availability and provider quotas;
- correlation and audit evidence.

## Trust boundaries

1. caller to integration gateway;
2. gateway to third-party provider;
3. webhook sender to gateway;
4. runtime to secret store;
5. metrics and logs to observability backend.

## Threats and controls

| Threat | Control |
|---|---|
| credential disclosure | `SecretStr`, no header/body logging, environment injection |
| response-driven SSRF | origin validation for pagination links |
| retry amplification | bounded attempts, delay cap, circuit breaker |
| quota exhaustion | local token-bucket admission |
| schema confusion | strict typed response validation |
| replayed webhook | timestamp tolerance and one-time replay key |
| forged webhook | HMAC SHA-256 over timestamp and raw bytes |
| cardinality attack | fixed provider, operation, and outcome metric labels |
| provider body leakage | stable safe errors instead of raw responses |
| duplicate write | operation-level idempotency key where provider supports it |

## Production gaps

- inbound authentication and authorization;
- durable distributed replay storage;
- egress proxy or network-policy enforcement;
- secret rotation and workload identity;
- OAuth audience and scope governance;
- provider-specific payload redaction and data residency;
- tamper-evident long-term audit storage.
