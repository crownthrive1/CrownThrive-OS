# PentaRelease™

Status: Production
Component ID: `ct.pentarelease`
Version: `2.0.0`
Canonical role: CrownThrive autonomous release intelligence, packaging, publication, and release-evidence subsystem.

## Mission

PentaRelease determines **when a release is warranted, what should be released, why the release exists, which version identifier is justified, what artifacts must be downloadable, and whether publication actually completed**. It must operate without requiring the founder, ChatGPT, or another conversational agent to remain present.

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
10. Treat the release as complete only after GitHub/provider readback confirms the expected tag and assets.

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

## Download contract

When a release is published, the governed publisher is responsible for the release notes, manifest, ZIP package, TAR.GZ package, SHA-256 checksums, GitHub source archives, and provider readback unless the release manifest narrows that artifact policy.

Secret-bearing files, credentials, vault content, private keys, `.env` material, and anything classified `no_release` are blocked from autonomous packaging.

## Safety and governance

PentaRelease may recognize and package authority already established elsewhere. It may never manufacture new authority. D3/breaking decisions remain human-reserved unless a later governing contract explicitly grants narrower authority. Self-approval of restricted gates is prohibited. Historical releases remain preserved.

## Production implementation

- Policy: `.pentarelease/policy.json`
- Decision engine: `scripts/pentarelease/decide.py`
- Autonomous observer: `.github/workflows/pentarelease-autonomous-awareness.yml`
- Publisher: `.github/workflows/crownthrive-os-v2-release.yml`
- Release requests: `.github/release-requests/`
- Release packages: `releases/`
