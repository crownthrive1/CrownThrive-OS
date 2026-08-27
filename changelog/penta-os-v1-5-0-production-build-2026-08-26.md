# Penta OS V1.5.0 production-build candidate

Date: 2026-08-26
Component: `ct.penta.os-v1`
Version: `1.5.0`
Compatibility line: `1.x`
Supersedes: `1.0.0`
State: `built_unreleased`
Certification: `HOLD`

## Change summary

Penta OS V1.5.0 establishes the versioned V1.5 registry and control-kernel line with dependency-closed registry verification, deterministic verification receipts, deterministic cohort-preserving batch planning that emits all-or-none planning HOLDs without claiming atomic execution, and reproducible public-safe source distributions. Stable component IDs, registry IDs, file paths, documentation routes, and the `1.x` compatibility line are preserved from this governed release forward.

The V1.5 package builder resolves its payload from the exact registry source-digest closure, the Penta Family catalog index and catalogs, and the governed software-asset manifest. It rejects unsafe, missing, escaping, or symbolic-link inputs. ZIP and TAR.GZ distributions contain the same canonical regular-file payload and carry SHA-256 file records, an SPDX 2.3 SBOM, an all-rights-reserved extracted LicenseRef, and an SPDX package verification code.

## Build-verification contract

The exact-head workflow must:

1. validate generated registry and documentation state;
2. compile and run the focused Penta OS tests;
3. build the distribution twice from the same exact commit;
4. prove the two builds are byte-identical;
5. verify the checksum file and build-result bindings;
6. reject unsafe or non-regular archive members;
7. prove ZIP/TAR content equivalence;
8. compare the archive with the exact current source closure; and
9. safely materialize each archive and run the packaged runtime validator.

Each safely materialized archive must also pass the deterministic registry generation check and the complete focused Penta OS test suite, including the registry, plan, batch-plan, and verification-receipt schemas. Declared software assets must be present in the payload; the operation-policy registry is a declared component asset.

The deterministic archives do not embed workflow timestamps or provider observations. Exact-head CI, independent-verifier, provider-release, and deployment-readback receipts remain separate evidence bound to the archive hashes.

Repository-wide documentation governance runs before packaging from the complete repository. `scripts/validate_docs.py` and its repository-wide dependency corpus are not represented as a self-contained distributable replay surface.

## Authority and release boundary

This version does not promote any child Penta, grant provider or D3 authority, advance the institutional phase, or certify the wider ecosystem. The correct public state is **implemented; build candidate; release HOLD**.

Release requires a protected-default-branch exact-head merge, successful CI at that head, a separate independent-verifier receipt, publication under the non-umbrella tag `penta-os-v1.5.0`, and provider readback of the exact target commit and every downloadable asset's size and SHA-256. Command Center production language additionally requires exact deployment-to-source readback.

## Rollback and preservation

Version `1.0.0` remains attributable only as prior built-unreleased metadata lineage; this repository does not assert an independently preserved exact V1.0 source revision or registry digest. V1.5 rollback therefore means reverting the exact V1.5 change to its immediate known parent and re-running current-head gates, not reconstructing an unproven V1.0 artifact. No V1.5 receipt may be reused to certify a different source or artifact digest.
