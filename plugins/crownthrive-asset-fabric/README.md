# CrownThrive Asset Fabric Control Plugin

**Plugin ID:** `ct.plugin.crownthrive-asset-fabric`  
**Version:** `0.1.0`  
**State:** controlled test / governed HOLD  
**Candidate package records:** **5,760**  
**Authoritative source-asset count delta:** **0**

This plugin is the public-safe control surface for CrownThrive's Plugin–Pallet–Kernel Asset Fabric. It extends the existing 100,800-asset Proprietary Asset Factory with deterministic package projections for plugins, pallet bundles, kernels, executable profiles, scripts, skills, prompts, MCP packs, API adapters, event handlers, schema contracts, and test suites.

The generator materializes all 5,760 candidate records deterministically. They are not silently counted as 5,760 new independent source-IP claims.

## Control agents

`ThriveAssetGovernor` is the primary controller. It inventories, assigns, versions, deduplicates, routes, packages, and monitors assets.

`ThriveAssetScrutinizer` is a different independent verifier. The Governor cannot approve its own work.

Additional bounded agents handle custody, kernel/executable construction, contracts, plugin packaging, and release drift.

## Tool surface

The controlled-test surface contains 20 tools covering status, search, exact retrieval, pallet/kernel/plugin/executable/script listing, dependency graphs, generation/materialization/package plans, verification, scrutiny, custody, gap scans, lifecycle/supersession/commercialization plans, and receipts.

Planning tools do not materialize assets or perform provider writes. Verification and scrutiny write only institutional evidence receipts through the restricted runtime.

## Hard boundaries

- no D3 automation;
- no sovereign-vote effect;
- no direct-main merge;
- no raw secret or private-identity export;
- no public protected implementation;
- no provider-write inheritance;
- no checkout or entitlement activation;
- no silent deletion;
- rights, security, tests, custody, runtime, and independent verification remain mandatory.

## Local commands

```bash
bin/thrive-assets status
bin/thrive-assets search rights
bin/thrive-assets get ct.assetfabric.p03.rights-registry.plugin.internal-controlled.v1
bin/thrive-assets dependencies ct.assetfabric.p03.rights-registry.plugin.internal-controlled.v1
bin/thrive-assets validate
bin/thrive-assets scrutinize
```

Windows launchers are included as `bin/thrive-assets.cmd` and `bin/thrive-assets.ps1`.

## Reproducibility

The repository stores the source matrix and per-pallet digest receipt. `bin/thrive-assets generate` materializes the full catalog under `build/asset-fabric`, and validation compares every generated shard with the committed receipt.
