# Operations Runbook

## Signals

- `/health`: process liveness;
- `/ready`: process readiness;
- `/metrics`: request totals and latency histograms with bounded provider, operation, and outcome
  labels;
- JSON logs: provider, operation, method, outcome, duration, and correlation ID.

Credentials, provider bodies, webhook bodies, and idempotency keys are not logged or used as metric
labels.

## Triage

### Increased `timeout` or `unavailable`

1. Check provider status and egress DNS/TLS connectivity.
2. Compare connect failures with read timeouts.
3. Confirm the timeout budget is below the caller's end-to-end deadline.
4. Avoid increasing retries until retry amplification and provider capacity are understood.

### Increased `circuit_open`

1. Inspect the preceding retryable provider failures.
2. Confirm only one half-open probe is admitted per process.
3. Do not force-close a circuit while the provider is still failing.
4. Reduce or pause upstream work if recovery attempts worsen an incident.

### Increased `contract_error`

1. Capture a redacted provider schema sample through approved tooling.
2. Compare it with the typed model and provider changelog.
3. Update the adapter and contract fixture together.
4. Do not weaken validation to accept unknown structures blindly.

## Deployment

1. Inject provider credentials from a secrets manager.
2. Configure outbound DNS and host allow-lists.
3. Run contract tests against provider sandboxes.
4. Build the pinned container image.
5. Deploy canaries and monitor per-provider outcomes.
6. Roll back if contract errors, authentication failures, or latency regress.

## Recovery limitations

Circuit, rate-limit, OAuth cache, and webhook replay state are process-local. Restarting clears that
state. This is acceptable for the reference implementation but must be addressed before relying on
it for distributed production enforcement.
