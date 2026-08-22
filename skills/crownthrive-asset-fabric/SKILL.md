# CrownThrive Asset Fabric Control Skill

## Purpose

Use this skill to inventory, generate, search, validate, scrutinize, package, version, custody, and route CrownThrive asset candidates across plugins, pallets, kernels, executables, scripts, skills, prompts, MCP packs, APIs, events, schemas, and tests.

## Required operating sequence

1. Read the current source matrix, catalog receipt, predecessor state, and exact target version.
2. Resolve the stable asset ID, pallet, capability, type, deployment profile, and classification.
3. Detect duplicates, near-duplicates, predecessor/successor records, and conflicting ownership.
4. Resolve dependencies and reverse dependencies.
5. Bind an owner and a different independent verifier.
6. Generate only a candidate plan unless exact D0–D2 execution authority and current evidence exist.
7. Run structural validation and digest verification.
8. Run independent scrutiny for security, privacy, rights, dependencies, tests, custody, and truthful commercial state.
9. Bind Vault custody, encrypted archive, fingerprints, restore evidence, and DAIL receipts.
10. Promote only through the exact lifecycle gate; never infer production from generation.

## Primary controller

`ct.asset.agent-governor` — ThriveAssetGovernor.

The Governor coordinates the complete estate but may not verify its own originating work.

## Independent verifier

`ct.asset.agent-scrutinizer` — ThriveAssetScrutinizer.

The Scrutinizer must preserve real HOLD conditions rather than converting missing evidence into PASS.

## Lifecycle

`recovered -> specified -> generated_candidate -> controlled_test -> verifying -> certified -> approved_not_live -> live -> maintained -> superseded -> retired`

Not every asset uses every state. Each transition requires evidence.

## Hard invariants

- D2 maximum for automated work.
- D3 human or qualified-professional reserved.
- No sovereign-vote effect.
- No direct-main merge.
- No raw secret or private-identity export.
- No protected implementation in public package records.
- No provider-write inheritance.
- No live checkout or entitlement from a package record.
- No silent deletion.
- Every completion requires owner/verifier separation, digest, evidence, and custody.

## Catalog math

The initial catalog contains 5,760 derived candidates:

`12 pallets × 10 capability families × 12 asset types × 4 deployment profiles`

These candidates productize the existing proprietary estate. They do not silently add 5,760 independent source-IP claims to the authoritative 100,800-asset factory count.

## Commands

```bash
bin/thrive-assets status
bin/thrive-assets search <query>
bin/thrive-assets get <asset_id>
bin/thrive-assets dependencies <asset_id>
bin/thrive-assets generate
bin/thrive-assets validate
bin/thrive-assets scrutinize
```

## Truthful completion language

Use precise states such as `specified candidate`, `structural validation PASS`, `PASS_WITH_CONTROLLED_TEST_HOLDS`, `controlled-test package`, `certified`, `approved not live`, or `live`.

Never call a specified or structurally valid candidate production, installed, rights-cleared, customer-entitled, or monetized.
