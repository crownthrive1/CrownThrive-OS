# PENTA Execution Norm

**Canonical rule:** CrownThrive Phase 3 work defaults to executable institutionalization, not planning-only prose.

## Build-first requirement

When a material gap is discovered, the normal Phase 3 disposition is to create or repair the smallest durable executable asset that closes it, then bind documentation and evidence to that implementation. Depending on scope, the asset may be software, validator, schema, migration, API/MCP contract, provider adapter, queue worker, test, CI workflow, recovery routine, registry entry, or machine-readable policy.

Documentation is required, but documentation alone does not prove execution.

## Required execution chain

`Discover gap → classify authority/risk → build candidate → validate → govern → implement through certified path → read back → preserve receipt → reconcile docs`

A step may end in HOLD or DENY. The chain must never manufacture authority merely to reach implementation.

## Gap closure states

- `GAP_DISCOVERED` — evidence identifies missing, stale, contradictory, or unbound capability.
- `BUILD_REQUIRED` — executable asset is needed.
- `DOCS_ONLY_VALID` — the gap is genuinely documentary and requires no runtime/code change.
- `CANDIDATE_BUILT` — implementation exists but is not yet accepted/deployed.
- `VALIDATED` — deterministic checks passed for the candidate's stated scope.
- `HOLD_AUTHORITY` — implementation exists but authority/evidence/provider certification is incomplete.
- `IMPLEMENTED` — bounded implementation occurred through an authorized path.
- `READBACK_VERIFIED` — independent or provider readback proves the stated implementation effect.
- `RECONCILED` — code, registry, docs, archive and evidence surfaces agree.
- `PRESERVED` — superseded state and receipts remain recoverable.

## Prohibited shortcuts

Do not call a gap closed merely because a README was written, a branch exists, a workflow file exists, a provider returned success without readback, a model generated code, a migration was drafted, or a historical phase label was renamed.

Do not delete historical evidence to make current-state scans pass. Retired phase labels, legacy product names, old contracts and prior release statements remain valid historical evidence when correctly classified.

## PENTA phase relationship

This is the default operating norm of **Phase 3 — Execute**. It prepares CrownThrive for **Phase 4 — Verify**, where independently reproducible assurance becomes dominant, and **Phase 5 — Preserve**, where durable continuity and inheritance become dominant.

The norm is recursive: every new subsystem still passes through Discover → Govern → Execute → Verify → Preserve within the current institutional generation.
