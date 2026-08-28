# PentaRelease™

Status: Implemented software; registry maturity `specified`; production certification `HOLD`
Component ID: `ct.pentarelease`
Version: `2.2.2`
Canonical role: CrownThrive autonomous release intelligence, packaging, publication, repair, reconciliation, and release-evidence subsystem.

## Mission

PentaRelease determines **when a release is warranted, what should be released, why the release exists, which version identifier is justified, what artifacts must be downloadable, whether publication actually completed, and whether already-published releases still satisfy the release contract**. It must operate without requiring the founder, ChatGPT, or another conversational agent to remain present.

## Autonomous operating loop

1. Observe the canonical repository and latest published release.
2. Compare all unreleased changes against the latest tag.
3. Ignore generated release machinery, historical archives, and non-release deltas.
4. Classify the remaining change surface as breaking, feature, fix/hardening, governed evidence/integration, or non-release documentation.
5. Apply the CrownThrive version scheme declared by policy and the current release lineage.
6. HOLD breaking/D3 authority changes for human governance rather than manufacturing authority.
7. For bounded D0-D2 releaseable deltas, generate release notes and a machine-readable manifest explaining the exact `why`, files changed, prior version, selected bump, target, governance constraints, and package policy.
8. Create the governed release request automatically.
9. Hand the request to the PentaRelease publisher, which validates, packages, hashes, publishes, attaches downloadable artifacts, and performs provider readback.
10. Synchronize the comprehensive release surface for the latest published release, promoting repository surface updates only through a gated pull request or recording an explicit HOLD.
11. Reconcile already-published releases against the current artifact contract and repair missing downloadable evidence from the immutable release tag when a valid governed package is present.
12. Treat a release as complete only after GitHub/provider readback confirms the expected tag and required assets.

## Version intelligence

For CrownThrive Extended Institutional Versioning `A.B.C.D`:

- breaking/incompatible authority or architecture: `(A+1).0.0.0` — human reserved by default;
- backward-compatible executable capability: `A.(B+1).0.0`;
- production fix/hardening: `A.B.(C+1).0`;
- bounded evidence, governance, CI/integration, or convergence increment: `A.B.C.(D+1)`.

For three-segment SemVer, ordinary MAJOR.MINOR.PATCH rules apply.

The version number never grants rights, settles money, certifies a provider, changes legal authority, or converts HOLD to PASS.

## Release awareness

PentaRelease runs on every merge/push to `main`, every 15 minutes as a reconciliation watch, and on explicit workflow dispatch. A scheduled run that finds no release-relevant delta records HOLD and exits without creating noise.

Release-worthy signals include executable runtime changes, new integrations/adapters/providers, security fixes, governed production fixes, release-contract changes, and machine-governed version/Phase 3 control-plane changes. Ordinary prose-only or historical documentation updates do not automatically create an OS release.

## Resilient autonomous publication

PentaRelease 2.0.2 hardened the autonomous publisher so a provider identity gap does not stall a governed release.

- Every autonomous release is materialized on a governed exact branch named `pentarelease/auto-<version>-<run-id>` and must pass the CrownThrive governed merge gate on that exact branch before publication.
- The preferred promotion path is a protected-main pull request that PentaRelease creates and merges itself.
- If GitHub Actions cannot create or merge the protected-main pull request, PentaRelease publishes the release from the fully gated exact branch instead. The release request and manifest record that exact branch as the target.
- The publisher builds the governed ZIP and TAR.GZ bundles, `SHA256SUMS`, `MANIFEST.json`, and `RELEASE_NOTES.md`, uploads them to the provider release, and performs provider readback before treating publication as complete.
- The publisher contract for this path is `ct.pentarelease.autonomous.v2.0.2`.

## Release-surface synchronization and idempotent promotion

PentaRelease 2.2.2 governs how the comprehensive release surface (managed repository surfaces, PentaDocs release pages, and provider release assets) is kept synchronized with the latest published release.

- A release-readiness preflight runs before any work. It verifies local readiness (release-surface state matches the latest tag, managed blocks are present, the PentaDocs release tab and pages are intact) and provider readiness (the comprehensive release body block and all eight required release assets exist, including `PENTARELEASE_RELEASE_RECORD.json`, `PENTARELEASE_DATA_CATALOG.json`, and `PENTARELEASE_EVIDENCE.json`).
- If both local and provider state are already current, the run records `ALREADY_SYNCHRONIZED` and exits. Reruns are idempotent and create no duplicate branches, pull requests, or assets.
- If local surfaces are current but provider assets are incomplete, PentaRelease repairs only the provider release assets. No repository promotion occurs.
- Pending repository updates live on one stable PentaRelease-owned branch per release and base commit, named `pentarelease/surface-<tag>-<base-sha>`. Retries reuse that branch instead of creating new ones.
- Before merge, the governed merge gate must pass as a `pull_request` run against the exact head commit of that pull request. A stale or non-passing gate is a HOLD.
- The direct protected-main push fallback is removed. PentaRelease never pushes directly to protected `main`.
- A missing provider identity is recorded as an explicit HOLD instead of a bypass. `HOLD_PR_PROVIDER_IDENTITY` means GitHub Actions cannot create the protected-main pull request; the gated branch is preserved for an authorized PR provider identity. `HOLD_PR_MERGE_IDENTITY` means the pull request is gated and ready but the workflow token cannot perform the protected-main merge.
- `MERGED` is the only promotion success state. HOLD states are never silently rewritten.

## Published-release reconciliation

PentaRelease 2.1 adds a production repair plane for releases that were published before the current artifact contract was fully enforced.

- It audits published governed OS releases rather than assuming publication means completeness.
- It checks for the required ZIP, TAR.GZ, SHA-256 checksum file, manifest, and release notes.
- If assets are missing, it reconstructs only those missing artifacts from the immutable release tag's governed package and uploads them additively.
- It does not rewrite an existing release's narrative, target, tag, or authority merely to repair downloadable evidence.
- Provider readback is performed after repair and the latest release must satisfy the required asset contract.
- Historical backfill is best-effort. If an older release lacks a recoverable governed package, PentaRelease records that state rather than fabricating source material.
- Missing latest-release evidence fails closed until repaired and verified.

## Download contract

When a release is published, the governed publisher is responsible for the release notes, manifest, ZIP package, TAR.GZ package, SHA-256 checksums, GitHub source archives, and provider readback unless the release manifest narrows that artifact policy.

Secret-bearing files, credentials, vault content, private keys, `.env` material, and anything classified `no_release` are blocked from autonomous packaging.

## Safety and governance

PentaRelease may recognize and package authority already established elsewhere. It may never manufacture new authority. D3/breaking decisions remain human-reserved unless a later governing contract explicitly grants narrower authority. Self-approval of restricted gates is prohibited. Historical releases remain preserved.

## Current implementation

The files below are executable implementation signals. They do not by themselves prove an exact-head production deployment or promote the `penta.release` family member. The current Penta OS V1 release gate remains HOLD until exact-head governed CI, packaging, publication, provider readback, and the wider release blockers are resolved.

- Policy: `.pentarelease/policy.json`
- Activation state: `.pentarelease/state/activation.json`
- Decision engine: `scripts/pentarelease/decide.py`
- Published-release reconciler: `scripts/pentarelease/reconcile.py`
- Release-surface engine: `scripts/pentarelease/release_surface.py`
- Autonomous observer: `.github/workflows/pentarelease-autonomous-awareness.yml`
- Comprehensive release surface: `.github/workflows/pentarelease-comprehensive-release-surface.yml`
- Published-release repair workflow: `.github/workflows/pentarelease-published-release-reconciler.yml`
- Workflow contract tests: `tests/test_pentarelease_workflow_contract.py`, `tests/test_pentarelease_release_surface.py`
- Publisher: `.github/workflows/crownthrive-os-v2-release.yml`
- Release requests: `.github/release-requests/`
- Release packages: `releases/`
