# CrownThrive Penta Assignment Fulfillment & Institutionalization v1

## Canonical contracts

- Assignment fulfillment: `ct.penta.assignment-fulfillment.v1`
- Institutionalization: `ct.penta.institutionalization.v1`
- Change rule: `ct.penta.change-institutionalization.rule.v1`
- PR terminalization: `ct.penta.pr-terminalization.v4`

## Rule

Every CrownThrive D0–D2 technical or evidence change must be represented by a stable assignment contract, routed to its owning Pentas and constitutional Penta family, completed against exact artifacts and acceptance criteria, independently certified when required, and institutionalized before its linked pull request may merge or close.

Institutional completion requires all of the following:

1. The exact artifact, digest and—when source-controlled—the exact Git head are bound.
2. Every assigned owner Penta has a latest immutable `PASS` result. An older pass cannot override a newer hold or failure.
3. The provider projection is mirrored three ways in Drive:
   - Human guide/record
   - Hybrid architecture/evidence dossier
   - Machine ledger spreadsheet
4. DAIL-EVIDENCE, DAIL-DECISION and DAIL-EXECUTION events append through the governed CHLOM contract and independently read back.
5. PentaDocs projects the current institutional record and reads it back.
6. D1–D2 work receives an independent PentaCertify decision. The originator cannot certify its own mutation.
7. CrownThrive OS projects and reads back the exact assignment/certification state.
8. DAIL chain verification passes after the activation event is appended and read back.
9. Only then may the native PentaPR terminal provider perform an exact-head merge or close and record provider readback.

A green build, provider acceptance, a documentation page, a crawler observation or a GitHub workflow result is not independently sufficient.

## Authority boundaries

The fabric supports D0–D2 only. It does not create or expand authority. D3 and human-reserved matters remain outside autonomous execution, including sovereign votes/quorum, legal or professional determinations, final rights grants, material money movement, credential creation or rotation, final contract acceptance and authority expansion.

Assignment contracts permanently set:

- `money_movement_allowed = false`
- `credential_change_allowed = false`
- `authority_expansion = false`
- `d3_human_reserved = true`

## Owner and certifier separation

`owner_pentas` identify the builders, operators, projectors and specialist owners responsible for producing the work and evidence. `PentaCertify` is a separate verifier. A certification is rejected if its verifier is present in the owner set.

PentaCrawler and PentaCensus may discover and route work. They do not convert discovery into PASS. PentaDocs and PentaDrive project evidence. They do not certify the mutation. PentaPR, PentaMerge and PentaCloser execute terminal provider actions only after the institutional gate returns `PASS`.

## Constitutional family obligations

All fifteen constitutional families have active obligation contracts in `integration_control.penta_family_obligation_contracts_v1`:

1. Automation & Agentic
2. Build, Certification & Release
3. Commerce & Economy
4. Communications & Service
5. Governance, Legal & Institutional Controls
6. Intelligence, Research & Impact
7. Knowledge, Semantics & Data
8. Media, Studio & Publishing
9. Observability & Organic Systems
10. Resilience & Continuity
11. Routing & Interoperability
12. Security, Identity & Trust
13. System Architecture
14. Transport & Capability Primitives
15. Workforce & People

The family contract coordinates responsibilities; it does not promote every member runtime or manufacture member authority.

## Lifecycle

`DISCOVERED → ROUTED → IN_PROGRESS/AWAITING_PROJECTION → AWAITING_CERTIFICATION → CERTIFIED → COMPLETED`

Terminal and exception states are `HOLD`, `FAILED`, `SUPERSEDED` and `RETIRED`. Historical owner results and assignment events are append-only. Corrections add superseding records rather than rewriting history.

## Native execution

The fulfillment cycle runs inside the existing `ct-penta-self-v1` native clock through `public.penta_self_tick_v1()`. No additional cron or external scheduler is created.

## PR terminalization

GitHub Actions are classification and evidence-projection surfaces only. They do not merge or close PRs. The only terminal provider mutation lane is the authenticated Supabase Edge Function `penta-pr-terminal-provider` v4.

Immediately before every provider mutation, v4 calls `public.penta_assignment_pr_terminal_gate_v1(repo, pr_number, exact_head_sha, action)`. It refuses deadline-only closure, retroactive merge and retroactive close. Historical backfill is provider-truth projection only.

## Evidence-preserving rollback

Rollback never deletes assignment, result, PentaDocs, Drive or DAIL history. The bounded rollback procedure:

1. Place `ct.penta.change-institutionalization.rule.v1` in `HOLD`.
2. Restore the prior PentaSELF tick without the assignment cycle.
3. Redeploy the exact retained v3 terminal-provider source/digest if v4 caused a regression.
4. Keep v4 terminal actions fail-closed while repair occurs.
5. Append rollback, readback and supersession events through DAIL.
6. Require independent recertification before reactivation.

The rollback source is stored under `supabase/rollback/penta-assignment-institutionalization-v1/` and does not weaken public ACLs or destroy evidence.
