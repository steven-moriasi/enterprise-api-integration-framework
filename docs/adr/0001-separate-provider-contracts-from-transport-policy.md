# ADR 0001: Separate provider contracts from transport policy

## Status

Accepted.

## Context

Copying retry, authentication, logging, and timeout logic into every adapter causes inconsistent
failure behavior. A universal provider model, however, erases real differences in payload,
pagination, and idempotency semantics.

## Decision

Keep provider paths and typed contracts in adapters. Put common outbound mechanics in
`IntegrationClient`.

## Consequences

Policy fixes apply consistently. Provider-specific behavior remains visible. The client API must
stay small so it does not become a provider abstraction language.
