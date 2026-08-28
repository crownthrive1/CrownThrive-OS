#!/usr/bin/env python3
"""Build and validate the current semantic view of substantive rebuild waves.

Historical Sprint 7-12 receipts remain immutable evidence.  This snapshot is a
separate, versioned recomputation over today's governed documentation profiles,
including semantic state-lane precedence and editorial eligibility ceilings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import build_substantive_rebuild_wave1 as wave1
import build_substantive_rebuild_wave2 as wave2
import build_substantive_rebuild_wave3 as wave3
import build_substantive_rebuild_wave4 as wave4
import build_substantive_rebuild_wave5 as wave5
import build_substantive_rebuild_wave6 as wave6

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "data/documentation/substantive-rebuild-current-semantic-snapshot.v1.json"
SNAPSHOT_SCHEMA = "ct.docs.substantive-current-semantic-snapshot/v1"
BUILDERS = (wave1, wave2, wave3, wave4, wave5, wave6)

HISTORICAL_RECEIPT_VIEW = {
    "1": {"selected_count": 16, "wave_sha256": "98021ca9c32a4cdf7cd9d8588271b1451f09d6f5cafb09629771943b10272add"},
    "2": {"selected_count": 19, "wave_sha256": "234cf1a35ed005b3b3ba20a2175634e4419948bc0d428ca3b379b206e50553cb"},
    "3": {"selected_count": 17, "wave_sha256": "e7b5c56af1a698d3466259fafc2a8fbceee76220d1befe2cd1be96a6c123fe12"},
    "4": {"selected_count": 5, "wave_sha256": "d688f197103c89495fed775fe3334c495f1a0769818db00570359f45179709a1"},
    "5": {"selected_count": 1, "wave_sha256": "0c7359b03dbf17f539adf055a3ad620243a7a3ef604ef864aaf6654f04cff9a8"},
    "6": {"selected_count": 3, "wave_sha256": "c4389ff5f19674813e0a89734a9aa6b65b7e6ecba2e4b3710278fa05a4616caa"},
}

HISTORICAL_WAVE1_REMAP_REQUIRED_IDS = frozenset({"HC-0072", "HC-0073", "HC-0074", "HC-0211"})


def canonical_sha(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _remaining_count(result: dict[str, Any]) -> int:
    keys = [key for key in result if key.startswith("p0_outside_waves_")]
    if len(keys) == 1:
        return int(result[keys[0]])
    if not keys:
        return int(result["p0_candidate_count"]) - int(result["selected_count"])
    raise ValueError(f"ambiguous current remaining-count fields: {sorted(keys)}")


def _state_lane_deferrals(result: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in result["held_records"]:
        reasons = sorted(reason for reason in row.get("hold_reasons", []) if str(reason).startswith("deferred_to_wave_"))
        if not reasons:
            continue
        records.append({
            "inventory_id": row["inventory_id"],
            "current_state_candidate": row["current_state_candidate"],
            "deferral_reasons": reasons,
            "source_specialist_review_flags": row.get("source_specialist_review_flags", []),
        })
    return sorted(records, key=lambda item: item["inventory_id"])


def current_wave_record(result: dict[str, Any], wave_number: int) -> dict[str, Any]:
    cumulative = int(result.get("cumulative_machine_qualified_p0_count", result["selected_count"]))
    return {
        "wave": wave_number,
        "selection_view": result["selection_view"],
        "selected_count": int(result["selected_count"]),
        "held_count": int(result["held_count"]),
        "cumulative_machine_qualified_p0_count": cumulative,
        "p0_outside_current_waves_count": _remaining_count(result),
        "selected_inventory_ids": sorted(str(row["inventory_id"]) for row in result["selected_records"]),
        "selected_section_counts": result.get("selected_section_counts", {}),
        "selected_state_counts": result.get("selected_state_counts", {}),
        "selected_anchor_counts": result.get("selected_anchor_counts", {}),
        "state_lane_deferrals": _state_lane_deferrals(result),
        "wave_sha256": result["wave_sha256"],
    }


def _specialist_review_diagnostics(result: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for row in result["selected_records"] + result["held_records"]:
        flags = row.get("source_specialist_review_flags", [])
        if not flags:
            continue
        diagnostics.append({
            "inventory_id": row["inventory_id"],
            "current_state_candidate": row["current_state_candidate"],
            "source_specialist_review_flags": flags,
            "current_selection_state": "selected" if row in result["selected_records"] else "held",
        })
    return sorted(diagnostics, key=lambda item: item["inventory_id"])


def _historical_wave1_remap_diagnostics(result: dict[str, Any]) -> list[dict[str, Any]]:
    held_by_id = {row["inventory_id"]: row for row in result["held_records"]}
    records: list[dict[str, Any]] = []
    missing = HISTORICAL_WAVE1_REMAP_REQUIRED_IDS - held_by_id.keys()
    if missing:
        raise ValueError("historical Wave 1 identities expected in current held/remap-required view: " f"{sorted(missing)}")
    for inventory_id in sorted(HISTORICAL_WAVE1_REMAP_REQUIRED_IDS):
        row = held_by_id[inventory_id]
        ineligible = [quality for quality in row.get("anchor_quality_checked", []) if quality.get("editorial_current_successor_eligible") is False]
        if not ineligible:
            raise ValueError(f"{inventory_id}: remap-required diagnostic lacks an editorially ineligible anchor")
        records.append({
            "inventory_id": inventory_id,
            "historical_receipt_state": "selected",
            "current_semantic_state": "held_remap_required",
            "current_state_candidate": row["current_state_candidate"],
            "reason": "historical_or_superseded_anchor_is_not_eligible_as_a_current_substantive_successor",
            "ineligible_anchor_routes": sorted({quality["route"] for quality in ineligible}),
            "editorial_eligibility_reasons": sorted({reason for quality in ineligible for reason in quality["editorial_eligibility_reasons"]}),
            "source_specialist_review_flags": row.get("source_specialist_review_flags", []),
        })
    return records


def build_current_snapshot() -> dict[str, Any]:
    results = [builder.build() for builder in BUILDERS]
    payload: dict[str, Any] = {
        "schema": SNAPSHOT_SCHEMA,
        "schema_version": "1.0.0",
        "current_view_authority": "current_semantic_recomputation_only_not_a_rewrite_of_historical_receipts",
        "historical_receipt_authority": "immutable_independent_evidence_verified_by_sprint_validators",
        "quality_algorithm": wave1.ROUTE_QUALITY_ALGORITHM,
        "selection_view_schema": wave1.CURRENT_SELECTION_VIEW_SCHEMA,
        "historical_receipt_view": HISTORICAL_RECEIPT_VIEW,
        "current_waves": {str(number): current_wave_record(result, number) for number, result in enumerate(results, start=1)},
        "historical_wave_1_current_remap_required": _historical_wave1_remap_diagnostics(results[0]),
        "source_specialist_review_diagnostics": _specialist_review_diagnostics(results[0]),
        "target_mapping_policy": "no_new_target_mappings_inferred",
    }
    payload["snapshot_sha256"] = canonical_sha(payload)
    return payload


def load_snapshot() -> dict[str, Any]:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def validate_current_wave(result: dict[str, Any], wave_number: int, snapshot: dict[str, Any] | None = None) -> list[str]:
    current = snapshot if snapshot is not None else load_snapshot()
    errors: list[str] = []
    if current.get("schema") != SNAPSHOT_SCHEMA:
        errors.append("current semantic snapshot schema drift")
    if current.get("quality_algorithm") != wave1.ROUTE_QUALITY_ALGORITHM:
        errors.append("current semantic snapshot quality algorithm drift")
    if current.get("selection_view_schema") != wave1.CURRENT_SELECTION_VIEW_SCHEMA:
        errors.append("current semantic snapshot selection-view schema drift")
    without_sha = {key: value for key, value in current.items() if key != "snapshot_sha256"}
    if current.get("snapshot_sha256") != canonical_sha(without_sha):
        errors.append("current semantic snapshot digest drift")
    expected = current.get("current_waves", {}).get(str(wave_number))
    actual = current_wave_record(result, wave_number)
    if expected != actual:
        errors.append(f"current semantic Wave {wave_number} snapshot drift")
    if current.get("historical_receipt_view") != HISTORICAL_RECEIPT_VIEW:
        errors.append("historical receipt facts drifted in current semantic snapshot")
    if wave_number == 1:
        try:
            remap = _historical_wave1_remap_diagnostics(result)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if current.get("historical_wave_1_current_remap_required") != remap:
                errors.append("historical Wave 1 current remap-required diagnostics drift")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", action="store_true", dest="print_snapshot")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    built = build_current_snapshot()
    if args.print_snapshot:
        print(json.dumps(built, ensure_ascii=False, indent=2))
    if args.check or not args.print_snapshot:
        if not SNAPSHOT_PATH.is_file():
            print(f"FAIL: missing {SNAPSHOT_PATH.relative_to(ROOT)}")
            return 1
        stored = load_snapshot()
        if stored != built:
            print("BEGIN_COMPUTED_SNAPSHOT_JSON")
            print(json.dumps(built, ensure_ascii=False, separators=(",", ":")))
            print("END_COMPUTED_SNAPSHOT_JSON")
            print("FAIL: current semantic substantive-rebuild snapshot drift")
            return 1
        print("PASS_SUBSTANTIVE_REBUILD_CURRENT_SEMANTIC_SNAPSHOT")
        print("snapshot_sha256=" + built["snapshot_sha256"])
        print("selected_counts=" + json.dumps([built["current_waves"][str(index)]["selected_count"] for index in range(1, 7)]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
