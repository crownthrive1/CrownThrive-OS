# CrownThrive Institutional Versioning Policy

Status: Active
Policy version: 1.2.0
Effective: 2026-08-27

## Purpose

Every production-capable CrownThrive software system, governed contract, protocol, API/MCP surface, schema, release package, documentation corpus, deployment adapter, and institutional framework must carry an explicit version. Silent replacement is prohibited.

## Version model

CrownThrive supports two governed version schemes.

### 1. Semantic Versioning

Production software and institutional artifacts SHOULD use MAJOR.MINOR.PATCH when conventional SemVer accurately represents the release family.

- MAJOR: incompatible architecture, authority model, contract, or public behavior change.
- MINOR: backward-compatible capability, subsystem, automation, integration, governance, or operational expansion.
- PATCH: backward-compatible correction, hardening, evidence, documentation, observability, or defect fix.

Pre-production artifacts may use prerelease suffixes such as `-alpha`, `-beta`, `-rc.N`, `-controlled-test`, or `-canary`.

### 2. CrownThrive Extended Institutional Versioning

CrownThrive umbrella/institutional releases MAY use an explicitly declared extended identifier such as `3.1.1.9` when the release package defines the meaning of each segment and the manifest sets `version_scheme: crownthrive_extended`.

An extended institutional identifier is not represented as strict three-segment SemVer. It may never be inferred silently. PentaRelease must reject an extended version if its release request/manifest does not explicitly declare the scheme.

## Required version identity

Each governed component must register: component_id, canonical_name, component_type, version, version_scheme, lifecycle_state, compatibility_line, exact source/deployment reference when known, evidence reference, supersedes version when applicable, and release timestamp.

## Preservation rule

A newer version does not erase an older version. Historical releases remain attributable and immutable as evidence. Deprecation must be explicit. Replacement requires compatibility and migration evidence.

## Production truth

A version may be marked released only when the applicable release mechanism confirms publication or deployment. A component without independently verified production evidence must not be labeled production merely because a version number exists.

## Governance

CHLOM preserves authority and rights boundaries. ThriveBase preserves runtime/version state. DAIL preserves execution and evidence lineage. GitHub preserves source and release history. Documentation surfaces may project the registry but do not independently manufacture release authority.

## PentaRelease

PentaRelease is CrownThrive's canonical governed release-engine subsystem.

PentaRelease is responsible for:

- validating machine-readable release requests and manifests;
- enforcing the applicable version scheme;
- building governed downloadable release bundles;
- computing checksums;
- publishing or updating an authorized provider release;
- attaching authorized release assets;
- independently reading back provider state and expected assets;
- preserving release lineage and evidence.

PentaRelease does not manufacture product authority, certification, legal authority, rights, pricing, entitlement, settlement, money movement, or deployment truth.

## Release families

The CrownThrive OS release line is the institutional umbrella version. Subsystems retain independent versions and do not automatically inherit the OS number unless their own package is changed and registered.

## Current umbrella lineage

- v1.0.0 — CrownThrive OS V1 Foundation Release.
- v2.0.1 — Founder Visibility & Autonomous Briefing.
- v2.1.0 — Institutional Version Registry & Release Governance.
- v3.1.1.9 — Autonomous Institutional Runtime Consolidation.
- v3.13.0.1 — Autonomous PentaRelease; provider publication verified at `2026-08-26T23:46:15Z` with five assets.

This compact lineage is not a claim that no intermediate immutable provider releases exist. Provider history remains preserved and may be imported into the registry only from exact provider readback or an equivalent immutable evidence record.

## Provider and candidate reconciliation

A generated branch, package, request, manifest, version calculation, workflow success, or local tag does not by itself establish a published release. The current released baseline is the latest authorized provider release that has been independently read back. A one-ahead generated candidate remains `CANDIDATE` / `HOLD` when its tag or release is absent from provider readback, and it may not supersede the published baseline.

Failed or incomplete candidates are never silently reused. Before their version or tag can be reused, an exact disposition must identify the candidate branch and commit, state whether it is abandoned, superseded, corrected, or intentionally resumed, and bind the decision to the new release head.

The current evidence reconciliation is machine-readable at `docs/versioning/RELEASE_RECONCILIATION_MANIFEST.v1.json`.

## Human-authorized major release gate

A major release is a reserved compatibility decision, not a number selected merely because a release was requested. PentaRelease's current four-part bump rule would provisionally advance `3.13.0.1` to `4.0.0.0`, but no target tag is assigned until all of the following are true:

- an exact D3 human-authority receipt names the release class, version, tag, target head, and compatibility effect;
- the current phase and OS release-family records are reconciled without inferring a phase transition from the version number;
- every earlier one-ahead candidate has an explicit immutable disposition;
- the exact target head passes governed merge, documentation, test, security, secret, packaging, checksum, and rollback predicates;
- inherited `HOLD`, `UNKNOWN`, `CONTROLLED_TEST`, legal, rights, financial, provider, and component states are resolved or explicitly carried forward without promotion; and
- provider publication and required assets are read back after the write before the release is marked complete.

A major OS version does not itself advance CrownThrive from Phase 3. A phase transition requires its own separately authorized canonical record.

## Automation requirement

Release publication must be machine-readable, auditable, idempotent, dynamically parameterized, downloadable when the artifact policy requires it, and capable of provider readback. Release requests must name the exact tag, target, title, package, lifecycle intent, version scheme, and artifact policy. The PentaRelease publisher validates the requested package before creating or editing a GitHub Release.
