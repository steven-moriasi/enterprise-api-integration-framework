# Security Policy

## Reporting

Report suspected vulnerabilities privately through GitHub's security advisory flow. Do not include
credentials, production payloads, or exploitable details in a public issue.

## Supported version

The latest `main` revision is the only supported portfolio version.

## Deployment warning

This reference implementation is not a production API gateway. Before deployment, add inbound
authentication and authorization, durable distributed replay protection, egress allow-listing,
provider-specific secret rotation, request-size enforcement at the edge, and centralized audit
retention.
