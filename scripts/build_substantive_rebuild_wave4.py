#!/usr/bin/env python3
"""Build Sprint 10 substantive-rebuild Wave 4.

Wave 4 preserves the completed 795-title candidate map and exact Waves 1-3.
It admits only P0 component/framework rows whose P0 status is also supported by
machine-contract terminology and whose current successor is a substantive,
public-safe component reconciliation contract. High-risk authority, rights,
economic, identity, evidence, legal, restricted and secret-bearing material is
held outside this D2 lane.
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

POLICY_PATH = ROOT / "data/documentation/substantive-rebuild-wave-4-policy.v1.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def text_has_any(text: str, terms: list[str]) -> bool:
    low = text.casefold()
    return any(term.casefold() in low for term in terms)


def classify(row: dict[str, Any], policy: dict[str, Any], prior_ids: set[str]) -> tuple[str, dict[str, Any]]:
    reasons: list[str] = []
    inventory_id = str(row["inventory_id"])
    title = str(row.get("legacy_title", ""))
    state = str(row.get("current_state_candidate", ""))
    flags = " ".join(str(x) for x in row.get("flags", []))
    target_routes = list(row.get("target_routes", []))

    if inventory_id in prior_ids:
        reasons.append("already_selected_prior_wave")
    if row.get("priority") != policy["required_priority"]:
        reasons.append("not_p0")
    if row.get("disposition_candidate") != policy["required_candidate_disposition"]:
        reasons.append("candidate_disposition_not_merged_successor")
    if row.get("missing_target_routes"):
        reasons.append("missing_target_route")
    if state not in set(policy["allowed_state_families"]):
        reasons.append("outside_wave_4_state_family")
    if state in set(policy["allowed_state_families"]) and not text_has_any(title, policy["required_title_any_terms"]):
        reasons.append("component_p0_not_machine_contract_derived")
    if text_has_any(title, policy["blocked_title_terms"]):
        reasons.append("d3_or_high_risk_title_term")
    if text_has_any(state, policy["blocked_state_terms"]):
        reasons.append("d3_or_high_risk_state")
    if text_has_any(flags, policy["blocked_flag_terms"]):
        reasons.append("explicit_high_risk_flag")

    anchor_route = policy.get("state_anchor_routes", {}).get(state)
    continuity_required = list(policy.get("state_continuity_requirements", {}).get(state, []))
    continuity_matches = sorted(set(target_routes) & set(continuity_required))
    if state in set(policy["allowed_state_families"]) and not continuity_matches:
        reasons.append("no_state_continuity_match")

    anchor_quality: dict[str, Any] | None = None
    if anchor_route:
        try:
            anchor_quality = wave1.route_quality(anchor_route)
        except FileNotFoundError:
            reasons.append("substantive_anchor_missing")
        else:
            if anchor_quality["body_characters"] < int(policy["minimum_anchor_body_characters"]):
                reasons.append("substantive_anchor_body_too_small")
            if anchor_quality["internal_link_count"] < int(policy["minimum_anchor_internal_links"]):
                reasons.append("substantive_anchor_continuity_too_weak")
    elif state in set(policy["allowed_state_families"]):
        reasons.append("substantive_anchor_not_defined")

    base = {
        "inventory_id": inventory_id,
        "article_id": row["article_id"],
        "legacy_section": row["legacy_section"],
        "legacy_subcategory": row["legacy_subcategory"],
        "legacy_title": title,
        "priority": row.get("priority"),
        "candidate_disposition": row.get("disposition_candidate"),
        "current_state_candidate": state,
        "target_routes": target_routes,
    }

    if reasons:
        return "held", {
            **base,
            "hold_reasons": sorted(set(reasons)),
            "continuity_matches": continuity_matches,
            "anchor_quality_checked": anchor_quality,
        }

    assert anchor_route is not None and anchor_quality is not None
    return "selected", {
        **base,
        "candidate_cohort": row["candidate_cohort"],
        "canonical_anchor_route": anchor_route,
        "canonical_anchor_quality": anchor_quality,
        "continuity_routes": target_routes,
        "continuity_matches": continuity_matches,
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
    first = wave1.build()
    second = wave2.build()
    third = wave3.build()

    wave1_ids = {str(row["inventory_id"]) for row in first["selected_records"]}
    wave2_ids = {str(row["inventory_id"]) for row in second["selected_records"]}
    wave3_ids = {str(row["inventory_id"]) for row in third["selected_records"]}
    if (wave1_ids & wave2_ids) or (wave1_ids & wave3_ids) or (wave2_ids & wave3_ids):
        raise ValueError("prior substantive waves overlap")
    prior_ids = wave1_ids | wave2_ids | wave3_ids

    selected: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    for row in rows:
        result_state, record = classify(row, policy, prior_ids)
        (selected if result_state == "selected" else held).append(record)

    selected_ids = {row["inventory_id"] for row in selected}
    overlap = selected_ids & prior_ids
    if overlap:
        raise ValueError(f"Wave 4 overlaps prior waves: {sorted(overlap)}")

    p0_total = sum(1 for row in rows if row.get("priority") == "P0")
    selected_sections = Counter(row["legacy_section"] for row in selected)
    selected_states = Counter(row["current_state_candidate"] for row in selected)
    selected_anchors = Counter(row["canonical_anchor_route"] for row in selected)
    hold_reasons = Counter(reason for row in held for reason in row["hold_reasons"])
    cumulative_selected = len(prior_ids) + len(selected)

    payload = {
        "schema_version": "1.0.0",
        "wave_id": "ct.docs.substantive-rebuild.wave-4.v1",
        "sprint": 10,
        "pass": "A_stale_state_then_B_component_framework_substantive_gap_closure",
        "source_universe_count": 795,
        "p0_candidate_count": p0_total,
        "wave_1_selected_count": len(wave1_ids),
        "wave_2_selected_count": len(wave2_ids),
        "wave_3_selected_count": len(wave3_ids),
        "prior_wave_selected_count": len(prior_ids),
        "selected_count": len(selected),
        "held_count": len(held),
        "cumulative_machine_qualified_p0_count": cumulative_selected,
        "p0_outside_waves_1_2_3_4_count": p0_total - cumulative_selected,
        "prior_wave_overlap_count": 0,
        "selected_section_counts": dict(sorted(selected_sections.items())),
        "selected_state_counts": dict(sorted(selected_states.items())),
        "selected_anchor_counts": dict(sorted(selected_anchors.items())),
        "hold_reason_counts": dict(sorted(hold_reasons.items())),
        "policy": policy,
        "selected_records": selected,
        "held_records": held,
        "guardrails": {
            "historical_body_recovery_claimed": False,
            "terminal_disposition_self_authorized": False,
            "parent_certification_required": True,
            "d3_human_reserved": True,
            "legal_policy_activation_created": False,
            "investment_or_securities_authority_created": False,
            "patent_status_authority_created": False,
            "franchise_or_license_activation_created": False,
            "rights_or_economic_activation_created": False,
            "identity_or_credential_activation_created": False,
            "evidence_or_attestation_authority_created": False,
            "token_exchange_or_settlement_authority_created": False,
            "provider_write_expansion_created": False,
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
    print("PASS_SUBSTANTIVE_REBUILD_WAVE4_BUILD")
    print(f"source_universe_count={result['source_universe_count']}")
    print(f"p0_candidate_count={result['p0_candidate_count']}")
    print(f"wave_1_selected_count={result['wave_1_selected_count']}")
    print(f"wave_2_selected_count={result['wave_2_selected_count']}")
    print(f"wave_3_selected_count={result['wave_3_selected_count']}")
    print(f"selected_count={result['selected_count']}")
    print(f"cumulative_machine_qualified_p0_count={result['cumulative_machine_qualified_p0_count']}")
    print(f"p0_outside_waves_1_2_3_4_count={result['p0_outside_waves_1_2_3_4_count']}")
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
