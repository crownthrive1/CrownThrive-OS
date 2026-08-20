# Phase 2.99 hard-exit ledger v1.3.1 — post-PR91 current-truth reconciliation

**State:** candidate / governed D2 reconciliation  
**Canonical baseline:** `8fcb68bf209e32ba2cd265e1b6ca730cb8da64d7`  
**Roadmap authority:** `CT-ADR-ROADMAP-010 / ten_phase_v1`  
**Phase:** 2 / 2.99; Phase 3 remains `blocked_pending_phase_2_99_hard_exit`

## Why this patch exists

Canonical `main` advanced through governed PR #91 after the first v1.3 deferral packet was published. That merge makes exactly one new Workstream-0 predicate true: the complete deterministic 795-title/hierarchy machine manifest now exists in canonical Git. It does **not** close historical body recovery, terminal disposition, P0/P1 substantive closure or GATE-002.

At the same time, the authoritative reconciliation-tag universe continued to grow while the most recent persisted full L/M/N/O scan remained on an older 170-scope universe. The ledger therefore represents current tag truth and formal-scan coverage as separate dimensions instead of forcing equality between them.

## Current permissioned evidence

### GitHub / Workstream 0

- canonical `main`: `8fcb68bf209e32ba2cd265e1b6ca730cb8da64d7`;
- PR #91 accepted head: `aeb1dbce17e4df7e351ff5d10fb2078a6a628a09`;
- `complete_machine_manifest_generated_in_repo = true`;
- GATE-002 remains NOT-MET because S94 body recovery, terminal disposition and P0/P1 closure remain unresolved.

### L / reconciliation tags

Current authoritative registry snapshot:

- 207 total;
- 121 PASS;
- 53 OPEN;
- 12 BLOCKED;
- 13 CLOSED;
- 8 DEFERRED.

All 207 remain scan-required and reconcile-required. PASS remains drift-watched. DEFERRAL remains NOT-PASS. UNKNOWN is never promoted to zero/PASS.

### M / permissioned sources

This bounded pass successfully read current GitHub, connected Supabase, Mintlify deployment/Git-source state, Google Drive Help Center structure sources and Gmail SimpleBase outage history. This is **not** an exhaustive institutional-source-recovery claim. A full current-scope source scan is still required before GATE-003 can close.

### N / proof boundary

The last persisted formal L/M/N/O scan remains:

- scanner: `ct.reconciliation.lmno.agent-e`;
- 170 tagged / 170 reconciled;
- 8 drift;
- 73 unresolved;
- status `partial`.

Against the current 207-scope registry, formal scan coverage is therefore incomplete by **37 scopes**. The validator now treats that as a first-class coverage gap instead of requiring a stale scan total to equal the moving current registry.

### Supabase RLS

Fresh permissioned PostgreSQL catalog/policy evidence confirms:

- 15 current `integration_control` base tables;
- 15/15 RLS enabled;
- 15/15 explicit `ALL` policies;
- all 15 policies scoped to `service_role`;
- FORCE RLS = 0.

GATE-005 remains PASS and drift-watched. The validator checks coverage equality rather than pinning a timeless 15-table constant, so future table growth fails closed unless every new table is also RLS- and policy-covered.

### #120 governed delivery deferrals

The founder-authorized Collab / Partnero / Stripe delivery dispositions remain **governed deferred / technically NOT-PASS**. Technical evidence is not fabricated. Each service retains its point-of-use reopen trigger, and Collab remains technical 6/7 with private fallback tracking active.

## Roadmap-v2 / full-documentation hard gate

Founder issue #123 establishes a prospective 20-phase direction plus a **non-deferrable full-documentation-estate reconciliation gate before Phase 3**. This patch records that direction without changing current roadmap authority:

- current canonical roadmap stays `CT-ADR-ROADMAP-010 / ten_phase_v1`;
- target 20-phase migration is `pending_governed_adr_and_machine_namespace`;
- Phase 3 does not move;
- GATE-008 remains fail-closed while the full-documentation estate is incomplete.

Issue #128 is retained as a prospective Phase-20 domain/DNS/custom-domain continuity gate. Mintlify currently uses its default deployment domain; custom-domain activation remains governed-deferred/not-PASS and is not made a Phase-3 prerequisite.

## Known documentation projection drift

The current Help Center seed page still states `complete_machine_manifest_generated_in_repo: pending_governed_merge`, which is stale after PR #91. That drift remains explicit and is owned by the full-documentation reconciliation campaign rather than being silently ignored or used to regress the canonical machine predicate.

## Validator changes

The v1.3.1 validator now:

- requires PR #91 canonical materialization while retaining every substantive articleization field as open;
- rejects premature 20-phase canonical promotion before a governed roadmap-v2 migration;
- separates current tag-universe truth from persisted formal-scan coverage;
- requires the formal coverage gap to be arithmetically correct;
- keeps GATE-003 blocking while formal scan coverage is incomplete;
- requires Agent-M source accounting to separate attempted, read and unavailable sources;
- validates dynamic all-table RLS/policy coverage rather than a fixed table count;
- preserves #120 technical-NOT-PASS semantics and reopen triggers;
- requires the non-deferrable full-documentation gate to remain in GATE-008;
- rejects premature GATE-008 or Phase-3 promotion.

## Docs impact, rollback and reopen

`docs_updated`.

Rollback is a straight revert of this bounded ledger/validator/changelog update. No provider, credential, customer, payment, rights, production, DNS or phase mutation occurs.

Reopen on canonical-main/head movement, RLS/policy drift, material L/M/N/O contradiction or coverage change, #120 point-of-use trigger, roadmap-v2 canonical migration, full-documentation-estate disposition change, or any new critical/high finding.

## Downstream

Phases 3–10 continue to inherit the current ten-phase contract until roadmap-v2 is separately governed. Future roadmap-v2 Phases 11–20 are recorded as prospective only. The full-documentation hard gate, source-accounting discipline, point-of-use reopen triggers and evidence distinctions must survive any later roadmap migration.
