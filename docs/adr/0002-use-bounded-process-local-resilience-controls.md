# ADR 0002: Use bounded process-local resilience controls

## Status

Accepted for the reference implementation.

## Context

Retries, rate limiting, and circuit breaking need executable evidence without introducing a
distributed state dependency unrelated to the repository's focus.

## Decision

Use bounded retries, an async token bucket, and a closed/open/half-open circuit per client process.

## Consequences

The behavior is deterministic and testable. Multiple replicas do not share quota or provider-health
state, so production adopters must choose explicit distributed semantics.
