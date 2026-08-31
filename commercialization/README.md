# CrownThrive OS COS V1 Commercialization Fabric

**Component ID:** `ct.cos.commercialization-fabric`  
**Version:** `1.0.0-rc.1`  
**Institutional context:** CrownThrive OS Phase 3 / OS 3.x  
**State:** built candidate; production publication remains evidence-gated

This fabric converts existing CrownThrive component evidence into a deterministic commercial catalog without reclassifying components by prose. It discovers plugins, pallets, modules, packages, engines, APIs/MCP assets, and related manifests; separates certified from withheld records; generates language-neutral install metadata; produces CHLOM license offers; binds paid flows to the CHLOM Wallet control contract; and routes operations through hot, warm, and cold mesh lanes.

## What becomes interoperable

Every eligible package receives a universal Git + OCI + JSON Schema/OpenAPI/MCP contract. Native descriptors are generated for npm, PyPI, Maven, NuGet, crates.io, Go modules, Composer, RubyGems, SwiftPM, Dart/pub.dev, and OCI registries. A language without a native adapter uses the universal contract rather than being excluded.

## Commercial lanes

- **Community Discovery candidate:** free, non-production interface evaluation under `ct.license.cos-community-evaluation.v1`; activation remains HOLD until exact-head independent verification and publication readback.
- **Commercial Request Quote:** active CHLOM intake for field-of-use, term, users/environments, support, data/model rights, branding, and economics.
- **Fixed-price or metered checkout:** generated only when an approved amount, currency, rights gate, economic gate, wallet route, entitlement rule, and exact certification evidence are present.

No price is invented. Eligible products without an approved fixed price become request-quote offers. A free component grant is generated only when the exact source record explicitly authorizes that evaluation scope.

## Certification rule

A lifecycle label, version number, public repository, workflow result, provider response, or documentation statement is insufficient. The catalog admits a package only from explicit PASS evidence or the strict composite release rule in `commercialization/policy.v1.json`. Every withheld record remains visible with machine-readable reasons.

## CHLOM Wallet

The bridge uses the existing `runners/chlom-agent-wallet` identity and Base/native-USDC policy. Free evaluation creates no money movement. Paid intents require an exact quote, accepted license, ECAC authorization, idempotency, source/version binding, provider readback, settlement reconciliation, entitlement issuance, and DAIL evidence. Current unattended value remains zero.

## MCP mesh contract

`commercialization/api/openapi.v1.json` supplies a server-neutral OpenAPI 3.1 contract for generated clients, while `commercialization/mcp/commercialization-tools.v1.json` declares the public-safe tool surface and binds each operation to the configured CrownThrive OS and CHLOM evidence MCP servers. `scripts/commercialization/mesh_router.py` emits deterministic dispatch envelopes only; it never performs a provider call. Hot reads are side-effect-free. Warm and cold actions require explicit authority, DAIL evidence, CHLOM state where applicable, idempotency, and rollback or compensation.

## Commands

```bash
python3 scripts/commercialization/build_catalog.py \
  --repo-root . \
  --output dist/commercialization \
  --source-sha "$GITHUB_SHA" \
  --require-clean-sources

python3 scripts/commercialization/generate_adapters.py \
  --catalog dist/commercialization/catalog.json \
  --output dist/commercialization/registry-adapters

python3 scripts/commercialization/package_release.py \
  --repo-root . \
  --output dist/release \
  --version 1.0.0-rc.1 \
  --source-sha "$GITHUB_SHA" \
  --catalog-dir dist/commercialization \
  --release-notes releases/cos-commercialization-fabric-v1.0.0-rc.1/RELEASE_NOTES.md

python3 -m unittest tests.test_cos_commercialization_fabric
```

The GitHub workflow validates and packages on pull requests and main. Publication is handed to PentaRelease and a protected production environment; no registry or wallet credential is stored in the repository.
