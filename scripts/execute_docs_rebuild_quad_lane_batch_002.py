#!/usr/bin/env python3
"""Execute Wave 7 documentation rebuild quad-lane batch 002.

Batch 002 advances the work queue without silently changing qualification truth.
It preserves the 65-qualified / 384-pending baseline established by the first
Wave 7 AdLuxe substantive gate, excludes every identity touched in batch 001
from reselection, and executes four bounded lanes across 16 new exact records.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave1 as wave1
import execute_docs_rebuild_quad_lane_batch as q1

BATCH1 = ROOT / "developers/manifests/docs-rebuild-quad-lane-batch-001.v1.json"
GATE1 = ROOT / "developers/manifests/docs-wave7-adluxe-substantive-gate-001.v1.json"
BATCH_SIZE_PER_LANE = 4


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build() -> dict[str, Any]:
    rows = wave1.aggregate_candidate_rows()
    if len(rows) != 795:
        raise ValueError("source universe must remain 795")

    prior = q1.prior_ids()
    gate = load_json(GATE1)
    newly_qualified = {str(x) for x in gate["qualified_inventory_ids"]}
    if len(prior) != 61 or len(newly_qualified) != 4 or prior & newly_qualified:
        raise ValueError("Wave 7 qualified baseline is inconsistent")
    qualified = prior | newly_qualified
    if len(qualified) != 65:
        raise ValueError("expected 65 machine-qualified P0 records")

    pending_p0 = [
        r for r in rows
        if r.get("priority") == "P0" and str(r["inventory_id"]) not in qualified
    ]
    pending_p0.sort(key=lambda r: str(r["inventory_id"]))
    if len(pending_p0) != 384:
        raise ValueError(f"expected 384 pending P0 records, found {len(pending_p0)}")

    batch1 = load_json(BATCH1)
    previous_touched = {
        str(x)
        for ids in batch1["lane_inventory_ids"].values()
        for x in ids
    }
    if len(previous_touched) != 16:
        raise ValueError("batch 001 touched-set must contain 16 unique identities")

    used = set(previous_touched)
    lanes: dict[str, list[dict[str, Any]]] = {}
    for lane, chooser in (
        ("A", q1.lane_a_candidates),
        ("B", q1.lane_b_candidates),
        ("C", q1.lane_c_candidates),
        ("D", q1.lane_d_candidates),
    ):
        selected = chooser(pending_p0, used)
        if len(selected) != BATCH_SIZE_PER_LANE:
            raise ValueError(f"lane {lane} could select only {len(selected)} records")
        ids = {str(r["inventory_id"]) for r in selected}
        if ids & used:
            raise ValueError(f"lane {lane} overlaps prior or current operation lease")
        used |= ids
        lanes[lane] = selected

    current_ids = {
        str(r["inventory_id"])
        for records in lanes.values()
        for r in records
    }
    if len(current_ids) != 16:
        raise ValueError("batch 002 must touch exactly 16 unique identities")
    if current_ids & previous_touched:
        raise ValueError("batch 002 must not repeat batch 001 identities")
    if current_ids & qualified:
        raise ValueError("batch 002 must not touch already-qualified identities")
    if any(r.get("flags") for r in lanes["A"]):
        raise ValueError("Lane A must contain zero candidate flags")
    if any(q1.is_high_risk(r) for r in lanes["A"]):
        raise ValueError("Lane A contains a high-risk semantic record")

    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "execution_id": "ct.docs.rebuild.wave7.quad-lane.batch-002",
        "source_universe_count": 795,
        "p0_candidate_estate": 449,
        "machine_qualified_before_batch": 65,
        "remaining_p0_before_batch": 384,
        "previous_batch_touched_count": 16,
        "previous_batch_touched_ids": sorted(previous_touched),
        "parallel_lane_count": 4,
        "records_per_lane": 4,
        "unique_records_touched": 16,
        "lanes": lanes,
        "counting": {
            "machine_qualified_delta": 0,
            "remaining_p0_delta": 0,
            "official_machine_qualified_after_batch": 65,
            "official_remaining_p0_after_batch": 384,
            "reason": "batch 002 produces governed work receipts only; qualification requires a dedicated acceptance gate",
        },
        "guardrails": {
            "batch_001_identity_reuse": False,
            "already_qualified_identity_reuse": False,
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
    payload["execution_sha256"] = q1.canonical_hash(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build()
    print("PASS_DOCS_REBUILD_QUAD_LANE_BATCH_002")
    print(f"execution_id={result['execution_id']}")
    for lane in ("A", "B", "C", "D"):
        print(f"lane_{lane}_inventory_ids=" + ",".join(r["inventory_id"] for r in result["lanes"][lane]))
    print("official_machine_qualified_after_batch=65")
    print("official_remaining_p0_after_batch=384")
    print("terminal_disposition_self_authorized=false")
    print("execution_sha256=" + result["execution_sha256"])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"output={args.output}")


if __name__ == "__main__":
    main()
