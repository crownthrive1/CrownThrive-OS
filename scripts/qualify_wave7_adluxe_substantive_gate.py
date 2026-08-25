#!/usr/bin/env python3
"""Dedicated substantive-successor gate for Wave 7 AdLuxe cohort 001.

This gate may machine-qualify only the exact four low-risk records previously
admitted to quad-lane Lane A. Qualification means that a current canonical
successor document contains enough specific, machine-verifiable substance to
cover the recovered article intent. It does not claim recovery of a historical
body and does not accept a terminal disposition.
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
import build_substantive_rebuild_wave6 as wave6

RECEIPT_PATH = ROOT / "developers/manifests/docs-rebuild-quad-lane-batch-001.v1.json"
CANONICAL_ROUTE = "/platforms/adluxe-network-institutional-registry"
EXPECTED_IDS = ["HC-0004", "HC-0010", "HC-0011", "HC-0014"]

INTENT_RULES: dict[str, dict[str, Any]] = {
    "HC-0004": {
        "intent": "platform_tour_and_navigation",
        "required_phrases": [
            "## Continuity map",
            "## Institutional identity",
            "## Operating roles and portals",
            "## Campaign lifecycle",
            "## Inventory architecture",
            "## API and MCP target contract",
        ],
    },
    "HC-0010": {
        "intent": "ad_creative_upload_and_specs",
        "required_phrases": [
            "creative production or upload",
            "creative upload and status",
            "Every creative must identify:",
            "metadata, dimensions, destinations, disclosures",
            "format, dimensions/duration",
        ],
    },
    "HC-0011": {
        "intent": "targeting_and_audience_segmentation",
        "required_phrases": [
            "## Targeting and privacy",
            "audience construction rule",
            "sensitive-data exclusion review",
            "suppression and opt-out rules",
            "minimum audience thresholds",
        ],
    },
    "HC-0014": {
        "intent": "crownthrive_ecosystem_placements",
        "required_phrases": [
            "## Inventory architecture",
            "CrownThrive-owned web placements",
            "Virality Music and Backroad FM sponsorship inventory",
            "KJV Visualized public-page placements where policy permits",
            "Locticians and beauty/wellness inventory",
            "event, ticketing, kiosk and screen placements",
        ],
    },
}


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def aggregate_by_id() -> dict[str, dict[str, Any]]:
    rows = wave1.aggregate_candidate_rows()
    return {str(r["inventory_id"]): r for r in rows}


def prior_ids() -> set[str]:
    _sets, union = wave6.prior_wave_sets()
    w6 = wave6.build()
    union = set(union)
    union.update(str(r["inventory_id"]) for r in w6["selected_records"])
    if len(union) != 61:
        raise ValueError(f"expected 61 prior qualified records, found {len(union)}")
    return union


def build() -> dict[str, Any]:
    receipt = load_json(RECEIPT_PATH)
    admitted = list(receipt["lane_inventory_ids"]["A"])
    if admitted != EXPECTED_IDS:
        raise ValueError(f"Lane A receipt drift: {admitted}")
    if not receipt["lane_a_quality"]["zero_candidate_flags"]:
        raise ValueError("Lane A receipt does not prove zero candidate flags")
    if receipt["official_counts_after_batch"]["machine_qualified_p0"] != 61:
        raise ValueError("unexpected pre-gate qualified count")

    rows = aggregate_by_id()
    qualified_before = prior_ids()
    if qualified_before & set(EXPECTED_IDS):
        raise ValueError("Wave 7 cohort overlaps prior qualified set")

    route_path = wave1.route_to_path(CANONICAL_ROUTE)
    route_text = route_path.read_text(encoding="utf-8")
    route_quality = wave1.route_quality(CANONICAL_ROUTE)
    if route_quality["body_characters"] < 20000:
        raise ValueError("canonical AdLuxe successor body is below substantive threshold")
    if route_quality["internal_link_count"] < 4:
        raise ValueError("canonical AdLuxe successor continuity is below threshold")

    results: list[dict[str, Any]] = []
    selected: list[str] = []
    for inventory_id in EXPECTED_IDS:
        row = rows[inventory_id]
        reasons: list[str] = []
        flags = list(row.get("flags", []))
        if row.get("priority") != "P0":
            reasons.append("not_p0")
        if row.get("disposition_candidate") != "merged_successor":
            reasons.append("not_merged_successor_candidate")
        if flags:
            reasons.append("candidate_flags_not_empty")
        if row.get("missing_target_routes"):
            reasons.append("missing_target_routes")
        if CANONICAL_ROUTE not in row.get("target_routes", []):
            reasons.append("canonical_adluxe_route_not_mapped")

        rule = INTENT_RULES[inventory_id]
        phrase_checks = {p: (p.casefold() in route_text.casefold()) for p in rule["required_phrases"]}
        missing_phrases = [p for p, ok in phrase_checks.items() if not ok]
        if missing_phrases:
            reasons.append("substantive_intent_evidence_incomplete")

        accepted = not reasons
        if accepted:
            selected.append(inventory_id)
        results.append({
            "inventory_id": inventory_id,
            "article_id": row.get("article_id"),
            "legacy_title": row.get("legacy_title"),
            "intent": rule["intent"],
            "canonical_successor_route": CANONICAL_ROUTE,
            "candidate_flags": flags,
            "phrase_checks": phrase_checks,
            "missing_required_phrases": missing_phrases,
            "machine_substantive_qualified": accepted,
            "qualification_state": "QUALIFIED_CURRENT_SUCCESSOR" if accepted else "HELD",
            "hold_reasons": sorted(set(reasons)),
            "historical_body_recovered": False,
            "terminal_disposition_accepted": False,
            "parent_review_required_for_terminal_disposition": True,
        })

    expected_selected = set(EXPECTED_IDS)
    if set(selected) != expected_selected:
        raise ValueError(f"dedicated substantive gate held records: {sorted(expected_selected - set(selected))}")

    qualified_after = 61 + len(selected)
    remaining_after = 388 - len(selected)
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "gate_id": "ct.docs.rebuild.wave7.adluxe-substantive-gate-001.v1",
        "source_execution_receipt": RECEIPT_PATH.relative_to(ROOT).as_posix(),
        "canonical_successor_route": CANONICAL_ROUTE,
        "canonical_successor_quality": route_quality,
        "records_evaluated": len(EXPECTED_IDS),
        "records_machine_qualified": len(selected),
        "qualified_inventory_ids": selected,
        "results": results,
        "counting": {
            "machine_qualified_before": 61,
            "pending_p0_before": 388,
            "machine_qualified_delta": len(selected),
            "pending_p0_delta": -len(selected),
            "machine_qualified_after": qualified_after,
            "pending_p0_after": remaining_after,
        },
        "guardrails": {
            "exact_lane_a_identity_required": True,
            "zero_candidate_flags_required": True,
            "current_successor_substance_required": True,
            "historical_body_recovery_claimed": False,
            "terminal_disposition_self_authorized": False,
            "authority_activation_created": False,
            "provider_write_expansion_created": False,
            "phase_3_entry": "blocked_pending_phase_2_99_hard_exit",
        },
    }
    payload["gate_sha256"] = canonical_hash(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build()
    print("PASS_WAVE7_ADLUXE_SUBSTANTIVE_GATE")
    print("qualified_inventory_ids=" + ",".join(result["qualified_inventory_ids"]))
    print(f"records_machine_qualified={result['records_machine_qualified']}")
    print(f"machine_qualified_after={result['counting']['machine_qualified_after']}")
    print(f"pending_p0_after={result['counting']['pending_p0_after']}")
    print("historical_body_recovery_claimed=false")
    print("terminal_disposition_self_authorized=false")
    print("gate_sha256=" + result["gate_sha256"])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"output={args.output}")


if __name__ == "__main__":
    main()
