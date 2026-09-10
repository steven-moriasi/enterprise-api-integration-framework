# ADR 0003: Verify webhooks before parsing

## Status

Accepted.

## Context

Parsing and re-serializing JSON before signature verification can change bytes and invalidate the
sender's signing contract. It also increases work performed for forged requests.

## Decision

Verify timestamped HMAC signatures over the raw request body, register replay state, and only then
hand the body to downstream processing.

## Consequences

Signature behavior matches byte-level provider contracts. Replay state must become durable and
distributed before horizontal production deployment.
