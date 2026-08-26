# PentaImmune System + PentaEVIBuilder

## Status

**Candidate implementation.** Production/active status is not claimed until the exact governed head is tested, independently certified, merged through repository policy, and verified on `main`.

## Purpose

PentaImmune is CrownThrive's bounded autonomic maintenance layer for authorized repository-local weaknesses. PentaEVIBuilder is its deterministic evidence-construction engine. Together they close the loop from observed weakness to repair evidence without allowing the repair system to manufacture authority, certification, or production state.

The operating loop is:

`observe -> hunt -> rank -> work candidate -> PentaFactory repair -> exact-head tests -> PentaEVIBuilder evidence -> independent PentaCertify/PentaAssure -> governed PentaPR merge -> readback -> advisory repair memory`

## Hunting perimeter

PentaImmune may hunt only CrownThrive-owned or explicitly authorized repository-local signals:

- failed CI/workflow runs;
- failed or stale tests;
- evidence gaps and SHA drift;
- stale automation;
- known governed defects explicitly admitted to the repair queue;
- documentation and registry drift.

It does **not** scan third-party targets, conduct offensive security activity, run arbitrary issue-supplied commands, or interpret untrusted text as execution authority.

The scheduled hunter is intentionally read-only. It ranks live failed workflow runs and issues explicitly labeled `penta-immune-ready`. Repair execution remains a separate PentaFactory/PentaPR action under the existing authority contract.

## Autonomy and throttles

Default autonomy is bounded to D0-D2/A2 reversible work. D3 remains human-reserved. The default throttle is one repair per cycle, two attempts per candidate, and a one-hour cooldown. A kill switch can move the loop to HOLD immediately.

Every repair plan must emit both:

1. **Rollback / throwback** — a deterministic way to reverse the candidate repair, normally a Git revert or known-good restoration.
2. **Fallback / redundancy** — the operational alternative used if the repair cannot be certified, normally fail-closed HOLD plus known-good `main` or another certified path.

The retry cap prevents self-competition from becoming an infinite repair loop.

## PentaEVIBuilder evidence contract

PentaEVIBuilder binds proof to an exact 40-character Git head SHA and emits a SHA-256 receipt over a canonical JSON payload. The evidence bundle records:

- work-order and source identity;
- repository and exact head SHA;
- observations and scoped claims;
- test receipts and evidence references;
- rollback and fallback/redundancy;
- provenance and autonomy envelope;
- producer identity;
- target state.

Evidence is emitted as `UNVERIFIED`. PentaEVIBuilder may not certify its own bundle. The certification gate fails closed on producer/verifier identity collision, evidence digest tampering, SHA drift, missing evidence, failed tests, missing rollback/fallback, forbidden autonomy flags, or an ungated D3 decision.

A PASS certification still does not itself authorize production promotion; governed merge/release policy remains authoritative.

## Repair memory

Successful repair memory stores a weakness fingerprint, recipe references, evidence receipt, rollback/fallback, and successful head. Memory is **advisory only**. It grants no authority and no certification, and every reuse requires prerequisite matching plus fresh tests on the new exact head.

Failed or held repairs cannot be learned as successful recipes.

## Creating new Pentas

PentaImmune may generate a subsystem proposal when repeated evidence indicates a missing capability. Such output is always `CANDIDATE`, requires external governance, and cannot self-register, self-activate, self-certify, or expand its own authority.

## 24/7 operation

`.github/workflows/penta-immune-assurance.yml` is designed to run an hourly read-only hunt from trusted repository code after merge. Pull requests run only deterministic code/test/evidence assurance; the live GitHub hunt is suppressed for pull-request code so an untrusted PR cannot receive a repository token through the hunter.

The loop may be disabled for maintenance or by kill switch. "Always on" never means "always writing."

## Evidence and certification

The dedicated workflow has separate jobs for:

1. deterministic compile/unit assurance;
2. PentaEVIBuilder exact-head evidence construction;
3. independent PentaCertify-style evidence verification on a separate job/runner;
4. live read-only hunting on trusted non-PR execution.

Production evidence must come from observed GitHub results for the exact head. Local test results and historical evidence are useful development input but are not production certification.

## First-hunt behavior

The first connected hunt found two classes of signal:

- issue #121's evidence-data classifier is already implemented by the current v2 classifier and has a passing self-test, so PentaImmune must not invent a duplicate code patch merely because the issue is still open;
- a fresh governed-merge failure exposed an unlisted generated provider documentation page and a duplicate stable contract ID during the Phase-3 baseline audit. Those are live repair candidates because they are objective validator failures; the validators themselves must not be weakened to make them disappear.

This distinction is intentional: PentaImmune is expected to compete on correctness, not on the number of changes it can manufacture.

## Invariants

- Never manufacture authority.
- Never self-certify consequential output.
- Never mark HOLD as PASS.
- Never reuse stale evidence as new evidence.
- Never promote a different SHA than the SHA tested and evidenced.
- Never learn a failed repair as a successful recipe.
- Never bypass required GitHub review, status checks, specialist gates, or human-reserved D3 controls.
- Never delete history to make a failure disappear.
