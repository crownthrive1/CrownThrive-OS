#!/usr/bin/env python3
"""Build Sprint 12 substantive-rebuild Wave 6.

Pass A performs non-terminal classification hygiene for the 35-row P0
AI/agent/algorithm collision family and intentionally admits zero rows from that
mixed family. Pass B then qualifies only the three bounded CIE imprint-framework
records identified by the prior low-risk diagnostic through a dedicated current
successor contract. Historical bodies and terminal dispositions remain pending.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave1 as wave1
import build_substantive_rebuild_wave2 as wave2
import build_substantive_rebuild_wave3 as wave3
import build_substantive_rebuild_wave4 as wave4
import build_substantive_rebuild_wave5 as wave5
import inspect_sprint_12_ai_collision_hygiene as ai_hygiene

POLICY_PATH = ROOT / "data/documentation/substantive-rebuild-wave-6-policy.v1.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def prior_wave_sets() -> tuple[list[set[str]], set[str]]:
    built = [wave1.build(), wave2.build(), wave3.build(), wave4.build(), wave5.build()]
    sets = [{str(row["inventory_id"]) for row in result["selected_records"]} for result in built]
    union: set[str] = set()
    for current in sets:
        if union & current:
            raise ValueError("prior substantive waves overlap")
        union |= current
    return sets, union


def base_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "inventory_id": str(row["inventory_id"]),
        "article_id": row["article_id"],
        "legacy_section": row["legacy_section"],
        "legacy_subcategory": row["legacy_subcategory"],
        "legacy_title": str(row.get("legacy_title", "")),
        "priority": row.get("priority"),
        "candidate_disposition": row.get("disposition_candidate"),
        "current_state_candidate": str(row.get("current_state_candidate", "")),
        "flags": list(row.get("flags", [])),
        "target_routes": list(row.get("target_routes", [])),
    }


def classify_pivot(row: dict[str, Any], policy: dict[str, Any], prior_ids: set[str]) -> tuple[str, dict[str, Any]]:
    lane = policy["pivot_lane"]
    reasons: list[str] = []
    inventory_id = str(row["inventory_id"])
    flags = {str(x) for x in row.get("flags", [])}
    target_routes = list(row.get("target_routes", []))
    continuity = sorted(set(target_routes) & set(lane["continuity_requirements"]))

    if inventory_id in prior_ids:
        reasons.append("already_selected_prior_wave")
    if row.get("priority") != policy["required_priority"]:
        reasons.append("not_p0")
    if row.get("disposition_candidate") != policy["required_candidate_disposition"]:
        reasons.append("candidate_disposition_not_merged_successor")
    if row.get("missing_target_routes"):
        reasons.append("missing_target_route")
    if row.get("current_state_candidate") != lane["state_family"]:
        reasons.append("outside_cie_framework_state_family")
    if row.get("legacy_section") != lane["legacy_section"]:
        reasons.append("outside_cie_section")
    if row.get("legacy_subcategory") != lane["legacy_subcategory"]:
        reasons.append("outside_cie_imprint_framework_subcategory")
    if inventory_id not in set(lane["required_inventory_ids"]):
        reasons.append("outside_exact_bounded_inventory_set")
    if any(blocked in flags for blocked in lane["blocked_flag_terms"]):
        reasons.append("explicit_high_risk_flag")
    if flags - set(lane["allowed_flags"]):
        reasons.append("unexpected_flag_outside_bounded_cie_lane")
    if not continuity:
        reasons.append("no_cie_framework_continuity_match")

    anchor_quality: dict[str, Any] | None = None
    if inventory_id in set(lane["required_inventory_ids"]):
        try:
            anchor_quality = wave1.route_quality(lane["anchor_route"])
        except FileNotFoundError:
            reasons.append("substantive_anchor_missing")
        else:
            if not anchor_quality["editorial_current_successor_eligible"]:
                reasons.append("substantive_anchor_not_current_editorial_state")
            if anchor_quality["body_characters"] < int(policy["minimum_anchor_body_characters"]):
                reasons.append("substantive_anchor_body_too_small")
            if anchor_quality["internal_link_count"] < int(policy["minimum_anchor_internal_links"]):
                reasons.append("substantive_anchor_continuity_too_weak")

    base = base_record(row)
    if reasons:
        return "held", {
            **base,
            "hold_reasons": sorted(set(reasons)),
            "continuity_matches": continuity,
            "anchor_quality_checked": anchor_quality,
        }

    assert anchor_quality is not None
    return "selected", {
        **base,
        "candidate_cohort": row["candidate_cohort"],
        "canonical_anchor_route": lane["anchor_route"],
        "canonical_anchor_quality": anchor_quality,
        "continuity_routes": target_routes,
        "continuity_matches": continuity,
        "historical_body_status": row.get("body_status", "reconstruction_required"),
        "substantive_current_successor_body": "present_and_machine_qualified",
        "machine_acceptance_state": policy["machine_acceptance_state"],
        "terminal_disposition_accepted": False,
        "parent_certification_required": True,
        "authority_ceiling": policy["authority_ceiling"],
    }


def build() -> dict[str, Any]:
    policy = load_json(POLICY_PATH)
    rows = wave1.aggregate_candidate_rows()
    prior_sets, prior_ids = prior_wave_sets()
    overlay = ai_hygiene.build_overlay(rows, prior_ids)

    selected: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    for row in rows:
        state, record = classify_pivot(row, policy, prior_ids)
        (selected if state == "selected" else held).append(record)

    selected_ids = {row["inventory_id"] for row in selected}
    if selected_ids & prior_ids:
        raise ValueError("Wave 6 overlaps prior waves")

    expected_ids = set(policy["pivot_lane"]["required_inventory_ids"])
    p0_total = sum(1 for row in rows if row.get("priority") == "P0")
    selected_sections = Counter(row["legacy_section"] for row in selected)
    selected_states = Counter(row["current_state_candidate"] for row in selected)
    selected_anchors = Counter(row["canonical_anchor_route"] for row in selected)
    hold_reasons = Counter(reason for row in held for reason in row["hold_reasons"])
    cumulative_selected = len(prior_ids) + len(selected)

    payload = {
        "schema_version": "1.0.0",
        "selection_view": wave1.current_selection_view(6),
        "wave_id": "ct.docs.substantive-rebuild.wave-6.v1",
        "sprint": 12,
        "pass": "A_ai_collision_hygiene_zero_admission_then_B_cie_framework_pivot",
        "source_universe_count": 795,
        "p0_candidate_count": p0_total,
        "wave_1_selected_count": len(prior_sets[0]),
        "wave_2_selected_count": len(prior_sets[1]),
        "wave_3_selected_count": len(prior_sets[2]),
        "wave_4_selected_count": len(prior_sets[3]),
        "wave_5_selected_count": len(prior_sets[4]),
        "prior_wave_selected_count": len(prior_ids),
        "ai_collision_candidate_count": overlay["candidate_count"],
        "ai_collision_machine_admission_count": overlay["machine_admission_count"],
        "ai_collision_primary_hold_lane_counts": overlay["primary_hold_lane_counts"],
        "ai_collision_overlay_sha256": overlay["overlay_sha256"],
        "ai_collision_historical_crosswalk_rewritten": overlay["historical_sprint_4_crosswalk_rewritten"],
        "pivot_state_family": policy["pivot_lane"]["state_family"],
        "pivot_expected_inventory_ids": sorted(expected_ids),
        "selected_count": len(selected),
        "held_count": len(held),
        "cumulative_machine_qualified_p0_count": cumulative_selected,
        "p0_outside_waves_1_2_3_4_5_6_count": p0_total - cumulative_selected,
        "prior_wave_overlap_count": 0,
        "selected_section_counts": dict(sorted(selected_sections.items())),
        "selected_state_counts": dict(sorted(selected_states.items())),
        "selected_anchor_counts": dict(sorted(selected_anchors.items())),
        "hold_reason_counts": dict(sorted(hold_reasons.items())),
        "policy": policy,
        "ai_collision_overlay": overlay,
        "selected_records": selected,
        "held_records": held,
        "editorial_current_successor_exclusions": wave1.editorial_exclusion_report(held),
        "guardrails": {
            "historical_body_recovery_claimed": False,
            "terminal_disposition_self_authorized": False,
            "parent_certification_required": True,
            "d3_human_reserved": True,
            "ai_collision_family_broadly_qualified": False,
            "ai_collision_historical_crosswalk_rewritten": False,
            "legal_policy_activation_created": False,
            "investment_or_securities_authority_created": False,
            "patent_status_authority_created": False,
            "franchise_or_license_activation_created": False,
            "rights_or_economic_activation_created": False,
            "identity_or_credential_activation_created": False,
            "evidence_or_attestation_authority_created": False,
            "provider_write_expansion_created": False,
            "interface_runtime_activation_created": False,
            "token_exchange_or_settlement_authority_created": False,
            "production_activation_created": False,
            "phase_3_entry": "blocked_pending_phase_2_99_hard_exit",
            "phase_11_20_state": "reserved_definition_required",
            "canonical_brand": "CrownThrive"
        }
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["wave_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    result = build()
    print("PASS_SUBSTANTIVE_REBUILD_WAVE6_BUILD")
    print(f"source_universe_count={result['source_universe_count']}")
    print(f"p0_candidate_count={result['p0_candidate_count']}")
    print(f"prior_wave_selected_count={result['prior_wave_selected_count']}")
    print(f"ai_collision_candidate_count={result['ai_collision_candidate_count']}")
    print(f"ai_collision_machine_admission_count={result['ai_collision_machine_admission_count']}")
    print("ai_collision_primary_hold_lane_counts=" + json.dumps(result["ai_collision_primary_hold_lane_counts"], sort_keys=True))
    print("ai_collision_overlay_sha256=" + result["ai_collision_overlay_sha256"])
    print(f"selected_count={result['selected_count']}")
    print(f"cumulative_machine_qualified_p0_count={result['cumulative_machine_qualified_p0_count']}")
    print(f"p0_outside_waves_1_2_3_4_5_6_count={result['p0_outside_waves_1_2_3_4_5_6_count']}")
    print("selected_section_counts=" + json.dumps(result["selected_section_counts"], sort_keys=True))
    print("selected_state_counts=" + json.dumps(result["selected_state_counts"], sort_keys=True))
    print("selected_anchor_counts=" + json.dumps(result["selected_anchor_counts"], sort_keys=True))
    print("wave_sha256=" + result["wave_sha256"])
    print("terminal_disposition_self_authorized=false")
    print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"output={args.output}")
    elif not args.summary_only:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
