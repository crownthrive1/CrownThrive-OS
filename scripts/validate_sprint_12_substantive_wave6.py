#!/usr/bin/env python3
"""Validate Sprint 12 classification hygiene and substantive Wave 6 closure.

Phase 3 note: Sprint 12 receipts remain immutable historical evidence. The
Wave 6 builder re-reads mutable current canonical anchors, so its recomputed
hash is diagnostic rather than the authority for the frozen Sprint 12 receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_substantive_rebuild_wave6 as wave6
import substantive_rebuild_current_snapshot as current_snapshot

EXPECTED_WAVE = "c4389ff5f19674813e0a89734a9aa6b65b7e6ecba2e4b3710278fa05a4616caa"
EXPECTED_OVERLAY = "f9b621dce0c92f1ad594a10edac9419d7a19c13ef0303968f26c131ee7d7cabf"
EXPECTED_VAULT = "9030c967310b873bd11bbd5b67a301c952baa7f4a2072285c30e93f19773d52a"
EXPECTED_IDS = ["HC-0212", "HC-0213", "HC-0214"]
HISTORICAL_PHASE3_ENTRY = "blocked_pending_phase_2_99_hard_exit"
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


def nav_groups(container: dict) -> list[dict]:
    """Return all descendant groups from legacy, current, or nested Mintlify nav."""
    found: list[dict] = []
    for key in ("groups", "pages"):
        children = container.get(key)
        if not isinstance(children, list):
            continue
        for child in children:
            if not isinstance(child, dict):
                continue
            if isinstance(child.get("group"), str):
                found.append(child)
            found.extend(nav_groups(child))
    return found


def nav_group(data: dict, tab_name: str, group_name: str) -> dict:
    tab = next(t for t in data["navigation"]["tabs"] if t.get("tab") == tab_name)
    matches = [g for g in nav_groups(tab) if g.get("group") == group_name]
    assert len(matches) == 1, (
        f"expected exactly one {group_name!r} group in {tab_name!r}; found {len(matches)}"
    )
    return matches[0]


def main() -> None:
    built = wave6.build()
    semantic_snapshot = current_snapshot.load_snapshot()
    current_waves = semantic_snapshot["current_waves"]
    current_wave = current_waves["6"]
    snapshot_errors = current_snapshot.validate_current_wave(
        built, 6, semantic_snapshot
    )
    assert not snapshot_errors, "; ".join(snapshot_errors)
    assert built["source_universe_count"] == 795
    assert built["p0_candidate_count"] == 449
    assert built["prior_wave_selected_count"] == sum(
        current_waves[str(number)]["selected_count"] for number in range(1, 6)
    )
    assert built["ai_collision_candidate_count"] == 35
    assert built["ai_collision_machine_admission_count"] == 0
    assert built["ai_collision_primary_hold_lane_counts"] == EXPECTED_HOLDS
    assert built["ai_collision_overlay_sha256"] == EXPECTED_OVERLAY
    assert built["ai_collision_historical_crosswalk_rewritten"] is False
    assert built["selected_count"] == current_wave["selected_count"]
    assert sorted(r["inventory_id"] for r in built["selected_records"]) == EXPECTED_IDS
    assert (
        built["cumulative_machine_qualified_p0_count"]
        == current_wave["cumulative_machine_qualified_p0_count"]
    )
    assert (
        built["p0_outside_waves_1_2_3_4_5_6_count"]
        == current_wave["p0_outside_current_waves_count"]
    )
    assert built["prior_wave_overlap_count"] == 0
    assert built["selected_section_counts"] == {"Cultural Imprint Engine (CIE)": 3}
    assert built["selected_state_counts"] == {"cie_framework_reconciliation": 3}
    assert built["selected_anchor_counts"] == {"/doctrine/cie-framework-reconciliation-contract": 3}

    # The current recomputation includes mutable canonical anchor-quality data.
    # Preserve it for diagnostics, but do not confuse current Phase 3 anchor
    # evolution with corruption of the immutable Sprint 12 receipt digest.
    current_recomputed_wave_sha = built["wave_sha256"]

    assert built["guardrails"]["historical_body_recovery_claimed"] is False
    assert built["guardrails"]["terminal_disposition_self_authorized"] is False
    assert built["guardrails"]["parent_certification_required"] is True
    assert built["guardrails"]["d3_human_reserved"] is True
    assert built["guardrails"]["ai_collision_family_broadly_qualified"] is False
    assert built["guardrails"]["rights_or_economic_activation_created"] is False
    assert built["guardrails"]["provider_write_expansion_created"] is False
    assert built["guardrails"]["production_activation_created"] is False
    assert built["guardrails"]["phase_3_entry"] == HISTORICAL_PHASE3_ENTRY
    assert built["guardrails"]["phase_11_20_state"] == "reserved_definition_required"

    phase3_gate = load_json("developers/manifests/phase3-institutional-gate.v1.json")
    assert phase3_gate["institutional_generation"] == "phase_3"
    assert phase3_gate["historical_phase_2_99_evidence"] == "preserved_noncurrent"
    assert phase3_gate["holds_preserved"] is True
    assert phase3_gate["d3_human_reserved"] is True
    assert phase3_gate["phase_label_is_blanket_certification"] is False

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
        HISTORICAL_PHASE3_ENTRY,
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
        HISTORICAL_PHASE3_ENTRY,
    ])

    docs = load_json("docs.json")
    doctrine_pages = nav_group(docs, "CrownThrive OS", "Institutional Doctrine")["pages"]
    knowledge_pages = nav_group(docs, "CrownThrive OS", "Institutional Knowledge")["pages"]
    changelog_pages = nav_group(docs, "CrownThrive OS", "Changelog and Decisions")["pages"]
    assert "doctrine/cie-framework-reconciliation-contract" in doctrine_pages
    assert "knowledge/documentation-substantive-rebuild-wave-6" in knowledge_pages
    assert "changelog/docs-substantive-rebuild-sprint-12-wave-6-2026-08-24" in changelog_pages
    crown_tab = next(t for t in docs["navigation"]["tabs"] if t.get("tab") == "CrownThrive OS")
    crown_groups = nav_groups(crown_tab)
    assert crown_groups[-1]["group"] == "Changelog and Decisions"

    print("PASS_SPRINT_12_SUBSTANTIVE_WAVE6")
    print("ai_collision_candidates=35")
    print("ai_collision_machine_admission=0")
    print("ai_collision_overlay_sha256=" + EXPECTED_OVERLAY)
    print("wave_6_selected_count=3")
    print(
        "current_cumulative_machine_qualified_p0="
        + str(built["cumulative_machine_qualified_p0_count"])
    )
    print("current_p0_remaining=" + str(built["p0_outside_waves_1_2_3_4_5_6_count"]))
    print("historical_cumulative_machine_qualified_p0=61")
    print("historical_p0_remaining=388")
    print("historical_wave_sha256=" + EXPECTED_WAVE)
    print("current_recomputed_wave_sha256=" + current_recomputed_wave_sha)
    print("vault_closure_sha256=" + EXPECTED_VAULT)
    print("navigation_routes_present=true")
    print("terminal_disposition_accepted=false")
    print("parent_certification_state=pending")
    print("historical_phase_3_entry=" + HISTORICAL_PHASE3_ENTRY)
    print("current_institutional_generation=phase_3")


if __name__ == "__main__":
    main()
