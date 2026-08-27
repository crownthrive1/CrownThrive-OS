# PentaRG™ — Release Governance & Recovery

PentaRG is the CrownThrive OS orchestration authority for release-gate reconciliation, bounded healing, refactoring control, update convergence, archive continuity, historical restoration, provider delivery, and interoperability.

It does **not** replace PentaGate, PentaHeal, PentaRanger, PentaCertify, PentaRelease, PentaDeploy, PentaPM, CHLOM, DAIL, PentaPolice, or PentaGovernance. It coordinates their registered authorities and emits a deterministic control receipt for every observation, plan, bounded mutation, and provider readback.

## Canonical loop

`PentaRG → PentaGate → PentaHeal → PentaRanger → PentaCrawler → PentaFlows → PentaHelper → PentaCertify → PentaPR → PentaMerge/PentaCloser → PentaRelease → PentaDeploy → PentaVercel → PentaRG readback → DAIL`

CHLOM and PentaPolice constrain the loop. PentaGovernance ratifies policy and founder-authority leases. DAIL receives hash-chained receipts. PentaPM owns projects, milestones, development links, and accountable work routing.

## Full autonomous governed mode

The production setting is `FULL_AUTONOMOUS_GOVERNED`:

- D0 and D1 actions are autonomous.
- D2 actions are autonomous only when exact-head evidence, deterministic tests, rollback, and provider readback are available.
- D3 remains founder-governed through a time-bounded lease. Expiration returns D3 to HOLD automatically.

The setting does not authorize branch-protection weakening, forced history rewrites, fabricated PASS states, secret-value disclosure, deletion of evidence, financial mutation, or provider-authority manufacture.

## Release-gate recovery classes

PentaRG distinguishes:

1. **Repository contract defects** — unpinned actions, unsafe permissions, missing topology assets, invalid source, or absent tests.
2. **Provider execution defects** — failed, cancelled, timed-out, startup-failed, or action-required runs.
3. **Source convergence defects** — stale same-repository PR heads that can be updated without force.
4. **Provider custody defects** — evidence must be refreshed by the registered provider-control workflow.
5. **Historical continuity defects** — missing required files are restored through a repair PR from canonical history; history is not rewritten.
6. **Duplicate/unbound workflow defects** — generic starter PRs are archived with an explicit tombstone and recoverable branch history.
7. **Delivery defects** — Vercel source, project binding, environment contract, preview, production, domain, runtime, and rollback are independently tracked.

## Vercel application plane

`apps/crownthrive-os-control-plane` is a buildless Vercel application for:

- Institutional Now
- release gates
- convergent topology
- DAIL receipts
- interoperability
- provider delivery bindings

The application deliberately reports `provider_readback: false` outside Vercel. Source readiness is not production deployment. The project must be created in team `crownthrive1s-projects`, rooted at `apps/crownthrive-os-control-plane`, then verified through preview and production readback.

## Archive and restore

Archival closes or tombstones superseded work without deleting the PR, branch, commit, or evidence history. Restoration uses exact canonical blobs or commits and creates a governed repair change. No reconstructed historical source may be represented as original provider history.
