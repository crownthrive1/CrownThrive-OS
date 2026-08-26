# PentaCompliance + PentaLicense Execution Roadmap

**Effective:** 2026-08-26  
**Mode:** execution ledger, not speculative plan  
**Owner:** CrownThrive LLC

This roadmap records what was built and the evidence still required for each larger execution scope. A later scope cannot inherit a pass from an earlier one.

| Lane | Current state | Exit evidence | Operating rule |
| --- | --- | --- | --- |
| Canonical identity | `PRODUCTION` | Family registry resolves `penta.compliance` and `penta.license` | Unknown or duplicate identities fail closed. |
| Obligation evidence evaluation | `PRODUCTION` | Deterministic runtime, negative tests, immutable receipts | Evaluates adopted sources only; no universal legal attestation. |
| License eligibility | `PRODUCTION` | Exact rights/asset/terms/acceptance tests and stress gate | Any missing or excess right produces a hold. |
| Internal immutable grant | `PRODUCTION` | Decision-bound grant hash and idempotent replay | Grant is append-only; lifecycle changes never rewrite it. |
| Command Center custody | `PRODUCTION` after deployment receipt | Authenticated D1 records, same-origin writes, evidence chain, deployed readback | Founder/operator writes; auditor reads; public sees no private records. |
| Provider issuance | `HOLD_PROVIDER_BINDING` until exact adapter proof | Certified operation, credential reference, canary, exact readback | Provider-ready is not provider-sent. |
| Binding legal attestation | `HOLD_HUMAN_AUTHORITY` | Applicable counsel/signatory authority and evidence sufficiency | Software does not practice law or self-attest. |
| D3/reviewed licensing | `HUMAN_REVIEW_REQUIRED` | PentaHybrid approval and accountable authority | D3 remains human-reserved. |
| Payments/royalties/entitlements | `HOLD_ECONOMIC_RAIL` until separately certified | Price authority, settlement, tax, entitlement and readback receipts | A license record does not move money or grant platform entitlement by itself. |
| Governed self-build | `PRODUCTION_CONTROL_CONTRACT` | Per-candidate exact tests, independent certification, release and readback | Every Penta can request software; none can self-promote it. |

## Maintenance cadence

- Re-evaluate obligations whenever an adopted source, jurisdiction, scope or effective date changes.
- Re-evaluate every license request when the asset hash, rights profile, terms, identity or acceptance changes.
- Append lifecycle events for amendments, renewals, suspensions and revocations.
- Run the compliance/license unit and stress gates on every affected pull request and main push.
- Reconcile Command Center records to source/provider readback; preserve mismatches as holds.
- Open a typed PentaRFA gap when any registered member lacks required software behavior.

## Convergence definition

Convergence means source, runtime, registry, tests, deployed Command Center and provider readback agree for the same exact scope. It never means converting unknown provider/legal/economic state into green status.
