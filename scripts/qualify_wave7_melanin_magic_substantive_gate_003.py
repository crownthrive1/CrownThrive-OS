#!/usr/bin/env python3
"""Dedicated substantive-current-successor gate for Wave 7 cohort 003.

This gate may machine-qualify only the exact four zero-flag Lane A records from
Batch 003. Qualification proves sufficient current canonical successor substance
for the recovered intent. It does not claim recovery of a historical article
body, accept terminal disposition, or create new legal/economic/provider authority.
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
import execute_docs_rebuild_quad_lane_batch as q1

RECEIPT_PATH = ROOT / "developers/manifests/docs-rebuild-quad-lane-batch-003.v1.json"
GATE1 = ROOT / "developers/manifests/docs-wave7-adluxe-substantive-gate-001.v1.json"
GATE2 = ROOT / "developers/manifests/docs-wave7-adluxe-substantive-gate-002.v1.json"
CANONICAL_ROUTE = "/platforms/melanin-magic-institutional-registry"
EXPECTED_IDS = ["HC-0104", "HC-0109", "HC-0110", "HC-0112"]

INTENT_RULES: dict[str, dict[str, Any]] = {
    "HC-0104": {
        "intent": "stylist_certification_curriculum",
        "required_phrases": [
            "Stylist Certification Curriculum",
            "Professional / Stylepreneur",
            "CrownThriveU — product/professional education and credentials",
            "content/education reviewer",
            "education/resources",
        ],
    },
    "HC-0109": {
        "intent": "wholesale_brand_master_guide",
        "required_phrases": [
            "Melanin Magic Wholesale — Brand Master Guide",
            "Melanin Magic must be governed as a product/brand system",
            "Consumer, professional and wholesale separation",
            "Wholesale access does not transfer trademarks",
            "digital/brand/product marketplace",
        ],
    },
    "HC-0110": {
        "intent": "wholesale_program",
        "required_phrases": [
            "Wholesale Program",
            "Business verification, terms, approved SKUs",
            "pricing schedule",
            "order/fulfillment",
            "tax/resale documentation",
        ],
    },
    "HC-0112": {
        "intent": "authorized_retailer_guide",
        "required_phrases": [
            "Wholesale Authorized Retailer Guide",
            "resale permissions",
            "territory/channel rules",
            "marketing standards",
            "suspension/revocation",
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


def prior_qualified_ids() -> set[str]:
    prior = q1.prior_ids()
    g1 = load_json(GATE1)
    g2 = load_json(GATE2)
    ids = set(prior)
    ids.update(str(x) for x in g1["qualified_inventory_ids"])
    ids.update(str(x) for x in g2["qualified_inventory_ids"])
    if len(ids) != 69:
        raise ValueError(f"expected 69 prior qualified records, found {len(ids)}")
    return ids


def build() -> dict[str, Any]:
    receipt = load_json(RECEIPT_PATH)
    admitted = list(receipt["lane_inventory_ids"]["A"])
    if admitted != EXPECTED_IDS:
        raise ValueError(f"Lane A receipt drift: {admitted}")
    if receipt["official_counts_after_batch"] != {"machine_qualified_p0": 69, "pending_p0": 380}:
        raise ValueError("unexpected Batch 003 baseline")
    if not receipt["guardrails"]["lane_a_requires_zero_flags"]:
        raise ValueError("Batch 003 receipt does not enforce zero-flag Lane A")

    rows = aggregate_by_id()
    qualified_before = prior_qualified_ids()
    if qualified_before & set(EXPECTED_IDS):
        raise ValueError("Gate 003 cohort overlaps prior qualified records")

    route_path = wave1.route_to_path(CANONICAL_ROUTE)
    route_text = route_path.read_text(encoding="utf-8")
    route_quality = wave1.route_quality(CANONICAL_ROUTE)
    if route_quality["body_characters"] < 12000:
        raise ValueError("canonical Melanin Magic successor body is below substantive threshold")
    if route_quality["internal_link_count"] < 4:
        raise ValueError("canonical Melanin Magic successor continuity is below threshold")

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
            reasons.append("canonical_melanin_magic_route_not_mapped")

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

    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "gate_id": "ct.docs.rebuild.wave7.melanin-magic-substantive-gate-003.v1",
        "source_execution_receipt": RECEIPT_PATH.relative_to(ROOT).as_posix(),
        "canonical_successor_route": CANONICAL_ROUTE,
        "canonical_successor_quality": route_quality,
        "records_evaluated": len(EXPECTED_IDS),
        "records_machine_qualified": len(selected),
        "qualified_inventory_ids": selected,
        "results": results,
        "counting": {
            "machine_qualified_before": 69,
            "pending_p0_before": 380,
            "machine_qualified_delta": len(selected),
            "pending_p0_delta": -len(selected),
            "machine_qualified_after": 69 + len(selected),
            "pending_p0_after": 380 - len(selected),
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
    print("PASS_WAVE7_MELANIN_MAGIC_SUBSTANTIVE_GATE_003")
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
