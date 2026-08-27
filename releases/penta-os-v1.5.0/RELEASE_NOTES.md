# Penta OS V1.5.0

Status: **implemented; build candidate; release HOLD**

Penta OS V1.5.0 is the backward-compatible V1 control-plane expansion for the reconciled Penta registry. It adds dependency-closed validation, deterministic verification receipts, deterministic cohort-preserving batch planning that emits all-or-none planning HOLDs without claiming atomic execution, and a reproducible, self-verifying public-safe distribution.

## Distribution

The governed build produces:

- `penta-os-v1-1.5.0.zip`
- `penta-os-v1-1.5.0.tar.gz`
- `penta-os-v1-1.5.0.sha256`
- `penta-os-v1-1.5.0.build.json`
- `penta-os-v1-1.5.0.verification.json` as a separate CI verification record

The ZIP and TAR.GZ contain an identical canonical source closure, `MANIFEST.json`, and `SBOM.spdx.json`. The SBOM uses SPDX 2.3 and `LicenseRef-CrownThrive-All-Rights-Reserved`; repository or package visibility grants no general license.

Both extracted archives must regenerate/check the registry, validate the runtime, and pass the complete focused component test suite against all four V1.5 schemas. The declared operation-policy registry and schema assets are package-closure requirements. Repository-wide documentation governance remains a pre-package repository gate; it is not claimed as a self-contained archive replay.

## Release gates

These notes do not assert publication. Release remains held until:

- the exact source is merged through the governed default-branch gate;
- exact-head CI and an independent verifier pass against the same digest;
- the `penta-os-v1.5.0` provider release targets that exact commit;
- every expected provider asset is downloaded and its byte size and SHA-256 match the build receipt; and
- deployment claims, if any, are supported by exact deployment-to-source readback.

No child Penta maturity, provider authority, D3 approval, institutional phase, commerce state, or ecosystem-wide production state changes because this package builds or publishes.
