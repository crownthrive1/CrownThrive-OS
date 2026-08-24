#!/usr/bin/env python3
"""Validate Sprint 12 classification hygiene and substantive Wave 6 closure."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave6 as wave6

EXPECTED_WAVE = "c4389ff5f19674813e0a89734a9aa6b65b7e6ecba2e4b3710278fa05a4616caa"
EXPECTED_OVERLAY = "f9b621dce0c92f1ad594a10edac9419d7a19c13ef0303968f26c131ee7d7cabf"
EXPECTED_VAULT = "9030c967310b873bd11bbd5b67a301c952baa7f4a2072285c30e93f19773d52a"
EXPECTED_IDS = ["HC-0212", "HC-0213", "HC-0214"]
EXPECTED_HOLDS = {
    "architecture_governance_collision_hold": 2,
    "authority_governance_specialist_hold": 4,
    "economic_specialist_hold": 6,
    "identity_specialist_hold": 3,
    "rights_economic_specialist_hold": 6,
    "rights_license_specialist_hold": 14,
}


def load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def require_text(path: str, terms: list[str]) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    for term in terms:
        assert term in text, f"{path}: missing required term {term!r}"


def nav_group(data: dict, tab_name: str, group_name: str) -> dict:
    tab = next(t for t in data["navigation"]["tabs"] if t.get("tab") == tab_name)
    return next(g for g in tab["groups"] if g.get("group") == group_name)


def main() -> None:
    built = wave6.build()
    assert built["source_universe_count"] == 795
    assert built["p0_candidate_count"] == 449
    assert built["prior_wave_selected_count"] == 58
    assert built["ai_collision_candidate_count"] == 35
    assert built["ai_collision_machine_admission_count"] == 0
    assert built["ai_collision_primary_hold_lane_counts"] == EXPECTED_HOLDS
    assert built["ai_collision_overlay_sha256"] == EXPECTED_OVERLAY
    assert built["ai_collision_historical_crosswalk_rewritten"] is False
    assert built["selected_count"] == 3
    assert sorted(r["inventory_id"] for r in built["selected_records"]) == EXPECTED_IDS
    assert built["cumulative_machine_qualified_p0_count"] == 61
    assert built["p0_outside_waves_1_2_3_4_5_6_count"] == 388
    assert built["prior_wave_overlap_count"] == 0
    assert built["selected_section_counts"] == {"Cultural Imprint Engine (CIE)": 3}
    assert built["selected_state_counts"] == {"cie_framework_reconciliation": 3}
    assert built["selected_anchor_counts"] == {"/doctrine/cie-framework-reconciliation-contract": 3}
    assert built["wave_sha256"] == EXPECTED_WAVE
    assert built["guardrails"]["historical_body_recovery_claimed"] is False
    assert built["guardrails"]["terminal_disposition_self_authorized"] is False
    assert built["guardrails"]["phase_3_entry"] == "blocked_pending_phase_2_99_hard_exit"
    assert built["guardrails"]["phase_11_20_state"] == "reserved_definition_required"

    overlay = load_json("data/documentation/sprint-12-ai-collision-reclassification-overlay.v1.json")
    assert overlay["candidate_count"] == 35
    assert overlay["machine_admission_count"] == 0
    assert overlay["primary_hold_lane_counts"] == EXPECTED_HOLDS
    assert overlay["overlay_sha256"] == EXPECTED_OVERLAY
    assert overlay["historical_sprint_4_crosswalk_rewritten"] is False
    assert overlay["terminal_disposition_accepted"] is False

    passa = load_json("data/documentation/sprint-12-pass-a-receipt.v1.json")
    assert passa["classification_collision_overlay"]["overlay_sha256"] == EXPECTED_OVERLAY
    assert passa["classification_collision_overlay"]["p0_candidate_count"] == 35
    assert passa["classification_collision_overlay"]["machine_admission_count"] == 0
    assert passa["bounded_pivot_diagnosis"]["selected_inventory_ids"] == EXPECTED_IDS

    gap = load_json("data/documentation/substantive-rebuild-wave-6-gap-closure.v1.json")
    assert gap["wave_sha256"] == EXPECTED_WAVE
    assert gap["ai_collision_overlay_sha256"] == EXPECTED_OVERLAY
    assert gap["result"]["wave_6_machine_qualified"] == 3
    assert gap["result"]["cumulative_machine_qualified_p0"] == 61
    assert gap["result"]["p0_outside_waves_1_2_3_4_5_6"] == 388
    assert gap["result"]["selected_inventory_ids"] == EXPECTED_IDS
    assert gap["result"]["terminal_disposition_accepted"] is False

    passb = load_json("data/documentation/sprint-12-pass-b-receipt.v1.json")
    assert passb["wave_sha256"] == EXPECTED_WAVE
    assert passb["ai_collision_overlay_sha256"] == EXPECTED_OVERLAY
    assert passb["vault_closure_sha256"] == EXPECTED_VAULT
    assert passb["wave_6"]["selected_inventory_ids"] == EXPECTED_IDS
    assert passb["wave_6"]["cumulative_machine_qualified_p0_count"] == 61
    assert passb["wave_6"]["p0_outside_waves_1_2_3_4_5_6_count"] == 388
    assert passb["framework_factory"]["package_state"] == "controlled_test"
    assert passb["framework_factory"]["parent_certification_state"] == "pending"
    assert passb["framework_factory"]["operationally_enabled"] is False
    assert passb["framework_factory"]["public_activation_allowed"] is False

    package = load_json("frameworks/documentation-reconciliation-continuity/sprint-12-substantive-wave6-package.v1.json")
    assert package["wave_sha256"] == EXPECTED_WAVE
    assert package["ai_collision_overlay_sha256"] == EXPECTED_OVERLAY
    assert package["vault_closure_sha256"] == EXPECTED_VAULT
    assert package["wave_6_selected_count"] == 3
    assert package["cumulative_machine_qualified_p0_count"] == 61
    assert package["p0_outside_waves_1_2_3_4_5_6_count"] == 388
    assert package["state"] == "controlled_test"
    assert package["authority"]["parent_certification_state"] == "pending"
    assert package["authority"]["operationally_enabled"] is False
    assert package["authority"]["public_activation_allowed"] is False

    require_text("doctrine/cie-framework-reconciliation-contract.mdx", [
        "framework definition ≠ deployed service",
        "provider capability ≠ CrownThrive authority",
        "/doctrine/cultural-imprint-engine",
        "/doctrine/cie-public-internal-usage",
        "/doctrine/cie-integration-handoffs",
        "/standards/evidence-claims-and-proof-standard",
        "/technology/phase-3-readiness-gate",
        "blocked_pending_phase_2_99_hard_exit",
    ])
    require_text("knowledge/documentation-substantive-rebuild-wave-6.mdx", [
        "ai_collision_p0_candidates: 35",
        "wave_6_machine_qualified: 3",
        "cumulative_machine_qualified_p0: 61",
        "p0_outside_waves_1_2_3_4_5_6: 388",
        EXPECTED_WAVE,
        EXPECTED_OVERLAY,
        "terminal_disposition_accepted: false",
    ])
    require_text("changelog/docs-substantive-rebuild-sprint-12-wave-6-2026-08-24.mdx", [
        "rights_license_specialist_hold: 14",
        "wave_6_machine_qualified: 3",
        "cumulative_machine_qualified_p0: 61",
        EXPECTED_WAVE,
        EXPECTED_VAULT,
        "blocked_pending_phase_2_99_hard_exit",
    ])

    docs = load_json("docs.json")
    doctrine_pages = nav_group(docs, "CrownThrive OS", "Institutional Doctrine")["pages"]
    knowledge_pages = nav_group(docs, "CrownThrive OS", "Institutional Knowledge")["pages"]
    changelog_pages = nav_group(docs, "CrownThrive OS", "Changelog and Decisions")["pages"]
    assert "doctrine/cie-framework-reconciliation-contract" in doctrine_pages
    assert "knowledge/documentation-substantive-rebuild-wave-6" in knowledge_pages
    assert "changelog/docs-substantive-rebuild-sprint-12-wave-6-2026-08-24" in changelog_pages
    crown_groups = next(t for t in docs["navigation"]["tabs"] if t.get("tab") == "CrownThrive OS")["groups"]
    assert crown_groups[-1]["group"] == "Changelog and Decisions"

    print("PASS_SPRINT_12_SUBSTANTIVE_WAVE6")
    print("ai_collision_candidates=35")
    print("ai_collision_machine_admission=0")
    print("ai_collision_overlay_sha256=" + EXPECTED_OVERLAY)
    print("wave_6_selected_count=3")
    print("cumulative_machine_qualified_p0=61")
    print("p0_remaining=388")
    print("wave_sha256=" + EXPECTED_WAVE)
    print("vault_closure_sha256=" + EXPECTED_VAULT)
    print("navigation_routes_present=true")
    print("terminal_disposition_accepted=false")
    print("parent_certification_state=pending")
    print("phase_3_entry=blocked_pending_phase_2_99_hard_exit")


if __name__ == "__main__":
    main()
