# CrownThrive Penta Assignment Institutionalization Rule v1

Canonical contract: `ct.penta.assignment-fulfillment.v1`

## Rule

Every material CrownThrive OS D0-D2 change must be owned by the appropriate Penta/family and completed through the canonical Penta Assignment Fulfillment fabric. A builder, crawler, provider, mailbox, database row, GitHub check, or documentation statement is evidence input; none is institutional completion by itself.

A change is terminal only after all required predicates are current and read back:

1. **Assigned owner execution** — stable assignment ID/key, owning family, owner Pentas, exact artifact/version/head/digest, authority ceiling, acceptance criteria, and bounded provider-write declaration.
2. **DAIL-EVIDENCE** — discovery/source/provider/runtime evidence is appended through the governed DAIL contract and read back.
3. **DAIL-DECISION** — PASS/HOLD/FAIL/UNKNOWN decision, authority basis, exact missing predicates, owner and supersession/causation are appended and read back.
4. **DAIL-EXECUTION** — mutation/build/test/rollback/deploy/readback result is appended and read back. No failed or held history is overwritten.
5. **Independent certification** — D1/D2 work requires an independent PentaCertifier/PentaCertify decision. Originators may never activate their own certificate.
6. **OS projection** — canonical CrownThrive OS/ThriveBase state must agree with the certified exact artifact.
7. **PentaDocs projection** — current human-readable operating documentation must be projected and read back; history remains append-only/superseding.
8. **Three-way Drive evidence mirror** — HUMAN document, HYBRID crosswalk document, and MACHINE sheet/manifest must be projected through the governed Drive/Sheets fabric and independently read back. Raw secrets and protected bodies stay in governed custody; mirrors carry safe references, hashes, timestamps, lineage and outcomes.
9. **DAIL chain gate** — current chain verification must PASS before terminalization.
10. **PR terminal gate** — a linked PR may merge/close automatically only when `public.penta_assignment_pr_terminal_gate_v1(...)` returns PASS for the exact current head and requested terminal action.

## Native ownership

`PentaCensus/PentaCrawler` discover and inventory. `PentaWire` resolves dependency and routing truth. Owning Pentas perform bounded work. `PentaBuild/PentaFactory` create or repair software. `PentaSecurity` performs bounded security review. `PentaTime/PentaCrons` own native scheduling. `PentaDocs` owns human-readable projection. `PentaDrive/PentaSync` own governed Drive/Sheets projection. `PentaCertify/PentaCertifier` remain independent. `PentaPR/PentaPM/PentaRelease` own exact-head PR/release terminalization.

## PR closure

PRs are not closed because an originator reports success. The assignment must be `COMPLETED`; evidence, decision, execution and activation readbacks must be true; PentaDocs, provider projection and OS projection must be `READBACK_PASS`; certification must be `ACTIVE` or explicitly `NOT_REQUIRED`; and the DAIL chain must be current PASS. The existing `penta_pr_terminal_reconcile` native executor then performs exact-head-fenced provider terminalization. Head movement invalidates the terminal packet and requires reread/reconciliation.

## D3 boundary

This rule creates no D3 authority. Human-reserved governance, legal/tax/professional determinations, rights grants, material money movement, credential creation/rotation, sovereign votes/quorum and authority expansion remain prohibited from autonomous completion.

## Current repair application

The credential-continuity repair is owned by PentaCredentials/PentaTime/PentaCrons/PentaBuild and moves the single canonical scheduler behind the hardened v3 contract. PentaSecurity receives a bounded D1 catalog/ACL review runtime so PentaDND and other registered systems can receive real security review without giving PentaSecurity D3 or certification authority. Both changes require independent certification and full assignment institutionalization before their repair PR terminalizes.
