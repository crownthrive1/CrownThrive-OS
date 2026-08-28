# PentaRelease™

Status: active-design baseline; the production autonomous engine is documented in [PENTARELEASE.md](../PENTARELEASE.md)
Version: 1.0.0 (baseline contract); current engine `2.2.2`
Owner: CrownThrive OS

PentaRelease is CrownThrive's governed release-engine subsystem. Its job is to turn an approved, version-addressable change set into a reproducible package, validate that package, publish the provider release, attach downloadable artifacts, verify provider readback, record evidence, and preserve prior versions without silently mutating unrelated systems.

## Mission

PentaRelease owns the release lifecycle, not product authority. It may package and publish only what an existing release request and source state authorize. It never manufactures PASS, rights, legal authority, entitlement authority, money-movement authority, deployment truth, or production certification.

## Required release inputs

Every release request MUST identify:

- release_id
- canonical product/system name
- exact version and tag
- exact source target/ref
- release title
- package directory
- release notes path
- manifest path
- lifecycle intent: release, prerelease, draft, or hold
- package mode
- artifact/download policy
- compatibility/supersession metadata when applicable
- evidence/readback requirement

If any required field is missing, PentaRelease fails closed.

## Download/package contract

When the user asks to "release", "package", "publish", "make downloadable", or equivalent, PentaRelease must determine the required downloadable set from the release manifest. By default it creates:

1. a ZIP bundle of the release package;
2. a TAR.GZ bundle of the release package;
3. SHA256SUMS for generated artifacts;
4. MANIFEST.json;
5. RELEASE_NOTES.md.

GitHub's provider-generated source ZIP/TAR remain supplementary source archives. They do not replace the governed PentaRelease package bundle.

A release manifest can explicitly add or exclude distributable files. Secrets, credentials, private keys, vault material, runtime-only tokens, regulated records, restricted source, and files classified `no_release` MUST never be attached.

## Dynamic behavior

PentaRelease is request-driven. The release workflow must not be hard-coded to one version. Any request matching `.github/release-requests/crownthrive-os-*.json` is resolved dynamically. The package path, tag, target ref, title, draft/prerelease state, artifact policy, and package contents are read from machine-readable request/manifest state.

Future CrownThrive product families may bind to PentaRelease by adopting the same request/manifest contract and a dedicated allowed path pattern.

## Release state machine

requested -> validated -> packaged -> published -> provider_readback_verified -> evidence_recorded

Failure states:

hold_missing_input
hold_validation_failed
hold_packaging_failed
hold_publish_failed
hold_readback_failed

The v2.2.2 release-surface promotion path adds two provider-identity HOLD states: `HOLD_PR_PROVIDER_IDENTITY` (GitHub Actions cannot create the protected-main PR) and `HOLD_PR_MERGE_IDENTITY` (the PR is gated but the workflow token cannot merge it). PentaRelease never pushes directly to protected `main`; a missing provider identity is held, not bypassed.

No failure or HOLD state may be silently rewritten to published.

## Version handling

PentaRelease preserves the product's governing version namespace. Strict SemVer products remain MAJOR.MINOR.PATCH. CrownThrive institutional extended release identifiers such as 3.1.1.9 are accepted only when the applicable release manifest explicitly declares `version_scheme: crownthrive_extended`.

Subsystems retain independent versions. Releasing the OS umbrella does not automatically version-bump every subsystem.

## Provider readback

A release is not treated as provider-published until readback confirms at minimum:

- expected tag;
- expected title;
- expected target ref;
- draft/prerelease flags;
- release URL.

When downloadable assets are required, readback must also confirm the expected asset names exist on the release.

## Authority boundaries

PentaRelease may:

- validate release requests and manifests;
- build deterministic distributable bundles;
- compute checksums;
- create/edit an authorized GitHub Release;
- upload authorized release assets;
- verify provider readback;
- preserve version lineage and release evidence.

PentaRelease may not:

- invent a release version;
- promote a HOLD without authority;
- expose secrets or restricted files;
- change unrelated runtime state merely because a release is published;
- mark a subsystem production without independent production evidence;
- alter legal, commercial, rights, tax, pricing, entitlement, settlement, or governance authority by version number alone.

## Default operating instruction

For every future CrownThrive release request:

1. identify exactly what changed;
2. select the smallest valid version transition under that product's version scheme;
3. create/update the package manifest and release notes;
4. enumerate what must be downloadable;
5. scan the package for prohibited/restricted material;
6. build deterministic ZIP and TAR.GZ bundles;
7. compute SHA-256 digests;
8. publish through the configured provider workflow;
9. verify release and asset readback;
10. preserve release lineage and report only the exact surfaces changed.

This contract is the standing PentaRelease operating baseline.