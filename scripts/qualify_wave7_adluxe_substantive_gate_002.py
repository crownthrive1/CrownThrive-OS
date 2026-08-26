#!/usr/bin/env python3
"""Dedicated substantive-successor gate for Wave 7 AdLuxe cohort 002.

This gate may machine-qualify only the exact four low-risk records admitted to
quad-lane Batch 002 Lane A. Qualification proves that the current canonical
AdLuxe successor contains article-specific, machine-verifiable substance. It
never claims recovery of the missing historical article body and never accepts
a terminal disposition, provider write authority, economic authority, or
Phase 3 entry.
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

BATCH_RECEIPT = ROOT / "developers/manifests/docs-rebuild-quad-lane-batch-002.v1.json"
PRIOR_GATE_RECEIPT = ROOT / "developers/manifests/docs-wave7-adluxe-substantive-gate-001.v1.json"
CANONICAL_ROUTE = "/platforms/adluxe-network-institutional-registry"
EXPECTED_IDS = ["HC-0020", "HC-0021", "HC-0022", "HC-0023"]

INTENT_RULES: dict[str, dict[str, Any]] = {
    "HC-0020": {
        "intent": "premium_placement_packages",
        "required_phrases": [
            "## Inventory architecture",
            "custom branded-content and integrated-campaign packages",
            "## Pricing and commercial models",
            "inventory/package commercial eligibility",
            "canonical service/SKU identities",
            "minimums, caps and overage rules",
        ],
    },
    "HC-0021": {
        "intent": "ad_space_value_viewability_layout_ux",
        "required_phrases": [
            "requested, served and viewable impressions where supported",
            "fill rate and no-fill",
            "format, dimensions/duration, surface, audience context",
            "inventory quality and measured performance",
            "accepted inventory and placement policies",
        ],
    },
    "HC-0022": {
        "intent": "delivery_and_traffic_quality",
        "required_phrases": [
            "delivery and anomaly monitoring",
            "invalid or filtered traffic",
            "fill rate and no-fill",
            "traffic-quality review",
            "incidents, missed delivery and make-goods",
        ],
    },
    "HC-0023": {
        "intent": "monetization_and_affiliates",
        "required_phrases": [
            "Crown Affiliates",
            "commissions and payouts",
            "commission and publisher-share rules",
            "required sponsorship/affiliate/AI disclosures",
            "creator/UGC/influencer deliverables through CrownFluence",
        ],
    },
}


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def aggregate_by_id() -> dict[str, dict[str, Any]]:
    return {str(r["inventory_id"]): r for r in wave1.aggregate_candidate_rows()}


def waves_1_6_ids() -> set[str]:
    _sets, union = wave6.prior_wave_sets()
    w6 = wave6.build()
    union = set(union)
    union.update(str(r["inventory_id"]) for r in w6["selected_records"])
    if len(union) != 61:
        raise ValueError(f"expected 61 Waves 1-6 qualified records, found {len(union)}")
    return union


def prior_qualified_ids() -> set[str]:
    prior = waves_1_6_ids()
    gate1 = load_json(PRIOR_GATE_RECEIPT)
    if gate1["official_counts_after_gate"] != {"machine_qualified_p0": 65, "pending_p0": 384}:
        raise ValueError("prior Wave 7 gate receipt count drift")
    prior.update(str(x) for x in gate1["qualified_inventory_ids"])
    if len(prior) != 65:
        raise ValueError(f"expected 65 qualified identities before gate 002, found {len(prior)}")
    return prior


def build() -> dict[str, Any]:
    batch = load_json(BATCH_RECEIPT)
    admitted = list(batch["lane_inventory_ids"]["A"])
    if admitted != EXPECTED_IDS:
        raise ValueError(f"Batch 002 Lane A receipt drift: {admitted}")
    if batch["official_counts_after_batch"] != {"machine_qualified_p0": 65, "pending_p0": 384}:
        raise ValueError("unexpected Batch 002 baseline")
    if not batch["guardrails"]["lane_a_requires_zero_flags"]:
        raise ValueError("Batch 002 does not preserve Lane A zero-flag invariant")
    if not batch["guardrails"]["lane_a_high_risk_semantics_prohibited"]:
        raise ValueError("Batch 002 does not preserve Lane A risk invariant")

    rows = aggregate_by_id()
    qualified_before = prior_qualified_ids()
    if qualified_before & set(EXPECTED_IDS):
        raise ValueError("cohort 002 overlaps already-qualified identities")

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
        if row.get("legacy_subcategory") != "AdLuxe Network":
            reasons.append("not_adluxe_network")
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

    expected = set(EXPECTED_IDS)
    if set(selected) != expected:
        raise ValueError(f"dedicated substantive gate held records: {sorted(expected - set(selected))}")

    qualified_after = 65 + len(selected)
    remaining_after = 384 - len(selected)
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "gate_id": "ct.docs.rebuild.wave7.adluxe-substantive-gate-002.v1",
        "source_execution_receipt": BATCH_RECEIPT.relative_to(ROOT).as_posix(),
        "prior_qualification_receipt": PRIOR_GATE_RECEIPT.relative_to(ROOT).as_posix(),
        "canonical_successor_route": CANONICAL_ROUTE,
        "canonical_successor_quality": route_quality,
        "records_evaluated": len(EXPECTED_IDS),
        "records_machine_qualified": len(selected),
        "qualified_inventory_ids": selected,
        "results": results,
        "counting": {
            "machine_qualified_before": 65,
            "pending_p0_before": 384,
            "machine_qualified_delta": len(selected),
            "pending_p0_delta": -len(selected),
            "machine_qualified_after": qualified_after,
            "pending_p0_after": remaining_after,
        },
        "guardrails": {
            "exact_batch_002_lane_a_identity_required": True,
            "zero_candidate_flags_required": True,
            "high_risk_semantics_prohibited": True,
            "current_successor_substance_required": True,
            "article_specific_phrase_evidence_required": True,
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
    print("PASS_WAVE7_ADLUXE_SUBSTANTIVE_GATE_002")
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
