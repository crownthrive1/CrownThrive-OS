#!/usr/bin/env python3
"""Build Sprint 11 substantive-rebuild Wave 5.

Sprint 11 first tests the proposed P0 interface-surface lane under the unchanged
D2 admission gate. That primary lane has five remaining P0 candidates and zero
admissions. The gate is not weakened. The builder then pivots to the single
low-risk CrownThrive IO surface/machine-contract candidate identified by the
bounded remaining-P0 diagnostic. Historical bodies remain missing and terminal
dispositions remain pending parent certification.
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
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_substantive_rebuild_wave1 as wave1
import build_substantive_rebuild_wave2 as wave2
import build_substantive_rebuild_wave3 as wave3
import build_substantive_rebuild_wave4 as wave4

POLICY_PATH = ROOT / "data/documentation/substantive-rebuild-wave-5-policy.v1.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def text_has_any(text: str, terms: list[str]) -> bool:
    low = text.casefold()
    return any(term.casefold() in low for term in terms)


def prior_wave_sets() -> tuple[list[set[str]], set[str]]:
    built = [wave1.build(), wave2.build(), wave3.build(), wave4.build()]
    sets = [{str(row["inventory_id"]) for row in result["selected_records"]} for result in built]
    for i, left in enumerate(sets):
        for right in sets[i + 1:]:
            if left & right:
                raise ValueError("prior substantive waves overlap")
    return sets, set().union(*sets)


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
        "target_routes": list(row.get("target_routes", [])),
    }


def primary_interface_probe(
    rows: list[dict[str, Any]], policy: dict[str, Any], prior_ids: set[str]
) -> dict[str, Any]:
    lane = policy["primary_lane"]
    state = lane["state_family"]
    candidate_rows = [
        row for row in rows
        if row.get("priority") == policy["required_priority"]
        and str(row["inventory_id"]) not in prior_ids
        and row.get("current_state_candidate") == state
    ]

    admitted: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    for row in candidate_rows:
        reasons: list[str] = []
        title = str(row.get("legacy_title", ""))
        flags = " ".join(str(x) for x in row.get("flags", []))
        target_routes = list(row.get("target_routes", []))
        continuity = sorted(set(target_routes) & set(lane["continuity_requirements"]))

        if row.get("disposition_candidate") != policy["required_candidate_disposition"]:
            reasons.append("candidate_disposition_not_merged_successor")
        if row.get("missing_target_routes"):
            reasons.append("missing_target_route")
        if not text_has_any(title, lane["required_title_any_terms"]):
            reasons.append("interface_surface_term_not_present")
        if text_has_any(title, lane["blocked_title_terms"]):
            reasons.append("d3_or_high_risk_title_term")
        if text_has_any(flags, lane["blocked_flag_terms"]):
            reasons.append("explicit_high_risk_flag")
        if not continuity:
            reasons.append("no_state_continuity_match")

        record = {
            **base_record(row),
            "continuity_matches": continuity,
            "probe_state": "admitted" if not reasons else "held",
            "hold_reasons": sorted(set(reasons)),
        }
        (admitted if not reasons else held).append(record)

    probe_payload = {
        "lane": "primary_interface_surface",
        "candidate_count": len(candidate_rows),
        "selected_count": len(admitted),
        "held_count": len(held),
        "gate_unchanged": True,
        "expected_result": lane["expected_result"],
        "admitted_inventory_ids": sorted(row["inventory_id"] for row in admitted),
        "held_records": held,
    }
    canonical = json.dumps(probe_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    probe_payload["probe_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return probe_payload


def classify_pivot(
    row: dict[str, Any], policy: dict[str, Any], prior_ids: set[str]
) -> tuple[str, dict[str, Any]]:
    lane = policy["pivot_lane"]
    reasons: list[str] = []
    inventory_id = str(row["inventory_id"])
    flags = " ".join(str(x) for x in row.get("flags", []))
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
        reasons.append("outside_pivot_state_family")
    if row.get("legacy_section") != lane["legacy_section"]:
        reasons.append("outside_pivot_section")
    if row.get("legacy_subcategory") != lane["legacy_subcategory"]:
        reasons.append("outside_pivot_subcategory")
    if str(row.get("legacy_title", "")) != lane["required_title_exact"]:
        reasons.append("outside_exact_pivot_title")
    if text_has_any(flags, lane["blocked_flag_terms"]):
        reasons.append("explicit_high_risk_flag")
    if not continuity:
        reasons.append("no_pivot_continuity_match")

    anchor_quality: dict[str, Any] | None = None
    if not reasons or (
        row.get("current_state_candidate") == lane["state_family"]
        and str(row.get("legacy_title", "")) == lane["required_title_exact"]
    ):
        try:
            anchor_quality = wave1.route_quality(lane["anchor_route"])
        except FileNotFoundError:
            reasons.append("substantive_anchor_missing")
        else:
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

    primary_probe = primary_interface_probe(rows, policy, prior_ids)

    selected: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    for row in rows:
        result_state, record = classify_pivot(row, policy, prior_ids)
        (selected if result_state == "selected" else held).append(record)

    selected_ids = {row["inventory_id"] for row in selected}
    if selected_ids & prior_ids:
        raise ValueError("Wave 5 pivot overlaps prior waves")

    p0_total = sum(1 for row in rows if row.get("priority") == "P0")
    selected_sections = Counter(row["legacy_section"] for row in selected)
    selected_states = Counter(row["current_state_candidate"] for row in selected)
    selected_anchors = Counter(row["canonical_anchor_route"] for row in selected)
    hold_reasons = Counter(reason for row in held for reason in row["hold_reasons"])
    cumulative_selected = len(prior_ids) + len(selected)

    payload = {
        "schema_version": "1.1.0",
        "wave_id": "ct.docs.substantive-rebuild.wave-5.v1",
        "sprint": 11,
        "pass": "A_interface_zero_admission_then_B_crownthrive_io_surface_machine_contract_pivot",
        "source_universe_count": 795,
        "p0_candidate_count": p0_total,
        "wave_1_selected_count": len(prior_sets[0]),
        "wave_2_selected_count": len(prior_sets[1]),
        "wave_3_selected_count": len(prior_sets[2]),
        "wave_4_selected_count": len(prior_sets[3]),
        "prior_wave_selected_count": len(prior_ids),
        "primary_interface_p0_candidate_count": primary_probe["candidate_count"],
        "primary_interface_selected_count": primary_probe["selected_count"],
        "primary_interface_zero_admission": primary_probe["selected_count"] == 0,
        "primary_interface_gate_unchanged": True,
        "primary_interface_probe_sha256": primary_probe["probe_sha256"],
        "classification_collision_inspection": {
            "ai_agent_algorithm_p0_candidate_count": 35,
            "broad_ai_family_qualified": False,
            "reason": policy["classification_collision_note"],
        },
        "pivot_state_family": policy["pivot_lane"]["state_family"],
        "pivot_inventory_id": "HC-0076",
        "selected_count": len(selected),
        "held_count": len(held),
        "cumulative_machine_qualified_p0_count": cumulative_selected,
        "p0_outside_waves_1_2_3_4_5_count": p0_total - cumulative_selected,
        "prior_wave_overlap_count": 0,
        "selected_section_counts": dict(sorted(selected_sections.items())),
        "selected_state_counts": dict(sorted(selected_states.items())),
        "selected_anchor_counts": dict(sorted(selected_anchors.items())),
        "hold_reason_counts": dict(sorted(hold_reasons.items())),
        "policy": policy,
        "primary_interface_probe": primary_probe,
        "selected_records": selected,
        "held_records": held,
        "guardrails": {
            "historical_body_recovery_claimed": False,
            "terminal_disposition_self_authorized": False,
            "parent_certification_required": True,
            "d3_human_reserved": True,
            "interface_gate_weakened": False,
            "ai_collision_family_broadly_qualified": False,
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
            "canonical_brand": "CrownThrive",
        },
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
    print("PASS_SUBSTANTIVE_REBUILD_WAVE5_BUILD")
    print(f"source_universe_count={result['source_universe_count']}")
    print(f"p0_candidate_count={result['p0_candidate_count']}")
    print(f"prior_wave_selected_count={result['prior_wave_selected_count']}")
    print(f"primary_interface_p0_candidate_count={result['primary_interface_p0_candidate_count']}")
    print(f"primary_interface_selected_count={result['primary_interface_selected_count']}")
    print(f"primary_interface_zero_admission={str(result['primary_interface_zero_admission']).lower()}")
    print(f"selected_count={result['selected_count']}")
    print(f"cumulative_machine_qualified_p0_count={result['cumulative_machine_qualified_p0_count']}")
    print(f"p0_outside_waves_1_2_3_4_5_count={result['p0_outside_waves_1_2_3_4_5_count']}")
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
