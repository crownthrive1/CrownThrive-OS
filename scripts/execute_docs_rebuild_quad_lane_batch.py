#!/usr/bin/env python3
"""Execute one bounded four-lane documentation-rebuild batch.

This is an evidence-producing triage/execution pass, not a terminal-disposition
or substantive-successor acceptance engine. It deterministically derives exact
P0 records from the current 795-row candidate map, excludes Waves 1-6 qualified
records, assigns up to four unique records to each of four operation classes,
and emits auditable receipts.

Official completion counts remain unchanged unless a later, dedicated gate
qualifies an exact record under the substantive-current-successor standard or
an authorized parent accepts a terminal disposition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave1 as wave1
import substantive_rebuild_current_snapshot as current_snapshot

BATCH_SIZE_PER_LANE = 4
CURRENT_WAVES_1_6_SELECTED_COUNT = 57
HISTORICAL_WAVES_1_6_SELECTED_COUNT = 61
P0_CANDIDATE_ESTATE = 449
HISTORICAL_REMAP_REASON = (
    "historical_or_superseded_anchor_is_not_eligible_as_a_current_"
    "substantive_successor"
)
HIGH_RISK_TERMS = (
    "legal", "license", "licensing", "rights", "royalty", "economic",
    "investment", "securities", "patent", "trademark", "franchise",
    "token", "exchange", "settlement", "payment", "credential", "identity",
    "restricted", "private", "authority", "governance", "ownership",
    "security", "2fa", "access", "permission", "verification", "budget",
)


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def prior_ids() -> set[str]:
    """Return the immutable 61-record baseline used by historical Wave 7.

    The current semantic Waves 1-6 view intentionally contains 57 identities.
    Four historical Wave 1 selections are now held for remapping because their
    former anchors are historical or superseded.  Wave 7 receipts predate that
    editorial correction, so their count and identity continuity must be
    reconstructed explicitly rather than changing either the current snapshot
    or the immutable historical receipts.
    """

    snapshot = current_snapshot.load_snapshot()
    if snapshot.get("schema") != current_snapshot.SNAPSHOT_SCHEMA:
        raise ValueError("Wave 7 baseline requires the governed current-snapshot schema")
    if snapshot.get("schema_version") != "1.0.0":
        raise ValueError("Wave 7 baseline requires current-snapshot schema version 1.0.0")
    if snapshot.get("selection_view_schema") != wave1.CURRENT_SELECTION_VIEW_SCHEMA:
        raise ValueError("Wave 7 baseline selection-view schema drift")
    if snapshot.get("current_view_authority") != (
        "current_semantic_recomputation_only_not_a_rewrite_of_historical_receipts"
    ):
        raise ValueError("Wave 7 baseline current-view authority drift")
    if snapshot.get("historical_receipt_authority") != (
        "immutable_independent_evidence_verified_by_sprint_validators"
    ):
        raise ValueError("Wave 7 baseline historical-receipt authority drift")

    without_sha = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    if snapshot.get("snapshot_sha256") != current_snapshot.canonical_sha(without_sha):
        raise ValueError("Wave 7 baseline current-snapshot digest drift")
    if snapshot.get("historical_receipt_view") != current_snapshot.HISTORICAL_RECEIPT_VIEW:
        raise ValueError("Wave 7 baseline historical Waves 1-6 receipt view drift")

    current_ids: set[str] = set()
    cumulative = 0
    current_waves = snapshot.get("current_waves")
    if not isinstance(current_waves, dict) or set(current_waves) != {
        "1", "2", "3", "4", "5", "6"
    }:
        raise ValueError("Wave 7 baseline requires exactly six current wave records")
    for wave_number in range(1, 7):
        record = current_waves[str(wave_number)]
        if not isinstance(record, dict):
            raise ValueError(f"Wave 7 baseline current Wave {wave_number} record is invalid")
        if record.get("selection_view") != wave1.current_selection_view(wave_number):
            raise ValueError(f"Wave 7 baseline current Wave {wave_number} selection state drift")
        selected = record.get("selected_inventory_ids")
        if not isinstance(selected, list) or any(not isinstance(item, str) for item in selected):
            raise ValueError(f"Wave 7 baseline current Wave {wave_number} identities are invalid")
        selected_ids = set(selected)
        if len(selected_ids) != len(selected):
            raise ValueError(f"Wave 7 baseline current Wave {wave_number} identities repeat")
        if len(selected_ids) != record.get("selected_count"):
            raise ValueError(f"Wave 7 baseline current Wave {wave_number} count drift")
        if current_ids & selected_ids:
            raise ValueError("Wave 7 baseline current Waves 1-6 identities overlap")
        current_ids |= selected_ids
        cumulative += len(selected_ids)
        if record.get("cumulative_machine_qualified_p0_count") != cumulative:
            raise ValueError(f"Wave 7 baseline current Wave {wave_number} cumulative count drift")
        if record.get("p0_outside_current_waves_count") != P0_CANDIDATE_ESTATE - cumulative:
            raise ValueError(f"Wave 7 baseline current Wave {wave_number} pending count drift")
    if len(current_ids) != CURRENT_WAVES_1_6_SELECTED_COUNT:
        raise ValueError(
            "Wave 7 baseline requires 57 current Waves 1-6 identities, "
            f"found {len(current_ids)}"
        )

    remap_records = snapshot.get("historical_wave_1_current_remap_required")
    if not isinstance(remap_records, list):
        raise ValueError("Wave 7 baseline remap diagnostics are missing")
    remap_ids: set[str] = set()
    for record in remap_records:
        if not isinstance(record, dict):
            raise ValueError("Wave 7 baseline remap diagnostic is invalid")
        inventory_id = record.get("inventory_id")
        if not isinstance(inventory_id, str) or not inventory_id:
            raise ValueError("Wave 7 baseline remap identity is invalid")
        if record.get("historical_receipt_state") != "selected":
            raise ValueError(f"{inventory_id}: historical receipt state drift")
        if record.get("current_semantic_state") != "held_remap_required":
            raise ValueError(f"{inventory_id}: current semantic remap state drift")
        if record.get("reason") != HISTORICAL_REMAP_REASON:
            raise ValueError(f"{inventory_id}: historical remap reason drift")
        anchors = record.get("ineligible_anchor_routes")
        reasons = record.get("editorial_eligibility_reasons")
        if not isinstance(anchors, list) or not anchors:
            raise ValueError(f"{inventory_id}: historical remap anchor evidence is missing")
        if not isinstance(reasons, list) or not reasons:
            raise ValueError(f"{inventory_id}: historical remap editorial evidence is missing")
        if not set(reasons) & {
            "primary_audience_historical",
            "content_state_historical",
            "content_state_superseded",
        }:
            raise ValueError(f"{inventory_id}: historical remap editorial state is invalid")
        if inventory_id in remap_ids:
            raise ValueError(f"{inventory_id}: historical remap identity repeats")
        remap_ids.add(inventory_id)

    if remap_ids != set(current_snapshot.HISTORICAL_WAVE1_REMAP_REQUIRED_IDS):
        raise ValueError("Wave 7 baseline historical Wave 1 remap identity drift")
    if current_ids & remap_ids:
        raise ValueError("Wave 7 baseline remap identities overlap the current semantic view")

    historical_ids = current_ids | remap_ids
    if len(historical_ids) != HISTORICAL_WAVES_1_6_SELECTED_COUNT:
        raise ValueError(
            "Wave 7 baseline requires 61 immutable historical identities, "
            f"found {len(historical_ids)}"
        )
    return historical_ids


def normalized_text(row: dict[str, Any]) -> str:
    parts = [
        row.get("legacy_title", ""),
        row.get("legacy_section", ""),
        row.get("legacy_subcategory", ""),
        row.get("current_state_candidate", ""),
        " ".join(str(x) for x in row.get("flags", [])),
    ]
    return " ".join(str(x) for x in parts).casefold()


def is_high_risk(row: dict[str, Any]) -> bool:
    text = normalized_text(row)
    return bool(row.get("flags")) or any(term in text for term in HIGH_RISK_TERMS)


def base_receipt(row: dict[str, Any], lane: str, operation: str) -> dict[str, Any]:
    return {
        "inventory_id": str(row["inventory_id"]),
        "article_id": row.get("article_id"),
        "lane": lane,
        "operation": operation,
        "legacy_section": row.get("legacy_section"),
        "legacy_subcategory": row.get("legacy_subcategory"),
        "legacy_title": row.get("legacy_title"),
        "priority": row.get("priority"),
        "candidate_disposition": row.get("disposition_candidate"),
        "current_state_candidate": row.get("current_state_candidate"),
        "target_routes": list(row.get("target_routes", [])),
        "missing_target_routes": list(row.get("missing_target_routes", [])),
        "flags": list(row.get("flags", [])),
        "source_refs": list(row.get("source_refs", ["S11"])),
        "historical_body_status": row.get("body_status", "reconstruction_required"),
        "terminal_acceptance": False,
        "parent_review_required": True,
    }


def lane_a_candidates(rows: list[dict[str, Any]], used: set[str]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        rid = str(row["inventory_id"])
        if rid in used or is_high_risk(row):
            continue
        if row.get("disposition_candidate") != "merged_successor":
            continue
        if row.get("missing_target_routes") or not row.get("target_routes"):
            continue
        receipt = base_receipt(row, "A", "substantive_successor_verification")
        quality = []
        for route in row.get("target_routes", []):
            try:
                quality.append(wave1.route_quality(route))
            except FileNotFoundError:
                quality.append({"route": route, "path": None, "status": "missing"})
        qualified_route_count = sum(
            1 for q in quality
            if q.get("body_characters", 0) >= 1800 and q.get("internal_link_count", 0) >= 3
        )
        receipt.update({
            "route_quality_observations": quality,
            "qualified_route_observation_count": qualified_route_count,
            "lane_a_zero_flag_invariant": True,
            "result": "CANDIDATE_REQUIRES_DEDICATED_SUBSTANTIVE_GATE",
            "official_qualification_count_delta": 0,
        })
        out.append(receipt)
        if len(out) == BATCH_SIZE_PER_LANE:
            break
    return out


def lane_b_candidates(rows: list[dict[str, Any]], used: set[str]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        rid = str(row["inventory_id"])
        if rid in used or not is_high_risk(row):
            continue
        receipt = base_receipt(row, "B", "specialist_evidence_resolution")
        receipt.update({
            "specialist_reason": "high_risk_semantics_or_any_nonempty_candidate_flag",
            "result": "HOLD_SPECIALIST_EVIDENCE_REQUIRED",
            "authority_effect": "NONE_UNLESS_SEPARATELY_PROVEN",
            "official_qualification_count_delta": 0,
        })
        out.append(receipt)
        if len(out) == BATCH_SIZE_PER_LANE:
            break
    return out


def lane_c_candidates(rows: list[dict[str, Any]], used: set[str]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        rid = str(row["inventory_id"])
        if rid in used:
            continue
        body = str(row.get("body_status", "reconstruction_required"))
        if body not in {"reconstruction_required", "missing", "partial_source", "not_found"}:
            continue
        receipt = base_receipt(row, "C", "historical_body_recovery")
        receipt.update({
            "recovery_sources_checked_by_this_batch": ["repository_candidate_map", "S11_title_hierarchy_authority"],
            "s94_body_archive_available_to_this_batch": False,
            "result": "NOT_RECOVERED_FROM_AVAILABLE_REPOSITORY_SOURCES",
            "historical_body_fabricated": False,
            "official_qualification_count_delta": 0,
        })
        out.append(receipt)
        if len(out) == BATCH_SIZE_PER_LANE:
            break
    return out


def lane_d_candidates(rows: list[dict[str, Any]], used: set[str]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        rid = str(row["inventory_id"])
        if rid in used:
            continue
        disposition = str(row.get("disposition_candidate", ""))
        if disposition not in {
            "canonical_article", "merged_successor", "permanent_redirect",
            "restricted_record", "superseded_history", "unresolved_source",
        }:
            continue
        receipt = base_receipt(row, "D", "terminal_disposition_preparation")
        unresolved = []
        if row.get("missing_target_routes"):
            unresolved.append("missing_target_routes")
        if not row.get("target_routes") and disposition in {"merged_successor", "permanent_redirect"}:
            unresolved.append("stable_target_not_verified")
        if str(row.get("body_status", "reconstruction_required")) == "reconstruction_required":
            unresolved.append("historical_body_reconstruction_pending")
        if is_high_risk(row):
            unresolved.append("specialist_clearance_required")
        receipt.update({
            "proposed_disposition": disposition,
            "unresolved_before_acceptance": sorted(set(unresolved)),
            "result": "PREPARED_NOT_ACCEPTED",
            "terminal_acceptance": False,
            "official_qualification_count_delta": 0,
        })
        out.append(receipt)
        if len(out) == BATCH_SIZE_PER_LANE:
            break
    return out


def build() -> dict[str, Any]:
    rows = wave1.aggregate_candidate_rows()
    qualified = prior_ids()
    p0 = [r for r in rows if r.get("priority") == "P0" and str(r["inventory_id"]) not in qualified]
    p0.sort(key=lambda r: str(r["inventory_id"]))

    if len(rows) != 795:
        raise ValueError("source universe must remain 795")
    if len(qualified) != 61:
        raise ValueError(f"expected 61 Waves 1-6 qualified records, found {len(qualified)}")
    if len(p0) != 388:
        raise ValueError(f"expected 388 remaining P0 records, found {len(p0)}")

    used: set[str] = set()
    lanes: dict[str, list[dict[str, Any]]] = {}
    for lane, chooser in (
        ("A", lane_a_candidates),
        ("B", lane_b_candidates),
        ("C", lane_c_candidates),
        ("D", lane_d_candidates),
    ):
        selected = chooser(p0, used)
        if len(selected) != BATCH_SIZE_PER_LANE:
            raise ValueError(f"lane {lane} could select only {len(selected)} records")
        ids = {str(r["inventory_id"]) for r in selected}
        if ids & used:
            raise ValueError(f"lane {lane} overlaps an earlier operation lease")
        used |= ids
        lanes[lane] = selected

    if any(r.get("flags") for r in lanes["A"]):
        raise ValueError("Lane A must contain zero candidate flags")
    if any(is_high_risk(r) for r in lanes["A"]):
        raise ValueError("Lane A contains a high-risk semantic record")

    payload: dict[str, Any] = {
        "schema_version": "1.0.1",
        "execution_id": "ct.docs.rebuild.wave7.quad-lane.batch-001",
        "source_universe_count": 795,
        "p0_candidate_estate": 449,
        "waves_1_6_machine_qualified": 61,
        "remaining_p0_before_batch": 388,
        "parallel_lane_count": 4,
        "records_per_lane": BATCH_SIZE_PER_LANE,
        "unique_records_touched": len(used),
        "lanes": lanes,
        "counting": {
            "machine_qualified_delta": 0,
            "remaining_p0_delta": 0,
            "official_machine_qualified_after_batch": 61,
            "official_remaining_p0_after_batch": 388,
            "reason": "triage/recovery/disposition-preparation receipts are execution evidence but do not equal substantive qualification or terminal acceptance",
        },
        "guardrails": {
            "unique_operation_leases": True,
            "lane_a_requires_zero_flags": True,
            "lane_a_high_risk_semantics_prohibited": True,
            "invented_inventory_ids": False,
            "historical_body_recovery_fabricated": False,
            "terminal_disposition_self_authorized": False,
            "specialist_authority_promoted": False,
            "parent_review_required": True,
            "phase_3_entry": "blocked_pending_phase_2_99_hard_exit",
        },
    }
    payload["execution_sha256"] = canonical_hash(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build()
    print("PASS_DOCS_REBUILD_QUAD_LANE_BATCH")
    print(f"execution_id={result['execution_id']}")
    print(f"unique_records_touched={result['unique_records_touched']}")
    for lane in ("A", "B", "C", "D"):
        ids = [r["inventory_id"] for r in result["lanes"][lane]]
        print(f"lane_{lane}_inventory_ids=" + ",".join(ids))
        for receipt in result["lanes"][lane]:
            print("receipt=" + json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    print("official_machine_qualified_after_batch=61")
    print("official_remaining_p0_after_batch=388")
    print("terminal_disposition_self_authorized=false")
    print("execution_sha256=" + result["execution_sha256"])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"output={args.output}")


if __name__ == "__main__":
    main()
