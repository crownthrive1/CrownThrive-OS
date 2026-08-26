# CrownThrive Institutional Versioning Policy

Status: Active
Policy version: 1.0.0
Effective: 2026-08-25

## Purpose

Every production-capable CrownThrive software system, governed contract, protocol, API/MCP surface, schema, release package, documentation corpus, deployment adapter, and institutional framework must carry an explicit version. Silent replacement is prohibited.

## Version model

CrownThrive uses Semantic Versioning for production software and institutional artifacts: MAJOR.MINOR.PATCH.

- MAJOR: incompatible architecture, authority model, contract, or public behavior change.
- MINOR: backward-compatible capability, subsystem, automation, integration, governance, or operational expansion.
- PATCH: backward-compatible correction, hardening, evidence, documentation, observability, or defect fix.

Pre-production artifacts may use prerelease suffixes such as -alpha, -beta, -rc.N, -controlled-test, or -canary.

## Required version identity

Each governed component must register: component_id, canonical_name, component_type, version, lifecycle_state, compatibility_line, exact source/deployment reference when known, evidence reference, supersedes version when applicable, and release timestamp.

## Preservation rule

A newer version does not erase an older version. Historical releases remain attributable and immutable as evidence. Deprecation must be explicit. Replacement requires compatibility and migration evidence.

## Production truth

A version may be marked released only when the applicable release mechanism confirms publication or deployment. A component without independently verified production evidence must not be labeled production merely because a version number exists.

## Governance

CHLOM preserves authority and rights boundaries. ThriveBase preserves runtime/version state. DAIL preserves execution and evidence lineage. GitHub preserves source and release history. Documentation surfaces may project the registry but do not independently manufacture release authority.

## Release families

The CrownThrive OS release line is the institutional umbrella version. Subsystems retain independent versions and do not automatically inherit the OS number unless their own package is changed and registered.

## Current umbrella lineage

- v1.0.0 — CrownThrive OS V1 Foundation Release.
- v2.0.1 — Founder Visibility & Autonomous Briefing.
- v2.1.0 — Institutional Version Registry & Release Governance.

## Automation requirement

Release publication must be machine-readable, auditable, idempotent, and capable of readback. Release requests must name the exact tag, target, title, package, and lifecycle state. The release publisher validates the requested package before creating or editing a GitHub Release.
