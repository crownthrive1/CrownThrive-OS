# CrownThrive OS V2.1.0 — Institutional Version Registry & Release Governance

Release date: 2026-08-25 / 2026-08-26 UTC

## Summary

CrownThrive OS V2.1.0 institutionalizes version identity across the CrownThrive operating architecture. This release adds a permanent semantic-versioning policy, machine-readable version registry, historical release lineage, and a generalized governed GitHub release-publishing contract while preserving the production runtime and governance boundaries established in V2.0.1.

## Added

- CrownThrive Institutional Versioning Policy v1.0.0.
- Machine-readable VERSION_REGISTRY.json with umbrella and subsystem identities.
- Historical release lineage for v1.0.0, v2.0.1, and v2.1.0.
- Explicit rule that newer versions do not silently erase or replace prior versions.
- Independent subsystem versioning: OS umbrella versions do not automatically rewrite component versions.
- Required lifecycle state, compatibility line, exact source/deployment reference when known, and evidence lineage.
- Generalized release request contract for future CrownThrive OS releases.
- ThriveBase institutional version registry and release history as runtime source-of-truth state.
- Version promotion/readback requirements so a release is not considered published until provider readback confirms it.

## Compatibility

This is a backward-compatible minor release on the CrownThrive OS 2.x line. The existing V2 runtime, founder briefing system, scheduler topology, DAIL evidence, Mailgun notifications, CHLOM governance boundaries, and fail-closed execution posture remain intact.

## Governance boundaries

- D3/new-authority work remains human-reserved.
- HOLD is not converted to PASS by version promotion.
- A version number does not itself prove production deployment.
- A component is marked released only after the applicable release/deployment mechanism and readback succeed.
- Historical versions remain preserved as institutional evidence.

## Version lineage

- v1.0.0 — Foundation Release.
- v2.0.1 — Founder Visibility & Autonomous Briefing.
- v2.1.0 — Institutional Version Registry & Release Governance.

## Institutional result

CrownThrive now has an explicit, durable version-governance layer spanning GitHub source/releases and ThriveBase runtime state. Future OS and subsystem changes must be version-attributable rather than silently mutating production truth.
