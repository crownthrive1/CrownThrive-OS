# Phase 2.99 — Help Center 795 Machine-Manifest Materialization

**Original materialization date:** 2026-08-19  
**Current-truth reconciliation:** 2026-08-20  
**Workstream:** Phase 2.99 / Workstream 0 — Articleization  
**State:** complete 795-title/hierarchy machine manifest is canonical; terminal dispositions, per-record exposure/IP classification and P0/P1 reconstruction remain incomplete  
**Canonical phase state:** Phase 2 / 2.99; Phase 3 remains `blocked_pending_phase_2_99_hard_exit_and_full_docs_reconciliation`

## Purpose

The recovered CrownThrive Help Center estate has a verified 795-record title/hierarchy census, stable seed identities and a deterministic compact machine bundle. Governed PR #91 materialized that complete bundle into canonical `main` without inventing article bodies or current production state.

This reconciliation corrects the repository surfaces that still described the already-merged bundle as a candidate. It does **not** change any recovered title, bundle part, bundle hash, historical body, current policy, provider state, rights state or Phase-3 authority.

## Canonical materialization

Governed PR #91 merged as canonical commit:

`8fcb68bf209e32ba2cd265e1b6ca730cb8da64d7`

The only closure predicate established by that merge is:

`complete_machine_manifest_generated_in_repo = true`

The complete compact manifest remains stored as:

```text
data/help_center_article_manifest.v1.json.gz.b64.part01
data/help_center_article_manifest.v1.json.gz.b64.part02
data/help_center_article_manifest.v1.json.gz.b64.part03
```

The companion descriptor is `data/help_center_article_manifest.v1.bundle.json`.

The deterministic bundle still preserves exactly **795** recovered records, in recovered order, with only `inventory_id`, `recovered_order`, `recovered_section`, `recovered_subcategory`, and `recovered_title` in each compact record.

## Byte-level integrity unchanged

This post-merge reconciliation does not regenerate or alter the three bundle parts.

```text
encoding: base64(gzip(utf8-json))
parts: 3
base64 characters: 26,796
gzip bytes: 20,097
JSON bytes: 93,648
gzip SHA-256: 8ab1c4276463d1f72131c616e1d913de0bff30087c1a6ba6327145379380ed39
JSON SHA-256: 5920b69bf5731b7647ae24523a823dd938a912c37ca0c4da1095b4145acfbc53
```

Source authority remains `S11 — Help Center Structure (2).pdf` with registered SHA-256 `c7f16bd8b504431e71a4407728e22ab9a950ab9dcd891d831bd78f6802335b0f`.

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

These are historical recovery-corpus counts, not current platform, policy, product, rights, deployment or revenue counts.

## Current body-recovery posture

`S11` is title/hierarchy authority. `S94` and surviving `help.crownthrive.com` index/search references are partial historical recovery evidence only.

SimpleBase is retired and is **not** an active CrownThrive documentation dependency or restoration target. Retaining the historical support hostname as a CrownThrive-controlled alias/redirect is independent of SimpleBase.

The governed reconstruction standard now permits `source_not_recovered` as a terminal historical-body disposition after sufficient source search. This preserves title, hierarchy, historical existence and source lineage without manufacturing lost prose. Where the institution still needs current documentation, the replacement must be a new current artifact built from current authoritative evidence and must never be represented as the historical original.

## Publication and IP boundary

The recovered 795-title estate is not automatically a 795-page public publishing entitlement. Before a recovered record is publicly projected, its exact output must pass the #131 exposure/IP classification appropriate to that record.

Public-safe projections may expose approved identity, doctrine, interface, status and evidence summaries. Restricted legal, rights, private-evidence, credential/security, proprietary implementation, trade-secret or other controlled material remains fail-closed.

A source record, content hash or Fingerprint ID identifies an exact record version. It does not prove current deployment, ownership, legal authority, rights clearance or truth of the underlying claim.

## Deterministic validation

`scripts/validate_help_center_article_manifest_bundle.py` continues to verify the exact ordered compact bundle, byte/hash invariants, source authority, 795-record identity/order, safe defaults and nine-section census.

The validator now additionally fails closed unless:

- the bundle descriptor records canonical PR #91 materialization;
- the canonical merge SHA remains `8fcb68bf209e32ba2cd265e1b6ca730cb8da64d7`;
- the seed records machine-manifest materialization as complete;
- `source_not_recovered` is available as a governed terminal state;
- SimpleBase is marked retired historical-only rather than an active authenticated recovery dependency;
- per-record #131 exposure/IP classification remains explicit before blanket publication;
- terminal disposition and P0/P1 reconstruction remain incomplete; and
- Phase 3 remains blocked while GATE-002 and the full-documentation hard gate remain open.

The dedicated `.github/workflows/help-center-795-manifest.yml` now triggers when the current-truth seed changes, so seed/descriptor/validator drift cannot bypass the dedicated bundle control.

## Current unresolved scope

Canonical machine materialization does **not** close:

- terminal disposition for all 795 records;
- per-record public/restricted exposure and #131 IP classification;
- current taxonomy and section/category mapping;
- risk classification;
- owner or owner-queue assignment;
- canonical route or explicit nonpublic state;
- current platform/source mapping;
- navigation or intentionally-unlisted disposition;
- historical-body recovery terminalization where evidence supports `source_not_recovered`;
- P0/P1 substantive current reconstruction or explicit terminal unresolved-source closure;
- required D2/D3 specialist/human approvals;
- CT-P299-GATE-002;
- the full-documentation estate hard gate; or
- the Phase 2.99 hard exit.

## Draft and collision reconciliation

The old PR #101 branch still contains broad historical/current-state work but descends from an obsolete pre-PR91 base and is currently non-mergeable. It is not promoted wholesale to repair the seed.

PR #129 remains the current-main owner for broader source-register/revival/current-state documentation and does not own the corrected seed, bundle descriptor or dedicated bundle validator paths. PR #124 remains a bounded Agent-F post-PR91 handoff packet and does not replace this post-merge current-truth correction.

The current packet is therefore intentionally bounded to the specific machine-materialization/seed control family rather than flattening unrelated branch histories.

## Authority, risk and rollback

This reconciliation is **D1 source/evidence/current-truth documentation work**. Agent F remains non-voting and does not self-approve it. CI is technical evidence, not sovereign quorum or specialist acceptance.

Rollback is a straight revert of this bounded post-merge correction. The three canonical bundle parts, S11 source authority and the governed PR #91 merge remain intact. There is no provider, credential, payment, customer, rights or production state to unwind.

## Next articleization packet

The next hard-exit sequence remains:

`795-title exposure/IP pre-classification → P0/P1 cohort derivation → source_not_recovered terminalization where supported → current-authoritative mapping → taxonomy/exposure/risk/owner/route/navigation initialization → applicable specialist/quorum acceptance`

Source recovery and R&D may continue in parallel, but no registry growth, source discovery, fingerprint assignment or candidate-current page may be mistaken for GATE-002 closure or Phase-3 authority.
