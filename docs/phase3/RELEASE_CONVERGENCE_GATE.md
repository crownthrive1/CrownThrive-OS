# Phase 3 Release Convergence Gate

**Effective:** 2026-08-27

**Record ID:** `ct.release.convergence.phase3.v1`

**Institutional phase:** Phase 3 — Execute

**Decision:** `HOLD` for the intended human-authorized major release

**Machine record:** [`../versioning/RELEASE_RECONCILIATION_MANIFEST.v1.json`](../versioning/RELEASE_RECONCILIATION_MANIFEST.v1.json)

## Outcome

The canonical published baseline is now CrownThrive OS `v3.13.0.1`. The generated `v3.14.0.0` branch is not a published release. The intended major release remains a governed intent only: no target version, tag, or head is assigned, and no provider write is authorized by this record.

This reconciliation retains **Phase 3 — Execute**. A release-number change cannot independently advance the institutional phase or certify any component.

## Current release state

| Subject | Current state | Exact evidence | Effect |
| --- | --- | --- | --- |
| `v3.13.0.1` | `RELEASED` / provider readback `PASS` | Published `2026-08-26T23:46:15Z`; five assets; local tag commit `3b5ab399cc4a3014554f95736fcea7032972989a` | Canonical published baseline |
| `v3.14.0.0` | `CANDIDATE_HOLD` / `FAILED_NO_PROVIDER_RELEASE_READBACK` | Branch `pentarelease/auto-3.14.0.0-33024509722`; commit `ede88f08c3c93eac12adec306811573bfff27a19`; no tag or Releases API record observed | Does not supersede `v3.13.0.1`; tag/version reuse prohibited without disposition |
| Institutional phase | `ACTIVE` | [`../phase-model/PENTA_PHASE_MODEL.md`](../phase-model/PENTA_PHASE_MODEL.md) | Remains Phase 3; no phase transition |
| Intended major release | `HOLD` | Human intent is present, but no exact D3 receipt, target tag, or target head exists | Provider publication prohibited |

An authenticated provider readback at `2026-08-27T00:33:44Z` proves the published release, publication time, and all five exact asset names, sizes, and provider-computed SHA-256 digests for `v3.13.0.1`. Those values are pinned in the machine reconciliation record. Provider metadata is not a substitute for independently downloading and hashing the bytes; the future major release still requires both provider metadata readback and independent byte-parity verification.

## Major-version namespace collision

PentaRelease currently computes a four-part major bump by incrementing the first segment and zeroing the remaining segments. Applied to `3.13.0.1`, the provisional result is `4.0.0.0` / `v4.0.0.0`.

The current phase canon simultaneously says Phase 3 uses the OS `3.x` release family. Phase and release are independent namespaces, but the current records must still agree. Therefore the exact target remains unassigned until an authorized D3 decision does one of the following without advancing the phase:

1. explicitly adopts a `4.x` OS release family while retaining Phase 3 and updates every canonical phase/release projection; or
2. records another policy-compliant major-release disposition and explains its compatibility semantics.

An agent, workflow, version calculation, quorum, or generated branch may not make that reserved decision.

## Required predicates before provider write

Every predicate below must be `PASS` at the same exact target head. `HOLD` and `UNKNOWN` fail closed.

| Gate | Predicate | Current state |
| --- | --- | --- |
| `CT-MAJOR-001` | Provider-published baseline reconciled | `PASS` |
| `CT-MAJOR-002` | Institutional phase remains Phase 3 | `PASS` |
| `CT-MAJOR-003` | Immutable disposition for the `v3.14.0.0` candidate | `HOLD` |
| `CT-MAJOR-004` | Exact D3 authority names class, version, tag, head, and compatibility effect | `HOLD` |
| `CT-MAJOR-005` | Phase / OS release-family namespace reconciled | `HOLD` |
| `CT-MAJOR-006` | Canonical target head frozen, clean, and free of unresolved concurrent delta | `UNKNOWN` |
| `CT-MAJOR-007` | Governed merge and required check context pass at the exact head | `UNKNOWN` |
| `CT-MAJOR-008` | Applicable tests, docs, JSON, security, restricted-data, and secret scans pass | `UNKNOWN` |
| `CT-MAJOR-009` | Existing holds are resolved or explicitly inherited without promotion | `HOLD` |
| `CT-MAJOR-010` | Notes, manifest, packages, checksums, digests, and rollback target exist | `UNKNOWN` |
| `CT-MAJOR-011` | Registry and every managed public release projection agree | `HOLD` |
| `CT-MAJOR-012` | Provider permission, PR, check, merge, release, and retry topology is freshly verified | `UNKNOWN` |
| `CT-MAJOR-013` | Rollback, correction, and supersession paths are bound | `UNKNOWN` |

## Predicates after provider write

A successful write is not release completion. Before `RELEASED` may be recorded, independent readback must prove:

- the authorized provider release exists at the exact tag and target;
- draft and prerelease flags match the authority record;
- every required asset name, size, and digest matches the release manifest;
- the provider release is readable through the canonical API after the write; and
- the version registry, Phase 3 current state, archive lineage, README, PentaDocs release surfaces, and PentaRelease managed state have been reconciled from that readback.

Any missing or negative readback is `FAILED` / `HOLD`; no `PASS` is issued.

## Holds that survive release numbering

The major release may carry unresolved work only when each item is explicitly named with its unchanged prohibited action, owner, evidence need, and next review. In particular, it may not blanket-promote:

- unresolved contradiction and current-state validation queues;
- legal, rights, licensing, finance, tax, payment, settlement, or entitlement state;
- provider-wide write authority from a bounded provider operation;
- repository-family transport verification into authenticated runtime certification;
- Penta family membership or active identity into per-member production maturity;
- DAIL v2 controlled-test source into runtime/native-anchor production; or
- Phase 4 preparation or replicated gates into Phase 4 activation.

Primary inherited-state pointers are [`../../knowledge/contradiction-ledger.mdx`](../../knowledge/contradiction-ledger.mdx), [`../../knowledge/current-state-validation-queue.mdx`](../../knowledge/current-state-validation-queue.mdx), and [`../../support/legal-status-and-historical-claim-supersession.mdx`](../../support/legal-status-and-historical-claim-supersession.mdx).

## Stop condition

**STOP — do not publish the intended major release while any prepublication predicate is not `PASS`.** The latest released baseline remains `v3.13.0.1`; `v3.14.0.0` remains an unpublished candidate on hold; CrownThrive remains in Phase 3.
