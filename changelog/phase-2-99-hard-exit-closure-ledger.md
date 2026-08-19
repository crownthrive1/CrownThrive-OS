# Phase 2.99 Hard-Exit Closure Ledger

**Packet:** `ct.closure.phase-2-99.hard-exit.v1`  
**Issue:** #84  
**Observed canonical main:** `12f0dd9ab97391a8dd34438f77262438c0df0999`  
**Canonical roadmap:** `CT-ADR-ROADMAP-010 / ten_phase_v1`  
**Current institutional state:** Phase 2 / 2.99  
**Phase 3:** `blocked_pending_phase_2_99_hard_exit`  
**External maturity observation:** `97/100 — A+` (non-authoritative)

## Current conclusion

The latest external Mintlify regrade is directionally correct: Phase 2.99 is no longer a general recovery exercise. It is operating as an institutional certification/reconciliation program. The remaining work is concentrated in current-state closure, articleization, accepted deferrals, provider proof, canonicalization and final adversarial recovery evidence.

The external score is useful as a progress indicator only. It cannot complete Phase 2, open Phase 3, replace CT-ADR-GOV-011, or alter the canonical `CT-ADR-ROADMAP-010 / ten_phase_v1` roadmap. Any five-phase wording in an external assessment remains non-authoritative superseded lineage.

This ledger is a **closure checkpoint**, not a completion declaration.

## What is already structurally established

Four macro source/count universes are independently recovered and must remain independent:

| Universe | Source count | Current closure state |
| --- | ---: | --- |
| Holdings portfolio rows | 68 | source count certified; 62 typed/classified; 6 identity items pending |
| Holdings domain rows | 82 | source count certified; registrar/DNS/TLS/runtime certification incomplete |
| Holdings engine/service rows | 85 | source count certified; provider/account/version/deployment/API/export certification incomplete |
| Phase-2.7 platform/framework rows | 74 | source count certified; 54 typed/classified; 20 current identities unresolved |

These counts are not interchangeable and none proves production deployment. The controlling dimension rule remains:

`priority ≠ lifecycle ≠ implementation state ≠ institutional disposition`

A P0 item may remain unverified. A live URL is not proof of every capability. A sunset record can retain rights, source, domain, contract, evidence and continuity obligations.

## External 97 → 100 ladder — current interpretation

The grader's ladder is retained only as a non-authoritative quality signal.

### 97 — certification/reconciliation program operating

**Observed.**

The program now has dedicated hard-exit, specialist, sovereignty/quorum, drift-refractory, Node-24 supply-chain, private-data, schema, macro-registry, identity, Collab and API/MCP certification lanes. That is evidence of program maturity, not proof that the hard exit passed.

### 98 — stable-ID / provider / domain / API-export / identity closure

**Not met.**

Remaining examples include:

- six Holdings portfolio identity-resolution items;
- twenty S103 current identity items;
- many-to-many engine/domain/current-provider relationship verification;
- current registrar/DNS/TLS/runtime evidence;
- current provider/account/version/deployment/API/export evidence;
- accepted current/historical/research/reserve/blocked/deferral dispositions for all material unresolved records.

### 99 — articleization + specialists + agent/security + Collab + retroactive final reconciliation

**Not met.**

The 795-title source inventory and deterministic generator are established, but terminal disposition and P0/P1 closure are incomplete. Final reconciliation must also close or explicitly defer contradiction records, specialist/security findings, retroactive Phase-2.0–2.9 impacts, restricted/private-source boundaries, continuity/recovery evidence, canonical branch sequence, and all remaining Collab predicates.

### 100 — authoritative hard-exit PASS

**Not met.**

A genuine 100 requires the machine hard-exit evaluation to say PASS on the exact canonical state, all required validation to be green, all material branches reconciled, no undisclosed blocker, reproducible recovery, and the Phase-3 hard-entry packet formally open.

No score, page count, CI run, branch name, preview, workstream pass or agent confidence can substitute for that record.

## Material closure achieved in this cycle — Supabase RLS

One previously blocking security category materially moved.

The six private `integration_control` tables originally had RLS disabled, although `anon` and `authenticated` also lacked schema/table access. The founder explicitly authorized the remaining production hardening in this closure cycle.

Tracked Supabase migrations now:

1. enable RLS on all six `integration_control` base tables;
2. add explicit service-role-only ALL policies without adding client-role policies or grants.

Post-change evidence confirms:

- all six tables report `relrowsecurity=true`;
- `relforcerowsecurity=false` remains deliberate;
- `anon` and `authenticated` still have no schema usage/table access;
- the existing service-role snapshot/rate-check runtime path passes after the change;
- no provider mutation was invoked by the smoke;
- Supabase security advisor now reports **zero security lints**;
- machine gate `crownthrive_api_control / integration_control_rls_defense_in_depth` is now `passed`.

The hard-exit RLS category therefore moves from `not_met` to `pass`. Fresh independent Agent S and Agent D review is still required before repository promotion decisions; a technically remediated external security finding does not self-merge PR #64.

## Current repository/security sequence

Canonical `main` remains the merged PR #63 baseline observed by this packet.

PR #64 remains open and non-canonical. Its current role is the Node-24 runtime/supply-chain and always-run fail-closed GitHub-main perimeter bootstrap. The underlying RLS condition that contributed to the earlier Agent-S block is now remediated, so old RLS-based blocks must be re-evaluated against fresh evidence rather than carried forward mechanically.

Issue #83 remains the provider-admin activation gate. It must not run before the #64 substrate is canonical. If #64 is adopted, #83 then proves the actual GitHub `main` perimeter: PR-before-merge, required `CrownThrive governed merge gate`, strict/current-with-main, blocked force pushes/deletion, and no routine bypass outside explicit D3 break-glass.

PR #65 remains behind #64/#83 and must reconcile onto the resulting canonical state before fresh exact-head votes count.

PR #66 / issue #79 now preserve both the original RLS finding and the authorized remediation/revalidation evidence.

## Collab Portal — current 4/7 state

Collab remains fail-closed, but its earlier credential/authentication blockers are no longer current.

| Canonical predicate | State |
| --- | --- |
| `credential_exact_match` | **PASS** |
| `project_meta_authenticated` | **PASS** |
| `institutional_project_uid` | **PASS / pinned** |
| `approved_field_map` | **BLOCKED** |
| `authenticated_project_read` | **PASS** |
| `bounded_write_readback` | **CLOSED** |
| `webhook_sender_delivery_integrity` | **BLOCKED** |

The authenticated Collab request ledger remains **9 / 20,000** for August at this checkpoint. The private fallback notification route remains active until all seven predicates pass simultaneously.

The candidate write projection remains intentionally narrow: `status` + `info_description`; `project_custom_fields` remains excluded. This ledger does not self-approve that D2 field map or enable provider writes.

## Articleization closure

The Help Center estate remains one of the largest concentrated gaps:

```text
source inventory                 795 / 795 verified
stable article schema            defined
deterministic generator          present
full generated machine manifest  pending
terminal dispositions            incomplete
P0/P1 substantive-or-unresolved  incomplete
navigation/route/source/risk     incomplete across full estate
```

Every recovered title must terminate in an inspectable state such as substantive canonical article, merged successor, redirect, restricted record, superseded-history record, explicit unresolved-source record or another governed terminal disposition. A title/branch/generator alone is not article completion.

## Final-deferral contract

Phase 2 does not require every provider to become connected or every historical body to be recovered. It requires every material unresolved item to terminate in an inspectable disposition.

An accepted deferral must include at least:

```yaml
deferral_id: ct.deferral.<stable-id>
subject_id: <stable institutional object>
current_state: not_connected | unverified | blocked | source_not_recovered | owner_input_required | other_explicit_state
why_unresolved: <evidence-based reason>
risk_class: D0 | D1 | D2 | D3
blocking_phase_2_99_exit: true | false
authority_for_nonblocking_deferral: <decision or approval reference>
evidence_refs: []
owner_or_queue: <stable role/queue>
revisit_trigger: <event/evidence/date>
continuity_or_fallback: <if applicable>
docs_impact: docs_updated | docs_no_change | docs_delta_opened
```

Missing evidence is never permission. Safety, legal authority, security, rights, money, privacy, source integrity or continuity cannot be made nonblocking merely to improve a score.

## Current hard-gate count

The machine ledger now records eight categories, with **one passed and seven still blocking**:

1. 68/82/85/74 current certification — open;
2. 795 terminal disposition + P0/P1 closure — open;
3. unresolved external state + explicit deferral closure — open;
4. repository/security sequence canonicalization — open;
5. integration-control RLS security disposition — **PASS**;
6. Collab seven-predicate certification — open, 4/7 passed;
7. restricted sources + continuity/recovery final adversarial audit — open;
8. exact canonical snapshot + Phase-3 entry packet — open.

## Machine validator

`developers/manifests/phase-2-99-hard-exit-ledger.v1.json` is the public-safe current checkpoint.

`scripts/validate_phase_2_99_hard_exit_ledger.py` now rejects:

- five-phase re-promotion;
- count-universe collapse;
- false article completion;
- stale pre-remediation RLS state;
- stale pre-authentication Collab state;
- premature Phase-2 completion / Phase-3 opening;
- loss of #64 → provider-enforcement sequencing;
- promotion of the external 97/98/99/100 ladder into institutional authority.

Validator PASS means **ledger consistency PASS**, not hard-exit PASS.

## Workflow integration boundary

This bounded packet still does not change `.github/workflows/**` or the #64/#65 owned agent-governance surfaces. Once the predecessor sequence is dispositioned, Agent A may wire the closure validator into the always-run governed merge gate without colliding with the bootstrap packet.

## Hard-exit decision rule

```text
recover
→ reconcile
→ classify
→ resolve or explicitly defer
→ prove macro current-state closure
→ prove article/P0/P1 closure
→ prove security/repository/provider boundaries
→ prove continuity/recovery
→ adversarial audit
→ canonicalize exact accepted state
→ evaluate every hard-exit predicate
→ certify only if all blocking gates pass
```

Until then:

```yaml
phase_2_99_exit: not_met
open_blocking_gates: 7
phase_2_complete: false
phase_3_entry: blocked_pending_phase_2_99_hard_exit
```

## Rollback

The repository portion of this packet is reverted by reverting the bounded closure-ledger commits. The separate Supabase RLS remediation is migration-addressable and contains no data rewrite; any rollback must preserve audit evidence and rerun the same security/runtime controls rather than widening client access.
