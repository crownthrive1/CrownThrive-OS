#!/usr/bin/env python3
"""Build Sprint 8 substantive-rebuild Wave 2.

Wave 2 follows the completed 795-title candidate map and Sprint 7 Wave 1. It
selects only P0 merged-successor rows in evidence/audit, identity/trust,
registry/machine-contract and CrownThrive IO machine-contract state families.
It requires an already-substantive current canonical anchor and excludes the
Wave 1 identities plus high-risk D3/legal/economic/restricted material.
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

POLICY_PATH = ROOT / "data/documentation/substantive-rebuild-wave-2-policy.v1.json"

# Wave 2 owns machine-contract reconciliation.  Identity/trust and
# evidence/audit rows remain visible as continuity candidates but are reserved
# to Wave 3's state-specific contracts before any generic Wave 2 anchor scan.
WAVE2_OWNED_STATE_FAMILIES = wave1.WAVE2_RESERVED_STATE_FAMILIES
WAVE3_RESERVED_STATE_FAMILIES = wave1.WAVE3_RESERVED_STATE_FAMILIES
WAVE2_STATE_ANCHOR_ROUTES = {
    # This mapping is preserved from the governed Sprint 8 Wave 2 register and
    # receipt.  It is not inferred from today's body-size/link thresholds.
    "machine_contract_reconciliation": "/chlom/ecosystem-integrations",
}
WAVE2_CONTINUITY_ONLY_ROUTES = frozenset({"/chlom/registry-model"})
WAVE2_STATE_FAMILY_DEFERRAL_REASONS = {
    state: "deferred_to_wave_3_identity_evidence_state_lane"
    for state in WAVE3_RESERVED_STATE_FAMILIES
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def text_has_any(text: str, terms: list[str]) -> bool:
    low = text.casefold()
    return any(term.casefold() in low for term in terms)


def choose_anchor(row: dict[str, Any], policy: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    allowed = set(policy["canonical_anchor_routes"])
    checked: list[dict[str, Any]] = []
    state = str(row.get("current_state_candidate", ""))
    designated = WAVE2_STATE_ANCHOR_ROUTES.get(state)
    target_routes = list(row.get("target_routes", []))
    qualification_routes = (
        [designated]
        if designated is not None and designated in target_routes
        else [
            route
            for route in target_routes
            if route not in WAVE2_CONTINUITY_ONLY_ROUTES
        ]
    )
    for route in qualification_routes:
        if route is None:
            continue
        if route not in allowed:
            continue
        try:
            quality = wave1.route_quality(route)
        except FileNotFoundError:
            continue
        checked.append(quality)
        if (
            quality["editorial_current_successor_eligible"]
            and quality["body_characters"] >= int(policy["minimum_anchor_body_characters"])
            and quality["internal_link_count"] >= int(policy["minimum_anchor_internal_links"])
        ):
            return route, checked
    return None, checked


def classify(
    row: dict[str, Any],
    policy: dict[str, Any],
    wave1_ids: set[str],
) -> tuple[str, dict[str, Any]]:
    reasons: list[str] = []
    inventory_id = str(row["inventory_id"])
    title = str(row.get("legacy_title", ""))
    state = str(row.get("current_state_candidate", ""))
    flags = " ".join(str(x) for x in row.get("flags", []))
    deferred_state_reason = WAVE2_STATE_FAMILY_DEFERRAL_REASONS.get(state)

    if inventory_id in wave1_ids:
        reasons.append("already_selected_wave_1")
    if deferred_state_reason:
        reasons.append(deferred_state_reason)
    if row.get("priority") != policy["required_priority"]:
        reasons.append("not_p0")
    if row.get("disposition_candidate") != policy["required_candidate_disposition"]:
        reasons.append("candidate_disposition_not_merged_successor")
    if row.get("missing_target_routes"):
        reasons.append("missing_target_route")
    if state not in set(policy["allowed_state_families"]):
        reasons.append("outside_wave_2_state_family")
    if text_has_any(title, policy["blocked_title_terms"]):
        reasons.append("d3_or_high_risk_title_term")
    if text_has_any(state, policy["blocked_state_terms"]):
        reasons.append("d3_or_high_risk_state")
    if text_has_any(flags, policy["blocked_flag_terms"]):
        reasons.append("explicit_high_risk_flag")

    if deferred_state_reason:
        anchor, quality = None, []
    else:
        anchor, quality = choose_anchor(row, policy)
        if not anchor:
            reasons.append("no_qualified_substantive_anchor")

    base = {
        "inventory_id": inventory_id,
        "article_id": row["article_id"],
        "legacy_section": row["legacy_section"],
        "legacy_subcategory": row["legacy_subcategory"],
        "legacy_title": title,
        "priority": row.get("priority"),
        "candidate_disposition": row.get("disposition_candidate"),
        "current_state_candidate": state,
        "target_routes": row.get("target_routes", []),
        "continuity_only_routes": sorted(
            set(row.get("target_routes", [])) & WAVE2_CONTINUITY_ONLY_ROUTES
        ),
        "source_specialist_review_flags": wave1.source_specialist_review_flags(row),
    }

    if reasons:
        return "held", {
            **base,
            "hold_reasons": sorted(set(reasons)),
            "anchor_quality_checked": quality,
        }

    anchor_quality = next(q for q in quality if q["route"] == anchor)
    return "selected", {
        **base,
        "candidate_cohort": row["candidate_cohort"],
        "canonical_anchor_route": anchor,
        "canonical_anchor_quality": anchor_quality,
        "continuity_routes": row.get("target_routes", []),
        "historical_body_status": row.get("body_status", "reconstruction_required"),
        "substantive_current_successor_body": "present_and_machine_qualified",
        "machine_acceptance_state": policy["machine_acceptance_state"],
        "terminal_disposition_accepted": False,
        "parent_certification_required": True,
        "authority_ceiling": policy["authority_ceiling"],
    }


def build() -> dict[str, Any]:
    policy = load_json(POLICY_PATH)
    allowed_states = set(policy["allowed_state_families"])
    if not WAVE2_OWNED_STATE_FAMILIES <= allowed_states:
        raise ValueError("Wave 2 policy omits its reserved machine-contract state lane")
    if not WAVE3_RESERVED_STATE_FAMILIES <= allowed_states:
        raise ValueError("Wave 2 policy cannot transparently defer absent Wave 3 state lanes")
    if set(WAVE2_STATE_ANCHOR_ROUTES) != WAVE2_OWNED_STATE_FAMILIES:
        raise ValueError("Wave 2 state-anchor map must cover exactly its owned state families")
    if not set(WAVE2_STATE_ANCHOR_ROUTES.values()) <= set(policy["canonical_anchor_routes"]):
        raise ValueError("Wave 2 state-anchor route is outside the governed policy allowlist")
    rows = wave1.aggregate_candidate_rows()
    first = wave1.build()
    wave1_ids = {str(row["inventory_id"]) for row in first["selected_records"]}

    selected: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    for row in rows:
        result_state, record = classify(row, policy, wave1_ids)
        (selected if result_state == "selected" else held).append(record)

    selected_ids = {row["inventory_id"] for row in selected}
    overlap = selected_ids & wave1_ids
    if overlap:
        raise ValueError(f"Wave 2 overlaps Wave 1: {sorted(overlap)}")

    p0_total = sum(1 for row in rows if row.get("priority") == "P0")
    selected_sections = Counter(row["legacy_section"] for row in selected)
    selected_states = Counter(row["current_state_candidate"] for row in selected)
    selected_anchors = Counter(row["canonical_anchor_route"] for row in selected)
    hold_reasons = Counter(reason for row in held for reason in row["hold_reasons"])
    cumulative_selected = len(wave1_ids) + len(selected)

    payload = {
        "schema_version": "1.0.0",
        "selection_view": wave1.current_selection_view(2),
        "wave_id": "ct.docs.substantive-rebuild.wave-2.v1",
        "sprint": 8,
        "pass": "A_stale_state_and_evidence_identity_registry_machine_contract_qualification",
        "source_universe_count": 795,
        "p0_candidate_count": p0_total,
        "wave_1_selected_count": len(wave1_ids),
        "selected_count": len(selected),
        "held_count": len(held),
        "cumulative_machine_qualified_p0_count": cumulative_selected,
        "p0_outside_waves_1_2_count": p0_total - cumulative_selected,
        "wave_1_overlap_count": 0,
        "selected_section_counts": dict(sorted(selected_sections.items())),
        "selected_state_counts": dict(sorted(selected_states.items())),
        "selected_anchor_counts": dict(sorted(selected_anchors.items())),
        "hold_reason_counts": dict(sorted(hold_reasons.items())),
        "policy": policy,
        "selected_records": selected,
        "held_records": held,
        "editorial_current_successor_exclusions": wave1.editorial_exclusion_report(held),
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
    print("PASS_SUBSTANTIVE_REBUILD_WAVE2_BUILD")
    print(f"source_universe_count={result['source_universe_count']}")
    print(f"p0_candidate_count={result['p0_candidate_count']}")
    print(f"wave_1_selected_count={result['wave_1_selected_count']}")
    print(f"selected_count={result['selected_count']}")
    print(f"cumulative_machine_qualified_p0_count={result['cumulative_machine_qualified_p0_count']}")
    print(f"p0_outside_waves_1_2_count={result['p0_outside_waves_1_2_count']}")
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
