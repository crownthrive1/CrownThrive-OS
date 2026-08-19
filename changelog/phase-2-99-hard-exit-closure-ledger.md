# Phase 2.99 Hard-Exit Closure Ledger — v1.2.2 Snapshot-Semantics Self-Heal

**Packet:** `ct.closure.phase-2-99.hard-exit.v1`  
**Issue:** #84  
**Verification baseline main:** `ef04ea9a08960376859570bca8c6cf82a00442f2`  
**Canonical roadmap:** `CT-ADR-ROADMAP-010 / ten_phase_v1`  
**Current institutional state:** Phase 2 / 2.99  
**Phase 3:** `blocked_pending_phase_2_99_hard_exit`

## Current conclusion

The repository/security predecessor sequence remains canonically closed: PR #64 is canonical, issue #83 is closed after provider-perimeter certification and negative behavioral proof, PR #95 is canonical, and PR #65 is canonical. Repository/security canonicalization remains **PASS** and does not complete Phase 2.99.

This v1.2.2 self-heal repairs three machine-truth defects identified by independent C/D/S review of v1.2.1:

1. the validator incorrectly froze the non-authoritative external 97/A+ observation as a timeless CI invariant;
2. the current `integration_control` RLS evidence had expanded beyond the prior eight-table snapshot; and
3. volatile provider request counters were being validated as eternal exact values rather than timestamped runtime observations.

The repair changes evidence semantics, not hard-exit authority. The machine state remains **2 PASS / 6 blocking categories**. No new PASS category is manufactured.

## External assessment — explicitly non-authoritative and no longer CI-locked

The latest recorded external observation remains `97/100 — A+`, but it is now represented as a timestamped, volatile, **non-authoritative progress snapshot** with `hard_exit_decision_input=false`.

The validator no longer requires the exact numeric 97 or exact letter A+. It validates only that:

- the assessment authority remains `non_authoritative_progress_metric_only`;
- the snapshot is timestamped;
- any numeric grade is bounded to 0–100;
- any letter grade is a short non-empty string; and
- the external assessment cannot become a hard-exit decision input.

A self-test now proves that a later independent regrade (for example 96/A) remains ledger-valid without changing a single Phase-2.99 hard-exit predicate. A score change cannot break institutional CI merely because an external assessor changed its opinion.

## Supabase RLS — remains PASS; current live estate is 12/12

The original founder-authorized remediation remains preserved as a **six-table historical lineage record**. It is not rewritten.

Fresh read-only evidence for this reconciliation observes **12 current `integration_control` base tables**. All 12 have RLS enabled, `FORCE RLS` remains off, and all 12 have one explicit `service_role`-only `ALL` policy. `anon` and `authenticated` still lack schema USAGE and inspected table CRUD grants; `service_role` retains the required private control-plane access. Supabase Security Advisor currently reports **0 security lints**.

The current manifest records:

- original remediation count: 6;
- current live table count: 12;
- current policy count: 12;
- all-current-tables RLS state: PASS;
- client ACL denial preserved: PASS;
- Security Advisor lints: 0.

The existing live control-plane gate record still contains an older 8/8 observation in its reason/evidence text. This is explicitly labeled as **stale count evidence only**, not a current RLS regression. The direct read-only 12/12 evidence is the current snapshot; no production database mutation was performed in this repository self-heal.

`CT-P299-GATE-005 integration_control_rls_security_disposition` therefore remains **PASS**.

## Collab Portal — 6/7 and fail-closed

The canonical seven predicates remain:

| Predicate | State |
| --- | --- |
| `credential_exact_match` | PASS |
| `project_meta_authenticated` | PASS |
| `institutional_project_uid` | PASS |
| `approved_field_map` | PASS |
| `authenticated_project_read` | PASS |
| `bounded_write_readback` | PASS |
| `webhook_sender_delivery_integrity` | BLOCKED |

The approved bounded field map remains exactly `status + info_description`; the founder-authorized bounded write/readback evidence remains valid; the overall service `write_gate` remains false. The August request snapshot is **16 / 20,000**, now explicitly timestamped and marked `volatile_runtime_snapshot_not_ci_locked_counter`.

The validator enforces the seven-predicate state and that the observed request count is a non-negative snapshot within the positive configured limit, but it no longer treats `16` as an eternal CI constant.

`CT-P299-GATE-006 collab_portal_seven_predicate_certification` remains **NOT MET**, progress **6/7**.

## CrownThrive IO / API-MCP runtime — volatile counters separated from closure predicates

CrownThrive IO remains read-verified and write-closed. Fresh read-only runtime evidence observed **33 August requests**. That count is now stored with its period, timestamp and explicit volatile-snapshot semantics rather than as a timeless CI invariant.

The two Operations/SRE budget controls remain open:

- `monthly_request_budget_ceiling` — no authoritative monthly ceiling is currently configured;
- `scheduled_health_probe_budget_policy` — the scheduled probe still lacks a fail-closed pre-dispatch monthly-budget reservation policy.

The validator proves that a later increment in the IO request counter does **not** alter ledger validity, while a negative count, missing timestamp or authority-state change still fails closed.

The CrownThrive API/MCP control plane remains `write_gate=false` and hard-exit uncertified. Current open acceptance work remains explicit: verified D2 authority binding, direct Cell-07 governed CI, external MCP-client conformance, JSON Schema 2020-12 behavior, bounded inputs/outputs, runtime output validation, endpoint-catalog enforcement, path-template dispatch, byte/time bounds, provider semantic validation/projection, MCP parse/content-type/status conformance, atomic pre-dispatch audit/budget/rate reservation, an explicit monthly request ceiling and scheduled-probe budget policy.

No provider write is opened by this packet.

## Repository/security sequence — remains PASS

The accepted sequence remains:

1. PR #64 — Node-24/runtime and always-run fail-closed merge-gate bootstrap — canonical.
2. Issue #83 — provider `main` perimeter certification — closed completed; PR #93 preserves negative behavioral evidence.
3. PR #95 — ruleset-vs-classic machine reconciliation — canonical.
4. PR #65 — nine-domain specialist enforcement, trusted exact-Git-diff binding, operational current-PR preflight and CodeQL log minimization — canonical.

GitHub remains technical defense-in-depth, evidence and transport. CrownThrive sovereign authority remains CT-ADR-GOV-011.

`CT-P299-GATE-004 repository_security_governance_sequence_canonicalization` remains **PASS**.

## Macro, articleization and deferral closure — still open

The independent 68 / 82 / 85 / 74 source-count universes remain unchanged and not hard-exit certified:

- 68 portfolio rows: 62 typed/classified, 6 identity items pending;
- 82 domain rows: current registrar/DNS/TLS/runtime certification incomplete;
- 85 engine/service rows: current provider/account/version/deployment/API/export certification incomplete;
- 74 platform/framework rows: 54 typed/classified, 20 current identities unresolved.

PR #91 remains a noncanonical deterministic 795-title/hierarchy candidate only. It does not prove terminal disposition, article-body reconstruction, P0/P1 substantive-or-explicit-unresolved closure, full taxonomy/exposure/risk/owner/source/route/navigation disposition or Phase-2.99 exit.

Explicit deferrals, restricted-source final audit, and continuity/recovery reproducibility certification remain open.

## Remaining hard-exit categories

The machine ledger remains **2 PASS / 6 blocking**:

1. 68/82/85/74 current certification — NOT MET.
2. 795 terminal disposition + P0/P1 closure — NOT MET.
3. unresolved external state + explicit deferral closure — NOT MET.
4. repository/security sequence canonicalization — **PASS**.
5. integration-control RLS security disposition — **PASS**.
6. Collab seven-predicate certification — NOT MET, **6/7 passed**.
7. restricted sources + continuity/recovery final adversarial audit — NOT MET.
8. exact canonical snapshot + Phase-3 entry packet — NOT MET.

Therefore:

```yaml
phase_2_99_exit: not_met
open_blocking_gates: 6
phase_2_complete: false
phase_3_entry: blocked_pending_phase_2_99_hard_exit
```

## Governed validator self-heal

The dedicated read-only `Phase 2.99 Hard Exit Ledger` workflow remains the execution surface for:

- Python syntax validation;
- `scripts/validate_phase_2_99_hard_exit_ledger.py --self-test`;
- full ledger consistency validation;
- documentation governance; and
- whitespace/conflict-marker checks.

v1.2.2 preserves the original fail-closed tests for five-phase re-promotion, premature Phase-3 opening, count collapse, false article completion, false Collab completion, repository regression, stale PR #65 state and RLS regression. It adds negative tests for RLS policy/table mismatch, invalid snapshot counters/timestamps, external-assessment authority escalation and out-of-range grades. It also adds **positive invariants** proving that a non-authoritative external regrade and an incrementing IO request counter do not incorrectly fail institutional CI.

**Validator PASS means ledger consistency PASS, not Phase-2.99 hard-exit PASS.**

## Governance, docs impact and rollback

This is a bounded D2 institutional-evidence self-heal. Agent A materially performed the repair and therefore does not self-vote this exact head. Any prior B/C/D/S votes on v1.2.1 are stale after the head change. Fresh independent review is required, with the changed-domain specialist set expected to remain **Security & Privacy + AI/ML/LLM TEVV + Operations/SRE**.

Docs impact: `docs_updated`.

Rollback is a normal revert of this bounded ledger packet. No provider write, credential mutation, database mutation, payment, binding-rights action, Collab write, token/crypto activation or Phase-3 production authority is introduced by this self-heal.
