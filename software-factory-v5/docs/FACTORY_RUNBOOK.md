# CrownThrive Skills Factory Runbook

## Canonical flow

1. Load the 59-skill registry and nine-offer commercial registry.
2. Acquire the current UTC-hour idempotency key.
3. Select the next registry tranche without wrapping inside a cycle.
4. Generate exact-subject package and evidence manifests.
5. Run structural, negative, and secret-boundary validation.
6. Append production and factory-tick ledgers.
7. Emit one PentaGreen handoff per package.
8. Publish runtime state to `automation/skills-factory-state`.
9. Serve the latest state through `/api/factory/status`.
10. Surface provider and commercialization states in `/command-center/factory/`.

## Recovery

A repeated tick in the same hour returns the existing receipt and creates no duplicate package. A failed provider projection remains retryable in the warm lane. A rights, tax, money, entitlement, credential, provider-write, or readback defect remains a named HOLD rather than a false PASS.
