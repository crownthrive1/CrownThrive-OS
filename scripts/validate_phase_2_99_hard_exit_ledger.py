#!/usr/bin/env python3
"""Validate the Phase 2.99 hard-exit closure ledger.

A PASS from this validator means the ledger is internally coherent and fail-closed.
It does NOT mean the Phase 2.99 hard exit itself has passed.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "developers/manifests/phase-2-99-hard-exit-ledger.v1.json"

EXPECTED_COUNTS = {
    "holdings_portfolio_rows": 68,
    "holdings_domain_rows": 82,
    "holdings_engine_service_rows": 85,
    "phase_2_7_platform_framework_rows": 74,
}
ARTICLE_COMPLETION_FIELDS = (
    "complete_machine_manifest_generated_in_repo",
    "terminal_disposition_assigned_795",
    "section_and_category_mapping_795",
    "exposure_classified_795",
    "risk_classified_795",
    "owner_or_owner_queue_795",
    "canonical_route_or_explicit_nonpublic_state_795",
    "source_mapping_795",
    "navigation_or_intentionally_unlisted_795",
    "p0_p1_substantive_or_explicit_unresolved_closure",
)


def fail(message: str) -> None:
    raise ValueError(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(data: dict, root: Path, check_files: bool = True) -> None:
    authority = data.get("authority", {})
    expected_authority = {
        "roadmap_decision_id": "CT-ADR-ROADMAP-010",
        "governance_decision_id": "CT-ADR-GOV-011",
        "roadmap_generation": "ten_phase_v1",
        "top_level_phase_count": 10,
        "current_phase": 2,
        "current_subphase": "2.99",
        "phase_3_entry": "blocked_pending_phase_2_99_hard_exit",
        "five_phase_lineage": "superseded_historical_only",
    }
    for key, expected in expected_authority.items():
        if authority.get(key) != expected:
            fail(f"authority {key} drifted: {authority.get(key)!r} != {expected!r}")

    dimensions = data.get("dimension_separation", {})
    for key in (
        "priority_not_lifecycle",
        "priority_not_implementation_state",
        "priority_not_institutional_disposition",
        "public_url_not_operational_proof",
        "sunset_preserves_history_ip_sources_domains_contracts",
    ):
        if dimensions.get(key) is not True:
            fail(f"dimension-separation invariant {key} must remain true")

    universes = data.get("macro_count_universes", {})
    if set(universes) != set(EXPECTED_COUNTS):
        fail("macro count-universe identities drifted")
    seen_counts = set()
    for key, expected_count in EXPECTED_COUNTS.items():
        row = universes[key]
        if row.get("count") != expected_count:
            fail(f"{key} count drifted: {row.get('count')!r} != {expected_count}")
        if row.get("source_count_state") != "certified":
            fail(f"{key} source count is not certified")
        if row.get("hard_exit_certified") is not False:
            fail(f"{key} cannot be hard-exit-certified while current reconciliation remains open")
        seen_counts.add(row["count"])
    if len(seen_counts) != len(EXPECTED_COUNTS):
        fail("68/82/85/74 count universes were collapsed or duplicated")

    portfolio = universes["holdings_portfolio_rows"]
    if portfolio.get("typed_resolved_or_classified") != 62 or portfolio.get("pending_identity_resolution") != 6:
        fail("68-row identity reconciliation summary drifted")
    s103 = universes["phase_2_7_platform_framework_rows"]
    if s103.get("typed_resolved_or_classified") != 54 or s103.get("unresolved_current_identity") != 20:
        fail("74-row current identity crosswalk summary drifted")

    article = data.get("articleization", {})
    if article.get("source_inventory_count") != 795 or article.get("source_inventory_verified") is not True:
        fail("795-article source inventory invariant drifted")
    if article.get("stable_seed_schema_defined") is not True or article.get("generator_in_repo") is not True:
        fail("article seed schema/generator must remain registered")
    if article.get("complete_machine_manifest_generated_in_repo") is not False:
        fail("complete 795 machine manifest must remain false until repository evidence exists")
    for key in ARTICLE_COMPLETION_FIELDS[1:]:
        if article.get(key) is not False:
            fail(f"articleization field {key} cannot be promoted before manifest/P0-P1 closure")
    if article.get("hard_exit_certified") is not False:
        fail("articleization cannot be hard-exit-certified")

    reconciliation = data.get("reconciliation", {})
    if reconciliation.get("retroactive_phase_2_0_through_2_9_lane") != "active_until_hard_exit":
        fail("retroactive reconciliation must remain active until hard exit")
    if reconciliation.get("explicit_deferral_ledger_complete") is not False:
        fail("explicit deferral ledger is not yet complete")
    if reconciliation.get("restricted_source_final_audit") != "pending":
        fail("restricted-source final audit must remain pending")
    if reconciliation.get("continuity_recovery_final_reproducibility_audit") != "pending":
        fail("continuity/recovery final audit must remain pending")

    sequence = data.get("repository_security_sequence", {})
    if sequence.get("canonical_main_sha") != data.get("observed_main_sha"):
        fail("canonical main SHA and observed main SHA diverged")
    if sequence.get("canonicalization_complete") is not False:
        fail("canonicalization cannot be complete while active predecessor/security packets remain open")
    if sequence.get("issue_83", {}).get("must_not_run_before_pr_64_canonical") is not True:
        fail("provider-main activation sequence lost its PR #64 predecessor gate")
    if sequence.get("pr_66_issue_79", {}).get("critical_defense_in_depth_finding_resolved") is not False:
        fail("integration-control RLS security disposition was promoted without evidence")

    collab = data.get("collab_portal", {})
    if collab.get("state") != "fail_closed":
        fail("Collab Portal must remain fail-closed")
    if collab.get("all_seven_certification_predicates_passed") is not False:
        fail("Collab Portal seven-predicate certification must remain incomplete")
    if collab.get("private_fallback_tracking") != "active":
        fail("Collab fallback tracking must remain active until all seven predicates pass")

    gates = data.get("open_hard_gates", [])
    gate_ids = [item.get("gate_id") for item in gates]
    if len(gate_ids) != len(set(gate_ids)) or len(gates) < 8:
        fail("hard-exit gate registry is incomplete or contains duplicate IDs")
    blocking_open = [item for item in gates if item.get("blocking") is True and item.get("state") != "pass"]
    if not blocking_open:
        fail("this observed ledger must preserve at least one open blocking hard-exit gate")

    hard_exit = data.get("hard_exit", {})
    if hard_exit.get("state") != "not_met":
        fail("Phase 2.99 hard exit is not yet met")
    if hard_exit.get("phase_2_complete") is not False:
        fail("Phase 2 cannot be complete before Phase 2.99 hard exit")
    if hard_exit.get("phase_3_entry_open") is not False:
        fail("Phase 3 entry cannot be open")
    if hard_exit.get("phase_3_entry") != "blocked_pending_phase_2_99_hard_exit":
        fail("Phase 3 blocked state drifted")
    if hard_exit.get("final_certification_recorded") is not False:
        fail("final Phase 2 certification cannot be recorded")

    ladder = data.get("external_assessment_ladder", {})
    if ladder.get("authority") != "non_authoritative_progress_metric_only":
        fail("external grading ladder must never become institutional authority")
    if ladder.get("current_external_grade") != 96:
        fail("observed external grade context drifted")
    if any(ladder.get(key) != "not_met" for key in (
        "97_macro_certification",
        "98_articleization_p0_p1_closure",
        "99_final_adversarial_reconciliation",
        "100_phase_2_99_hard_exit_certification",
    )):
        fail("external closure thresholds cannot be promoted while hard exit remains open")

    integration = data.get("integration", {})
    if integration.get("workflow_wiring_state") != "deferred_to_post_pr64_integration_packet":
        fail("validator workflow integration must remain outside PR #64-owned workflow surfaces")
    if integration.get("rollback") != "revert_bounded_closure_ledger_packet":
        fail("bounded rollback invariant drifted")

    if check_files:
        for rel in data.get("evidence_paths", []):
            if not (root / rel).is_file():
                fail(f"required evidence path missing: {rel}")

        phase = load_json(root / "developers/manifests/institutional-phase-namespace.v2.json")
        if phase.get("decision_id") != "CT-ADR-ROADMAP-010":
            fail("machine phase namespace no longer points to CT-ADR-ROADMAP-010")
        if phase.get("top_level_phase_count") != 10:
            fail("machine phase namespace is not ten-phase")
        if phase.get("current_phase") != 2 or phase.get("current_subphase") != "2.99":
            fail("machine current phase/subphase drifted")
        if phase.get("phase_3_entry") != "blocked_pending_phase_2_99_hard_exit":
            fail("machine Phase 3 gate drifted")
        superseded = phase.get("superseded_top_level_namespaces", [])
        if not any(item.get("source_pr") == 62 and "superseded" in item.get("disposition", "") for item in superseded):
            fail("PR #62 five-phase snapshot must remain superseded lineage")

        article_text = (root / article["evidence_path"]).read_text(encoding="utf-8")
        for fragment in (
            "source_inventory_count: 795",
            "complete_machine_manifest_generated_in_repo: pending",
            "P0_P1_disposition_completion: pending",
        ):
            if fragment not in article_text:
                fail(f"articleization evidence missing current-state fragment: {fragment!r}")

        plan_text = (root / "changelog/phase-2-99-plan.mdx").read_text(encoding="utf-8")
        if "## Exit criteria" not in plan_text:
            fail("Phase 2.99 plan lost its exit criteria")
        if "current hard-exit gate evaluates `pass`" not in plan_text:
            fail("Phase 2.99 plan no longer requires explicit hard-exit PASS")


def self_test(data: dict) -> None:
    validate(data, ROOT, check_files=False)

    bad = copy.deepcopy(data)
    bad["authority"]["top_level_phase_count"] = 5
    try:
        validate(bad, ROOT, check_files=False)
    except ValueError:
        pass
    else:
        raise AssertionError("five-phase promotion must fail")

    bad = copy.deepcopy(data)
    bad["hard_exit"]["phase_3_entry_open"] = True
    try:
        validate(bad, ROOT, check_files=False)
    except ValueError:
        pass
    else:
        raise AssertionError("premature Phase 3 entry must fail")

    bad = copy.deepcopy(data)
    bad["macro_count_universes"]["holdings_domain_rows"]["count"] = 68
    try:
        validate(bad, ROOT, check_files=False)
    except ValueError:
        pass
    else:
        raise AssertionError("count-universe collapse must fail")

    bad = copy.deepcopy(data)
    bad["articleization"]["terminal_disposition_assigned_795"] = True
    try:
        validate(bad, ROOT, check_files=False)
    except ValueError:
        pass
    else:
        raise AssertionError("false articleization completion must fail")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    data = load_json(LEDGER)
    if args.self_test:
        self_test(data)
        print("Phase 2.99 closure-ledger self-test passed; false phase/count/article promotion remains blocked.")
        return 0

    validate(data, ROOT, check_files=True)
    open_count = sum(
        1 for item in data["open_hard_gates"]
        if item.get("blocking") is True and item.get("state") != "pass"
    )
    print("Phase 2.99 closure-ledger consistency validation: PASS")
    print(f"Open blocking hard-exit gates preserved: {open_count}")
    print("Institutional state: Phase 2 / 2.99; Phase 3 blocked_pending_phase_2_99_hard_exit.")
    print("Important: validator PASS != Phase 2.99 hard-exit PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
