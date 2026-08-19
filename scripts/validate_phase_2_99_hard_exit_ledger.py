#!/usr/bin/env python3
"""Validate the Phase 2.99 hard-exit closure ledger.

PASS means the ledger is coherent and fail-closed. It does not mean the
Phase 2.99 hard exit itself has passed.
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
ARTICLE_OPEN_FIELDS = (
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
CANONICAL_COLLAB = {
    "credential_exact_match": "passed",
    "project_meta_authenticated": "passed",
    "institutional_project_uid": "passed",
    "approved_field_map": "blocked",
    "authenticated_project_read": "passed",
    "bounded_write_readback": "closed",
    "webhook_sender_delivery_integrity": "blocked",
}


def fail(message: str) -> None:
    raise ValueError(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require_equal(actual, expected, label: str) -> None:
    if actual != expected:
        fail(f"{label} drifted: {actual!r} != {expected!r}")


def validate(data: dict, root: Path, check_files: bool = True) -> None:
    require_equal(data.get("manifest_version"), "1.1.0", "manifest version")

    authority = data.get("authority", {})
    for key, expected in {
        "roadmap_decision_id": "CT-ADR-ROADMAP-010",
        "governance_decision_id": "CT-ADR-GOV-011",
        "roadmap_generation": "ten_phase_v1",
        "top_level_phase_count": 10,
        "current_phase": 2,
        "current_subphase": "2.99",
        "phase_3_entry": "blocked_pending_phase_2_99_hard_exit",
        "five_phase_lineage": "superseded_historical_only",
    }.items():
        require_equal(authority.get(key), expected, f"authority.{key}")

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
    require_equal(set(universes), set(EXPECTED_COUNTS), "macro count-universe identities")
    observed_counts = set()
    for key, expected_count in EXPECTED_COUNTS.items():
        row = universes[key]
        require_equal(row.get("count"), expected_count, f"{key}.count")
        require_equal(row.get("source_count_state"), "certified", f"{key}.source_count_state")
        require_equal(row.get("hard_exit_certified"), False, f"{key}.hard_exit_certified")
        observed_counts.add(row["count"])
    require_equal(len(observed_counts), 4, "independent 68/82/85/74 count universes")

    portfolio = universes["holdings_portfolio_rows"]
    require_equal(portfolio.get("typed_resolved_or_classified"), 62, "68-row typed/classified count")
    require_equal(portfolio.get("pending_identity_resolution"), 6, "68-row pending identity count")
    s103 = universes["phase_2_7_platform_framework_rows"]
    require_equal(s103.get("typed_resolved_or_classified"), 54, "74-row typed/classified count")
    require_equal(s103.get("unresolved_current_identity"), 20, "74-row unresolved identity count")

    article = data.get("articleization", {})
    require_equal(article.get("source_inventory_count"), 795, "article source inventory count")
    require_equal(article.get("source_inventory_verified"), True, "article source inventory verification")
    require_equal(article.get("stable_seed_schema_defined"), True, "article seed schema")
    require_equal(article.get("generator_in_repo"), True, "article manifest generator")
    for key in ARTICLE_OPEN_FIELDS:
        require_equal(article.get(key), False, f"articleization.{key}")
    require_equal(article.get("hard_exit_certified"), False, "articleization hard-exit certification")

    reconciliation = data.get("reconciliation", {})
    require_equal(
        reconciliation.get("retroactive_phase_2_0_through_2_9_lane"),
        "active_until_hard_exit",
        "retroactive reconciliation lane",
    )
    require_equal(reconciliation.get("explicit_deferral_ledger_complete"), False, "deferral ledger completion")
    require_equal(reconciliation.get("restricted_source_final_audit"), "pending", "restricted-source final audit")
    require_equal(
        reconciliation.get("continuity_recovery_final_reproducibility_audit"),
        "pending",
        "continuity/recovery final audit",
    )

    sequence = data.get("repository_security_sequence", {})
    require_equal(sequence.get("canonical_main_sha"), data.get("observed_main_sha"), "canonical/observed main SHA")
    require_equal(sequence.get("canonicalization_complete"), False, "canonicalization completion")
    require_equal(
        sequence.get("issue_83", {}).get("must_not_run_before_pr_64_canonical"),
        True,
        "PR #64 -> issue #83 sequence",
    )
    rls = sequence.get("pr_66_issue_79", {})
    require_equal(rls.get("critical_defense_in_depth_finding_resolved"), True, "integration-control RLS resolution")
    require_equal(rls.get("rls_enabled_on_all_six_tables"), True, "integration-control RLS table state")
    require_equal(rls.get("client_acl_denial_preserved"), True, "integration-control client ACL denial")
    require_equal(rls.get("service_role_smoke_passed"), True, "integration-control service-role smoke")
    require_equal(rls.get("supabase_security_advisor_lints"), 0, "Supabase security-advisor lints")
    require_equal(rls.get("machine_gate_state"), "passed", "integration-control machine gate")
    if "founder_authorized_D3" not in str(rls.get("production_mutation_authority", "")):
        fail("RLS production remediation must retain explicit founder D3 authority evidence")

    collab = data.get("collab_portal", {})
    require_equal(collab.get("state"), "fail_closed", "Collab Portal state")
    require_equal(collab.get("canonical_predicate_count"), 7, "Collab canonical predicate count")
    require_equal(collab.get("predicates_passed_count"), 4, "Collab passed predicate count")
    require_equal(
        collab.get("all_seven_certification_predicates_passed"),
        False,
        "Collab seven-predicate certification",
    )
    for key, expected in CANONICAL_COLLAB.items():
        require_equal(collab.get(key), expected, f"collab_portal.{key}")
    require_equal(collab.get("request_budget_august", {}).get("consumed"), 9, "Collab request count")
    require_equal(collab.get("request_budget_august", {}).get("limit"), 20000, "Collab request limit")
    require_equal(collab.get("private_fallback_tracking"), "active", "Collab fallback tracking")

    gates = data.get("open_hard_gates", [])
    gate_ids = [row.get("gate_id") for row in gates]
    if len(gates) < 8 or len(gate_ids) != len(set(gate_ids)):
        fail("hard-exit gate registry is incomplete or contains duplicate IDs")
    by_id = {row["gate_id"]: row for row in gates}
    require_equal(by_id["CT-P299-GATE-005"].get("state"), "pass", "RLS hard gate")
    require_equal(by_id["CT-P299-GATE-006"].get("state"), "not_met", "Collab hard gate")
    blocking_open = [row for row in gates if row.get("blocking") is True and row.get("state") != "pass"]
    require_equal(len(blocking_open), 7, "open blocking hard-exit gate count")

    hard_exit = data.get("hard_exit", {})
    require_equal(hard_exit.get("state"), "not_met", "Phase 2.99 hard exit")
    require_equal(hard_exit.get("blocking_gate_count"), 7, "hard-exit blocking gate count")
    require_equal(hard_exit.get("phase_2_complete"), False, "Phase 2 completion")
    require_equal(hard_exit.get("phase_3_entry_open"), False, "Phase 3 entry-open flag")
    require_equal(
        hard_exit.get("phase_3_entry"),
        "blocked_pending_phase_2_99_hard_exit",
        "Phase 3 entry state",
    )
    require_equal(hard_exit.get("final_certification_recorded"), False, "final certification")

    ladder = data.get("external_assessment_ladder", {})
    require_equal(ladder.get("authority"), "non_authoritative_progress_metric_only", "external assessment authority")
    require_equal(ladder.get("current_external_grade"), 97, "external grade observation")
    require_equal(ladder.get("current_external_letter_grade"), "A+", "external letter grade observation")
    require_equal(ladder.get("97_certification_reconciliation_program_operating"), "observed", "97 assessment meaning")
    for key in (
        "98_stable_id_provider_domain_api_export_identity_closure",
        "99_articleization_specialists_agents_collab_retroactive_final_reconciliation",
        "100_phase_2_99_hard_exit_certification",
    ):
        require_equal(ladder.get(key), "not_met", f"external ladder {key}")

    integration = data.get("integration", {})
    require_equal(
        integration.get("workflow_wiring_state"),
        "deferred_to_post_pr64_integration_packet",
        "workflow integration state",
    )
    require_equal(integration.get("rollback"), "revert_bounded_closure_ledger_packet", "rollback")

    if not check_files:
        return

    for rel in data.get("evidence_paths", []):
        if not (root / rel).is_file():
            fail(f"required evidence path missing: {rel}")

    phase = load_json(root / "developers/manifests/institutional-phase-namespace.v2.json")
    require_equal(phase.get("decision_id"), "CT-ADR-ROADMAP-010", "machine roadmap decision")
    require_equal(phase.get("top_level_phase_count"), 10, "machine top-level phase count")
    require_equal(phase.get("current_phase"), 2, "machine current phase")
    require_equal(phase.get("current_subphase"), "2.99", "machine current subphase")
    require_equal(
        phase.get("phase_3_entry"),
        "blocked_pending_phase_2_99_hard_exit",
        "machine Phase 3 gate",
    )
    superseded = phase.get("superseded_top_level_namespaces", [])
    if not any(
        row.get("source_pr") == 62 and "superseded" in row.get("disposition", "")
        for row in superseded
    ):
        fail("PR #62 five-phase snapshot must remain superseded lineage")

    article_text = (root / article["evidence_path"]).read_text(encoding="utf-8")
    for fragment in (
        "source_inventory_count: 795",
        "complete_machine_manifest_generated_in_repo: pending",
        "P0_P1_disposition_completion: pending",
    ):
        if fragment not in article_text:
            fail(f"articleization evidence missing current fragment: {fragment!r}")

    plan_text = (root / "changelog/phase-2-99-plan.mdx").read_text(encoding="utf-8")
    for fragment in ("## Exit criteria", "current hard-exit gate evaluates `pass`"):
        if fragment not in plan_text:
            fail(f"Phase 2.99 plan missing hard-exit fragment: {fragment!r}")


def expect_failure(data: dict, mutate, label: str) -> None:
    bad = copy.deepcopy(data)
    mutate(bad)
    try:
        validate(bad, ROOT, check_files=False)
    except ValueError:
        return
    raise AssertionError(f"{label} must fail")


def self_test(data: dict) -> None:
    validate(data, ROOT, check_files=False)
    expect_failure(data, lambda d: d["authority"].__setitem__("top_level_phase_count", 5), "five-phase promotion")
    expect_failure(data, lambda d: d["hard_exit"].__setitem__("phase_3_entry_open", True), "premature Phase 3")
    expect_failure(
        data,
        lambda d: d["macro_count_universes"]["holdings_domain_rows"].__setitem__("count", 68),
        "count-universe collapse",
    )
    expect_failure(
        data,
        lambda d: d["articleization"].__setitem__("terminal_disposition_assigned_795", True),
        "false articleization completion",
    )
    expect_failure(
        data,
        lambda d: d["collab_portal"].__setitem__("approved_field_map", "passed"),
        "false Collab completion",
    )
    expect_failure(
        data,
        lambda d: d["repository_security_sequence"]["pr_66_issue_79"].__setitem__("critical_defense_in_depth_finding_resolved", False),
        "stale RLS state",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    data = load_json(LEDGER)

    if args.self_test:
        self_test(data)
        print("Phase 2.99 closure-ledger self-test passed; stale RLS/Collab and false phase/count/article promotion remain blocked.")
        return 0

    validate(data, ROOT, check_files=True)
    open_count = sum(
        1 for row in data["open_hard_gates"]
        if row.get("blocking") is True and row.get("state") != "pass"
    )
    print("Phase 2.99 closure-ledger consistency validation: PASS")
    print(f"Open blocking hard-exit gates preserved: {open_count}")
    print("RLS defense-in-depth gate: PASS; Collab Portal: 4/7 canonical predicates PASS, fail-closed.")
    print("Institutional state: Phase 2 / 2.99; Phase 3 blocked_pending_phase_2_99_hard_exit.")
    print("Important: validator PASS != Phase 2.99 hard-exit PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
