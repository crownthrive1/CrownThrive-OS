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

The companion descriptor is `data/help_center_article_manifest.v1.bundle.json`.

The bundle preserves exactly **795** recovered records in original recovered order. Each compact record contains only `inventory_id`, `recovered_order`, `recovered_section`, `recovered_subcategory`, and `recovered_title`.

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

The source authority remains S11 / `Help Center Structure (2).pdf` with registered SHA-256 `c7f16bd8b504431e71a4407728e22ab9a950ab9dcd891d831bd78f6802335b0f`.

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

`scripts/validate_help_center_article_manifest_bundle.py` verifies the exact ordered bundle, byte/hash invariants, compact schema/source authority, 795-record identity/order, nine-section census, safe unresolved defaults, continued candidate status and continued terminal-disposition/P0-P1 incompleteness. It deliberately fails closed if those unresolved states are falsely promoted.

## Self-heal evidence

During materialization, byte-level comparison detected that the initial third transport part did not match the expected source-derived segment. The packet was repaired before PR opening by replacing only that part with the byte-exact deterministic segment. No validator was weakened and no recovered title was changed to make the bundle pass.

## Current-main reconciliation

PR #91 is now reconciled onto canonical `main` `922a077cfd6cdb29cd47b4a5c3f13557bb26cd9e` through merge-parent reconciliation commit `13ecdcc04f0fc5a0b62c08bbe5e945a2c62e0f55`.

The nine commits that moved `main` from the former `1054e79226338809a5a91211c2271c19ff96b362` baseline changed only the repository pull-request template, shared Documentation/Governed-Merge workflows, homepage, homepage validator and documentation-governance standards. None overlaps the nine PR #91 paths. The current homepage/source-propagation control plane introduced by PRs #117/#119 is therefore inherited rather than overwritten.

Canonical hard-exit ledger v1.2.2 still records **2 PASS / 6 blocking hard-exit categories**. CT-P299-GATE-002 remains `not_met`. The ledger still names an older PR #91 candidate head because it is a canonical snapshot record; this draft does not rewrite the canonical hard-exit ledger before governed merge.

Source scan expansion in this reconciliation found `Help Center Structure (2).pdf` in connected Google Drive and File Library in addition to the registered repository authority. Gmail also contains the December 8, 2025 SimpleBase outage thread for `help.crownthrive.com` and historical backlink references. Those records corroborate existence/history only; they do **not** recover missing article bodies. No S94 body archive was recovered in the available Drive/File Library/Gmail scan, so S94 remains explicitly unresolved.

A filename-level collision check against active PRs #97, #101, #102 and #103 previously found no overlap; exact-head collision review remains mandatory before promotion because those branches can move.

The dedicated `.github/workflows/help-center-795-manifest.yml` directly compiles and runs the bundle validator using the repository's pinned Node-24-compatible checkout/setup-python actions. Current Documentation Governance, Security Governance and Governed Merge Gate must all rerun on the new exact head before any old vote can count.

Machine-readable current-main reconciliation and Agent B handoff are recorded in `developers/manifests/help-center-795-materialization-reconciliation.v1.json`.

## What this closes — and what it does not

Once this packet is independently governed and merged, only `complete_machine_manifest_generated_in_repo` may move to **true**.

It does **not** close terminal disposition for all 795 records; section/category-to-current-taxonomy mapping; exposure/risk/owner classification; canonical route or explicit nonpublic state; platform/source mapping; navigation disposition; S94 body recovery; P0/P1 substantive reconstruction or explicit unresolved-source closure; D2/D3 approvals; CT-P299-GATE-002; or the Phase 2.99 hard exit.

## Authority and risk

This remains **D1 deterministic source/evidence materialization and reconciliation**. It does not make semantic current-state decisions. No secret, private routing value, customer data, payment state, provider credential, legal term, license grant, production write, identity permission or Phase-9 crypto/token state is included.

Agent F is non-voting and does not self-approve this packet. A/B/C/D/S remain the only sovereign voter pool. Prior exact-head decisions are stale after the current-main/head change and must be replaced by fresh head-bound decisions after current controls pass.

## Rollback

Rollback is a straight revert of this bounded nine-file packet plus the reconciliation merge commit. S11, the existing 795 seed contract and historical inventory remain untouched; there is no external/provider/customer state to unwind.

## Next articleization packet

After canonical merge, update the Phase-2.99 closure ledger and seed article record to mark only machine-manifest materialization complete. Then begin controlled terminal disposition in risk order:

`P0 legal/rights/security/economic/canon → P1 customer/operator → P2 historical/research/reserve`.

Every disposition must remain source-grounded and independently validated. S94 remains open; unavailable bodies stay unresolved rather than being generated and labeled as historical originals.
