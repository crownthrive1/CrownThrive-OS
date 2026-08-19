# Phase 2.99 — Help Center 795 Machine-Manifest Materialization

**Date:** 2026-08-19  
**Workstream:** Phase 2.99 / Workstream 0 — Articleization  
**State:** complete machine-manifest candidate materialized on branch; terminal dispositions and P0/P1 reconstruction remain incomplete  
**Canonical phase state:** Phase 2 / 2.99; Phase 3 remains `blocked_pending_phase_2_99_hard_exit`

## Purpose

The recovered 795-title Help Center estate already had a verified source census, stable seed schema and deterministic generator. This packet advances the next mechanical closure predicate: materialize the complete recovered title/hierarchy machine manifest in the repository without inventing article bodies or current production state.

This packet is source-preserving. It does **not** decide legal/current/historical disposition, reconstruct missing prose, infer production capability, or complete P0/P1 articleization.

## Materialized artifact

The complete compact manifest is stored as a deterministic three-part base64/gzip bundle:

```text
data/help_center_article_manifest.v1.json.gz.b64.part01
data/help_center_article_manifest.v1.json.gz.b64.part02
data/help_center_article_manifest.v1.json.gz.b64.part03
```

The companion descriptor is:

`data/help_center_article_manifest.v1.bundle.json`

The bundle preserves exactly **795** recovered records in original recovered order. Each compact record contains only:

1. `inventory_id`;
2. `recovered_order`;
3. `recovered_section`;
4. `recovered_subcategory`;
5. `recovered_title`.

Safe shared defaults remain explicit at the manifest level:

- source `S11`;
- `title_and_hierarchy_recovered`;
- body `reconstruction_required`;
- confidence `high`;
- disposition `source_recovery_pending`;
- content state `reconstruction_required`;
- exposure/risk `unclassified`;
- no canonical route, owner, platform mapping or effective date yet.

## Byte-level integrity

The descriptor fixes the expected encoding and integrity values:

```text
encoding: base64(gzip(utf8-json))
parts: 3
base64 characters: 26,796
gzip bytes: 20,097
JSON bytes: 93,648
gzip SHA-256: 8ab1c4276463d1f72131c616e1d913de0bff30087c1a6ba6327145379380ed39
JSON SHA-256: 5920b69bf5731b7647ae24523a823dd938a912c37ca0c4da1095b4145acfbc53
```

The source authority remains S11 / `Help Center Structure (2).pdf` with registered SHA-256:

`c7f16bd8b504431e71a4407728e22ab9a950ab9dcd891d831bd78f6802335b0f`

The stored bundle is intentionally compact to keep repository transport deterministic while retaining all 795 recovered title identities.

## Section census preserved

| Recovered section | Records |
| --- | ---: |
| CHLOM | 297 |
| Convergent Ecosystem | 206 |
| CrownThrive Legal Depot | 198 |
| CrownThrive HQ | 46 |
| Thrive Flywheel | 14 |
| MM Suites | 13 |
| Cultural Imprint Engine (CIE) | 11 |
| Hybrid Incubator | 5 |
| Investor Relations | 5 |
| **Total** | **795** |

## Deterministic validation

`scripts/validate_help_center_article_manifest_bundle.py` verifies:

- the exact three ordered bundle parts;
- concatenated base64 length;
- gzip and uncompressed JSON SHA-256 values;
- compact schema version and source authority;
- exactly 795 records;
- exact `HC-0001` through `HC-0795` inventory sequence;
- exact recovered orders 1 through 795;
- derivable stable article identities `ct.article.recovered.0001` through `.0795`;
- nine-section census;
- safe default recovery/disposition/risk/exposure state;
- continued candidate/noncanonical status;
- continued terminal-disposition and P0/P1 incompleteness.

The validator can optionally materialize the validated compact JSON locally for inspection. That derived file does not acquire greater source authority than S11.

## Self-heal evidence

During materialization, a byte-level comparison of the stored Git blob identities against the deterministic local bundle detected that the initial third transport part did not match the expected final 8,932-character segment. The packet was repaired **before PR opening** by replacing only that part with the byte-exact deterministic segment. The repaired Git blob SHA now matches the expected source-derived blob.

No validator was weakened and no recovered title was changed to make the bundle pass.

## What this closes — and what it does not

Once this packet is governed and merged, the Workstream-0 predicate:

`complete_machine_manifest_generated_in_repo`

may move to **true**.

It does **not** close:

- terminal disposition for all 795 records;
- section/category-to-current-taxonomy mapping for all records;
- exposure/risk/owner classification;
- current canonical route or explicit nonpublic state;
- current platform/source mapping;
- navigation/intentionally-unlisted state;
- P0/P1 substantive reconstruction or explicit unresolved-source closure;
- D2/D3 specialist/human approvals;
- Phase 2.99 hard exit.

## Authority and risk

This is a bounded deterministic source-materialization packet. It does not make semantic current-state decisions. Treat as D1 evidence/data plumbing unless independent review identifies a higher-risk consequence.

No secret, private routing value, customer data, payment state, provider credential, legal term, license grant, production write, identity permission, or Phase-9 crypto/token state is included.

## Rollback

Rollback is a straight revert of the bundle, descriptor, validator and this changelog. The S11 source, existing 795 seed contract and historical inventory remain untouched.

## Next articleization packet

After canonical merge, update the Phase-2.99 closure ledger and seed article record to mark only machine-manifest materialization complete. Then begin controlled terminal disposition in risk order:

`P0 legal/rights/security/economic/canon → P1 customer/operator → P2 historical/research/reserve`.

Every disposition must remain source-grounded and independently validated.