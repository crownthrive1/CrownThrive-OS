# Phase 2.99 hard-exit ledger v1.3 — deferral and drift reconciliation

## Scope

This bounded Agent-C packet reconciles the canonical Phase 2.99 hard-exit machine ledger to independently verified current evidence without editing the broad PR #101/#102 control-plane/agent ownership surfaces.

Canonical baseline at packet creation: `922a077cfd6cdb29cd47b4a5c3f13557bb26cd9e`.

Canonical authority remains `CT-ADR-ROADMAP-010 / ten_phase_v1` + `CT-ADR-GOV-011`. Phase 2 / 2.99 remains current. Phase 3 remains `blocked_pending_phase_2_99_hard_exit`.

Changed files are limited to:

- `developers/manifests/phase-2-99-hard-exit-ledger.v1.json`;
- `scripts/validate_phase_2_99_hard_exit_ledger.py`;
- this changelog.

## Evidence reconciled

### Integration-control RLS drift

Permissioned read-only Supabase metadata at `2026-08-20T00:38:45.535280Z` shows:

- 15 current `integration_control` base tables;
- 15/15 RLS enabled;
- 15/15 tables covered by an explicit `service_role`-only `ALL` policy;
- `FORCE RLS` disabled on all current tables;
- no missing-RLS or missing-policy table in the observed estate.

The ledger therefore preserves `CT-P299-GATE-005 = PASS` while updating the dated current observation from 12/12 to 15/15. The validator enforces coverage equality rather than treating a historic table count as timeless security policy.

### Reconciliation-tag estate

Current tag telemetry is recorded as a volatile evidence snapshot:

- 170 authoritative scopes;
- 87 `PASS`;
- 53 `OPEN`;
- 15 `BLOCKED`;
- 10 `CLOSED`;
- 5 `DEFERRED`;
- all 170 remain scan-required and reconcile-required.

Latest L/M/N/O scan remains `partial`: 170 tagged/reconciled scopes, 8 drift scopes and 73 unresolved scopes. `PASS` remains drift-watched, `DEFERRED` remains NOT-PASS, and unavailable/unknown evidence is never converted to zero or PASS.

### Executive override #120

Founder decision #120 is reconciled as a bounded governance deferral, not technical certification.

- Collab Portal remains technically 6/7; provider sender/delivery integrity is unproven.
- Partnero live secret-backed webhook delivery remains unproven.
- Stripe institutional live signature-backed webhook delivery remains unproven.

The three live-delivery requirements are recorded as `governed_deferred_not_passed` for current blocking effect with compensating fail-closed controls and mandatory point-of-use reopen triggers. No technical PASS is manufactured.

For Phase 2.99 accounting, `CT-P299-GATE-006` changes from blocking `not_met` to nonblocking `deferred_accepted_not_passed`. The five unrelated gates `001`, `002`, `003`, `007` and `008` remain blocking. GATE-008 remains explicitly fail-closed while any upstream requirement remains unresolved.

### Current API/MCP evidence

CrownThrive IO remains `read_verified_write_closed`. The founder unlimited-call policy and scheduled health-probe policy are recorded as passed policy controls; request counts remain timestamped volatile telemetry rather than fail-closed ceilings. Provider writes remain closed.

## Validator changes and negative cases

The v1.3 validator now fails on:

- five-phase re-promotion;
- premature Phase 3 opening;
- 68/82/85/74 count collapse;
- false articleization completion;
- reconciliation-tag arithmetic or DEFERRAL-to-PASS drift;
- false Collab 7/7 or technical webhook PASS;
- any deferred provider-delivery row claiming technical PASS;
- loss of mandatory deferral reopen triggers;
- GATE-006 being relabeled technical PASS;
- premature GATE-008 PASS;
- repository-canonicalization regression;
- RLS coverage or policy/table mismatch;
- invalid/negative volatile observations;
- external assessment being promoted into hard-exit authority.

Positive controls prove external grades and request counters may change without becoming timeless institutional authority.

## Governance and collision state

Risk class: **D2** because the patch changes Phase 2.99 hard-exit blocking accounting while preserving the underlying technical NOT-PASS state.

Applicable independent specialist review includes Security & Privacy, Operations/SRE, AI/ML/LLM TEVV and any additional cells derived by the canonical trusted-diff preflight. Agent C materially originated this packet and must not self-vote.

PR #101 and PR #102 are current-main reconciliation-held broad packets. This bounded patch intentionally avoids their owned agent/control-plane files. Any later Agent-O integration must preserve this ledger decision, unique evidence and history rather than flattening it.

## Documentation impact

`docs_updated` through the canonical machine ledger and this public-safe changelog. No raw secrets, fingerprints, provider payloads or private routing values are stored.

## Rollback and reopen

Rollback: revert this three-file packet. No provider/database/customer/payment/rights/credential state is mutated by the repository change.

Reopen or supersede this ledger evidence when:

- canonical `main` or relevant exact PR heads move;
- current RLS/policy coverage regresses or the schema changes materially;
- L/M/N/O detects material drift/contradiction;
- any #120 point-of-use condition becomes true;
- webhook receiver/signing/event scope/provider behavior materially changes;
- a new critical/high security finding appears;
- one of the remaining hard-exit gates gains or loses authoritative evidence.

## Downstream Phase 3–10 impact

Phase 3 may prepare the deferred webhook certifications but must reopen them before provider-push delivery becomes a correctness dependency. Phase 4/5 must enforce the service-specific reopen triggers before federated or revenue workflows rely on those webhooks. Phases 6–10 inherit the same distinction between technical PASS, governed deferral and unresolved state. No Phase 9 token/crypto capability or any phase transition is activated by this packet.
