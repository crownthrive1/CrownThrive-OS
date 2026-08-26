# PentaImmune System + PentaEVIBuilder

## Status

**Production — governed repository-local autonomic maintenance and evidence construction.**

Initial implementation merged through PR #533. The pre-merge head `1fb79c7130f3a039da82a488bc3e13f6cffde621` passed the required CrownThrive governed merge gate plus the dedicated PentaImmune assurance/evidence/certification/hunt workflow. The merged `main` SHA `0ad7aff61027be9913f84852a1286fb6a4f1c429` then passed PentaImmune deterministic assurance, independent exact-head certification, and the live read-only hunt. Production status is limited to the capabilities and boundaries documented here; it is not a grant of D3, provider, credential, economic, legal, rights, security or other authority.

## Purpose

PentaImmune is CrownThrive's bounded autonomic maintenance layer for authorized repository-local weaknesses. PentaEVIBuilder is its deterministic evidence-construction engine.

Operating loop:

`observe -> hunt -> rank -> work candidate -> PentaFactory/PentaPR repair -> exact-head tests -> PentaEVIBuilder evidence -> independent PentaCertify/PentaAssure -> governed merge -> main readback -> advisory repair memory`

## Hunting perimeter

PentaImmune may inspect CrownThrive-owned or explicitly authorized repository-local signals: failed CI/workflow runs, failed/stale tests, evidence gaps and SHA drift, stale automation, explicitly admitted governed defects, and documentation/registry drift.

It does not scan third-party targets, conduct offensive security activity, run arbitrary issue-supplied commands, or interpret untrusted text as execution authority. The scheduled hunter is read-only; repair mutation stays separated through PentaFactory/PentaPR and repository governance.

## Autonomy and throttles

Default autonomy is A2 with reversible D0-D2 candidates. D3 is human-reserved. Default throttle is one repair per cycle, two attempts per candidate, one-hour cooldown, and an armed kill switch.

Every repair plan emits:

1. **Rollback / throwback** — deterministic reversal, normally Git revert or known-good restoration.
2. **Fallback / redundancy** — fail-closed HOLD plus known-good `main` or another certified route.

Retry caps prevent self-competition from becoming an infinite repair loop.

## PentaEVIBuilder evidence contract

PentaEVIBuilder binds proof to an exact 40-character Git SHA and emits a SHA-256 receipt over canonical JSON. Evidence includes work/source identity, repository/head SHA, observations/claims, test receipts, evidence references, rollback, fallback/redundancy, provenance, autonomy envelope, producer and target state.

Evidence starts `UNVERIFIED`. PentaEVIBuilder cannot certify itself. Certification fails closed on receipt tampering, producer/verifier collision, SHA drift, missing evidence/tests/rollback/fallback, forbidden autonomy flags or ungated D3. A PASS evidence decision still does not itself authorize production promotion; repository/release policy remains authoritative.

## Repair memory

Successful repairs may enter advisory memory with weakness fingerprint, recipe reference, evidence receipt, rollback/fallback and successful head. Memory grants no authority or certification and always requires prerequisite matching plus fresh exact-head retesting. Failed/HOLD repairs cannot be learned as successes.

## Creating new Pentas

PentaImmune may propose a missing subsystem when repeated evidence supports the need. Proposals are always `CANDIDATE`, require external governance, and cannot self-register, self-activate, self-certify or expand authority.

## 24/7 operation

`.github/workflows/penta-immune-assurance.yml` schedules the trusted read-only hunt at minute 17 of every hour and also supports `workflow_dispatch`. PR code gets deterministic tests/evidence only; the tokenized live hunt is suppressed on pull-request execution.

"Always on" never means "always writing." Maintenance, kill switch, governance HOLD, retry caps and exact-head certification remain effective at all times.

## Production evidence

Initial production evidence:

- PR: `#533`
- pre-merge exact head: `1fb79c7130f3a039da82a488bc3e13f6cffde621`
- pre-merge dedicated run: `33021239591` — SUCCESS
- evidence receipt SHA-256: `ecf54d83d5be0d906d48bb859a0500e5d1c2633f2910f37a1d2e24701b778e3e`
- independent certification decision SHA-256: `d62feeaf450bdc04fddc3f5f58ff53ff2dff9c93471beba7f1487b0886b278ea`
- governed merge gate on pre-merge head: SUCCESS
- merge/main SHA: `0ad7aff61027be9913f84852a1286fb6a4f1c429`
- main dedicated run: `33021479616`
- main deterministic assurance: SUCCESS
- main independent exact-head certification: SUCCESS
- main live read-only hunt: SUCCESS

Historical or branch evidence never substitutes for new exact-head evidence after a code change.

## First prey and first repair

The first controlled repair was issue #121. Current code already contained the bounded evidence-data classifier fix and a fresh governed self-test passed, so PentaImmune treated the ticket as stale-open state rather than manufacturing duplicate code. The issue received an evidence closure record and was closed `completed`. Reopening remains the rollback if its acceptance criteria regress.

The live hunter also surfaced failed workflow runs as current prey. A prior governed-merge failure exposed an unlisted generated provider documentation page and duplicate stable contract ID. Those remain repair candidates; the validators are not weakened to make them disappear.

## Invariants

- Never manufacture authority.
- Never self-certify consequential output.
- Never mark HOLD as PASS.
- Never reuse stale evidence as new evidence.
- Never promote a different SHA than the SHA tested and evidenced.
- Never learn a failed repair as a successful recipe.
- Never bypass required GitHub status/security/governance gates.
- Never delete history to make a failure disappear.
