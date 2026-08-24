#!/usr/bin/env python3
"""Build the Sprint 12 reconciliation overlay for the 35-row P0 AI/agent/algorithm collision family.

This is classification hygiene only. It does not rewrite the historical Sprint 4
crosswalk, qualify a substantive successor, accept a terminal disposition, or
create operational authority.
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

POLICY_PATH = ROOT / "data/documentation/substantive-rebuild-wave-6-policy.v1.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def prior_wave_ids() -> set[str]:
    ids: set[str] = set()
    built = [wave1.build(), wave2.build(), wave3.build(), wave4.build(), wave5.build()]
    for result in built:
        current = {str(row["inventory_id"]) for row in result["selected_records"]}
        if ids & current:
            raise ValueError("prior substantive waves overlap")
        ids |= current
    return ids


def text_has_any(text: str, terms: list[str]) -> bool:
    low = text.casefold()
    return any(term.casefold() in low for term in terms)


def primary_hold_lane(row: dict[str, Any], policy: dict[str, Any]) -> tuple[str, list[str]]:
    flags = {str(x) for x in row.get("flags", [])}
    title = str(row.get("legacy_title", ""))
    reasons: list[str] = []

    if "identity_claim_requires_current_binding_evidence" in flags:
        reasons.append("identity_binding_evidence_required")
        return "identity_specialist_hold", reasons

    economic = "no_economic_authority_from_recovered_title" in flags
    rights = "rights_and_license_state_requires_current_evidence" in flags
    if economic and rights:
        reasons.extend(["economic_authority_not_inferred", "rights_license_current_evidence_required"])
        return "rights_economic_specialist_hold", reasons
    if economic:
        reasons.append("economic_authority_not_inferred")
        return "economic_specialist_hold", reasons
    if rights:
        reasons.append("rights_license_current_evidence_required")
        return "rights_license_specialist_hold", reasons

    if "no_authority_expansion_from_article_rebuild" in flags:
        reasons.append("authority_expansion_prohibited")
        return "authority_governance_specialist_hold", reasons

    if "no_historical_research_promotion_to_current_authority" in flags:
        reasons.append("historical_research_not_current_authority")
        return "historical_research_hold", reasons

    if text_has_any(title, policy["collision_lane"]["architecture_governance_title_terms"]):
        reasons.append("title_semantics_collide_with_governance_or_specialist_domain")
        return "architecture_governance_collision_hold", reasons

    reasons.append("model_agent_term_requires_current_semantic_reconciliation")
    return "model_agent_semantic_collision_hold", reasons


def build_overlay(rows: list[dict[str, Any]] | None = None, prior_ids: set[str] | None = None) -> dict[str, Any]:
    policy = load_json(POLICY_PATH)
    if rows is None:
        rows = wave1.aggregate_candidate_rows()
    if prior_ids is None:
        prior_ids = prior_wave_ids()

    state = policy["collision_lane"]["source_state_family"]
    candidates = [
        row for row in rows
        if row.get("priority") == policy["required_priority"]
        and str(row["inventory_id"]) not in prior_ids
        and row.get("current_state_candidate") == state
        and row.get("disposition_candidate") == policy["required_candidate_disposition"]
        and not row.get("missing_target_routes")
    ]

    records: list[dict[str, Any]] = []
    lane_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    for row in candidates:
        lane, reasons = primary_hold_lane(row, policy)
        lane_counts[lane] += 1
        for flag in row.get("flags", []):
            flag_counts[str(flag)] += 1
        records.append({
            "inventory_id": str(row["inventory_id"]),
            "article_id": row["article_id"],
            "legacy_section": row["legacy_section"],
            "legacy_subcategory": row["legacy_subcategory"],
            "legacy_title": row.get("legacy_title"),
            "source_state_family": state,
            "priority": row.get("priority"),
            "candidate_disposition": row.get("disposition_candidate"),
            "flags": list(row.get("flags", [])),
            "target_routes": list(row.get("target_routes", [])),
            "overlay_primary_hold_lane": lane,
            "overlay_hold_reasons": reasons,
            "overlay_terminal": False,
            "machine_qualified": False,
        })

    records.sort(key=lambda row: row["inventory_id"])
    payload = {
        "schema_version": "1.0.0",
        "overlay_id": "ct.docs.sprint12.ai-agent-algorithm-collision-hygiene.v1",
        "sprint": 12,
        "source_state_family": state,
        "candidate_count": len(candidates),
        "machine_admission_count": 0,
        "broad_family_qualification": False,
        "historical_sprint_4_crosswalk_rewritten": False,
        "terminal_disposition_accepted": False,
        "classification_state": "non_terminal_reconciliation_overlay",
        "primary_hold_lane_counts": dict(sorted(lane_counts.items())),
        "flag_counts": dict(sorted(flag_counts.items())),
        "records": records,
        "guardrails": {
            "d3_human_reserved": True,
            "authority_created": False,
            "rights_or_license_authority_created": False,
            "economic_authority_created": False,
            "identity_or_credential_authority_created": False,
            "historical_research_promoted_to_current_authority": False,
            "provider_write_expansion_created": False,
            "production_activation_created": False,
            "phase_3_entry": "blocked_pending_phase_2_99_hard_exit",
            "phase_11_20_state": "reserved_definition_required",
            "canonical_brand": "CrownThrive"
        }
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["overlay_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_overlay()
    print("PASS_SPRINT_12_AI_COLLISION_HYGIENE")
    print(f"candidate_count={result['candidate_count']}")
    print("machine_admission_count=0")
    print("historical_sprint_4_crosswalk_rewritten=false")
    print("primary_hold_lane_counts=" + json.dumps(result["primary_hold_lane_counts"], sort_keys=True))
    print("flag_counts=" + json.dumps(result["flag_counts"], sort_keys=True))
    print("overlay_sha256=" + result["overlay_sha256"])
    print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"output={args.output}")


if __name__ == "__main__":
    main()
