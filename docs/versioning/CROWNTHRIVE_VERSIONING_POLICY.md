# CrownThrive Institutional Versioning Policy

Status: Active
Policy version: 1.1.0
Effective: 2026-08-26

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

## Automation requirement

Release publication must be machine-readable, auditable, idempotent, dynamically parameterized, downloadable when the artifact policy requires it, and capable of provider readback. Release requests must name the exact tag, target, title, package, lifecycle intent, version scheme, and artifact policy. The PentaRelease publisher validates the requested package before creating or editing a GitHub Release.
