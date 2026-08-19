# Phase 2.99 Hard-Exit Closure Ledger — v1.2 Current-Main Rebaseline

**Packet:** `ct.closure.phase-2-99.hard-exit.v1`  
**Issue:** #84  
**Verification baseline main:** `ef04ea9a08960376859570bca8c6cf82a00442f2`  
**Canonical roadmap:** `CT-ADR-ROADMAP-010 / ten_phase_v1`  
**Current institutional state:** Phase 2 / 2.99  
**Phase 3:** `blocked_pending_phase_2_99_hard_exit`  
**External maturity observation:** `97/100 — A+` (non-authoritative)

## Current conclusion

The repository/security predecessor sequence has materially closed. PR #64 is canonical, issue #83 is closed after provider-perimeter certification and negative behavioral proof, PR #95 is canonical, and PR #65 is now canonical on the verification baseline above. This closes the repository/security canonicalization category; it does **not** complete Phase 2.99.

The hard-exit machine state is now **2 PASS / 6 blocking categories**. The external 97/A+ remains a quality signal only and cannot become a phase namespace, sovereign vote, approval, or hard-exit decision.

## Repository/security sequence — now PASS

The accepted sequence is:

1. PR #64 — Node-24/runtime and always-run fail-closed merge-gate bootstrap — merged canonical.
2. Issue #83 — provider `main` perimeter certification — closed completed; disposable PR #93 preserved the failing-required-check behavioral proof.
3. PR #95 — ruleset-vs-classic machine-state reconciliation — merged canonical.
4. PR #65 — nine-domain specialist enforcement, trusted exact-Git-diff binding, operational current-PR preflight and CodeQL log minimization — merged canonical at `ef04ea9a08960376859570bca8c6cf82a00442f2`.

GitHub remains technical defense-in-depth, evidence and transport. CrownThrive sovereign authority remains CT-ADR-GOV-011.

Accordingly `CT-P299-GATE-004 repository_security_governance_sequence_canonicalization` moves to **PASS**.

## Supabase RLS — remains PASS

Fresh read-only revalidation in this rebaseline pass confirms all six `integration_control` base tables have RLS enabled, `FORCE RLS` remains off, and each table has one explicit policy. Supabase Security Advisor currently reports **0 security lints**. Issue #79 is closed/completed. The former RLS-disabled finding remains historical evidence rather than a current blocker.

`CT-P299-GATE-005 integration_control_rls_security_disposition` remains **PASS**.

## Collab Portal — remains 4/7 fail-closed

Current canonical predicates remain:

| Predicate | State |
| --- | --- |
| `credential_exact_match` | PASS |
| `project_meta_authenticated` | PASS |
| `institutional_project_uid` | PASS |
| `approved_field_map` | BLOCKED |
| `authenticated_project_read` | PASS |
| `bounded_write_readback` | CLOSED |
| `webhook_sender_delivery_integrity` | BLOCKED |

`write_gate=false`. August authenticated request count remains **9 / 20,000**. No Collab write is authorized by this packet.

## API/MCP/provider closure — still open

CrownThrive IO remains read-verified and write-closed. The August request ledger observed in this pass is **31**, including the pre-existing hourly health probe. The health-probe pre-dispatch budget policy remains open.

The CrownThrive API/MCP control plane remains write-closed. Its hard-exit category is not certified. Open acceptance work includes verified D2 authority binding, direct Cell-07 governed CI, external-client conformance, JSON Schema 2020-12 validation, bounded MCP input/output schemas, server-side output validation, endpoint-catalog revocation enforcement, validated path-template dispatch, request/provider byte limits, timeout/cancellation, provider semantic validation, least-data projection, MCP parse/content-type/HTTP-status conformance, and atomic pre-dispatch audit/budget/rate reservation.

These are subconditions inside the existing closure estate; they do not create a new phase or sovereign category.

## Macro and identity closure — still open

The 68 / 82 / 85 / 74 source-count universes remain independent:

- 68 portfolio rows: 62 typed/classified, 6 identity items pending.
- 82 domain rows: current registrar/DNS/TLS/runtime certification incomplete.
- 85 engine/service rows: current provider/account/version/deployment/API/export certification incomplete.
- 74 platform/framework rows: 54 typed/classified, 20 current identities unresolved.

No count universe is promoted into production proof.

## 795 article estate — candidate advanced, canonical closure still open

PR #91 contains a deterministic 795-title/hierarchy machine-manifest candidate, but it remains non-canonical on this checkpoint. Therefore canonical state remains:

- source inventory: 795 / 795 verified;
- stable seed schema: defined;
- deterministic generator: present;
- complete machine manifest on canonical main: **false**;
- terminal dispositions: incomplete;
- P0/P1 substantive-or-explicit-unresolved closure: incomplete;
- full taxonomy/exposure/risk/owner/source/route/navigation disposition: incomplete.

A title manifest is not an article-body or terminal-disposition certification.

## Remaining hard-exit categories

The machine ledger now tracks eight categories with **2 PASS / 6 blocking**:

1. 68/82/85/74 current certification — NOT MET.
2. 795 terminal disposition + P0/P1 closure — NOT MET.
3. unresolved external state + explicit deferral closure — NOT MET.
4. repository/security sequence canonicalization — **PASS**.
5. integration-control RLS security disposition — **PASS**.
6. Collab seven-predicate certification — NOT MET, 4/7 passed.
7. restricted sources + continuity/recovery final adversarial audit — NOT MET.
8. exact canonical snapshot + Phase-3 entry packet — NOT MET.

Therefore:

```yaml
phase_2_99_exit: not_met
open_blocking_gates: 6
phase_2_complete: false
phase_3_entry: blocked_pending_phase_2_99_hard_exit
```

## Governed validator execution

This rebaseline adds a dedicated, read-only `Phase 2.99 Hard Exit Ledger` workflow. It directly runs:

- Python syntax validation;
- `scripts/validate_phase_2_99_hard_exit_ledger.py --self-test`;
- the full closure-ledger consistency validator;
- repository documentation governance;
- whitespace/conflict-marker checks.

The validator intentionally fails on five-phase re-promotion, premature Phase-3 opening, count-universe collapse, false 795 completion, false Collab completion, repository-canonicalization regression, stale PR #65 state, and stale RLS state.

**Validator PASS means ledger consistency PASS, not Phase-2.99 hard-exit PASS.**

## Docs impact and rollback

Docs impact: `docs_updated`.

Repository rollback is a normal revert of this bounded closure-ledger packet. Separate production RLS remediation retains its own migration/audit lineage and must never be widened or silently rolled back to make repository state convenient.

No provider write, credential mutation, payment, binding-rights action, Collab write, token/crypto activation, or Phase-3 production authority is introduced by this rebaseline.
