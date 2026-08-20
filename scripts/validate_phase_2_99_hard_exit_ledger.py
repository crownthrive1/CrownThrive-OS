#!/usr/bin/env python3
"""Validate the Phase 2.99 hard-exit closure ledger v1.3.

PASS means the versioned ledger is internally coherent and fail-closed.
It does not mean Phase 2.99 hard exit has passed. Accepted governance
DEFERRED state remains explicitly distinct from technical PASS.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import datetime
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
VOLATILE_SNAPSHOT_SEMANTICS = "volatile_runtime_snapshot_not_ci_locked_counter"
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")


def fail(message: str) -> None:
    raise ValueError(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require_equal(actual, expected, label: str) -> None:
    if actual != expected:
        fail(f"{label} drifted: {actual!r} != {expected!r}")


def require_timestamp(value, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} is not valid ISO-8601: {value!r}") from exc
    if parsed.tzinfo is None:
        fail(f"{label} must include timezone information")


def require_nonnegative_int(value, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        fail(f"{label} must be a non-negative integer")


def require_sha40(value, label: str) -> None:
    if not isinstance(value, str) or not SHA40_RE.fullmatch(value):
        fail(f"{label} must be a 40-character lowercase commit SHA")


def validate(data: dict, root: Path, check_files: bool = True) -> None:
    require_equal(data.get("manifest_version"), "1.3.0", "manifest version")
    require_equal(data.get("observation_semantics"), "verification_baseline_snapshot_not_dynamic_post_merge_assertion", "observation semantics")
    require_timestamp(data.get("observed_at"), "observed_at")
    require_sha40(data.get("observed_main_sha"), "observed main SHA")

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

    for key in (
        "priority_not_lifecycle",
        "priority_not_implementation_state",
        "priority_not_institutional_disposition",
        "public_url_not_operational_proof",
        "sunset_preserves_history_ip_sources_domains_contracts",
    ):
        require_equal(data.get("dimension_separation", {}).get(key), True, f"dimension.{key}")

    universes = data.get("macro_count_universes", {})
    require_equal(set(universes), set(EXPECTED_COUNTS), "macro count-universe identities")
    require_equal(len({row.get("count") for row in universes.values()}), 4, "independent count universes")
    for key, count in EXPECTED_COUNTS.items():
        row = universes[key]
        require_equal(row.get("count"), count, f"{key}.count")
        require_equal(row.get("source_count_state"), "certified", f"{key}.source_count_state")
        require_equal(row.get("hard_exit_certified"), False, f"{key}.hard_exit_certified")
    require_equal(universes["holdings_portfolio_rows"].get("typed_resolved_or_classified"), 62, "68 typed")
    require_equal(universes["holdings_portfolio_rows"].get("pending_identity_resolution"), 6, "68 pending")
    require_equal(universes["phase_2_7_platform_framework_rows"].get("typed_resolved_or_classified"), 54, "74 typed")
    require_equal(universes["phase_2_7_platform_framework_rows"].get("unresolved_current_identity"), 20, "74 unresolved")

    article = data.get("articleization", {})
    require_equal(article.get("source_inventory_count"), 795, "article inventory")
    require_equal(article.get("source_inventory_verified"), True, "article inventory verified")
    require_equal(article.get("stable_seed_schema_defined"), True, "article seed")
    require_equal(article.get("generator_in_repo"), True, "article generator")
    for key in ARTICLE_OPEN_FIELDS:
        require_equal(article.get(key), False, f"articleization.{key}")
    require_equal(article.get("hard_exit_certified"), False, "article hard exit")
    candidate = article.get("noncanonical_candidate", {})
    require_equal(candidate.get("pr"), 91, "article candidate PR")
    require_equal(candidate.get("state"), "deterministic_795_title_hierarchy_manifest_candidate_only", "article candidate state")
    require_sha40(candidate.get("exact_head"), "article candidate head")

    reconciliation = data.get("reconciliation", {})
    require_equal(reconciliation.get("retroactive_phase_2_0_through_2_9_lane"), "active_until_hard_exit", "retroactive lane")
    require_equal(reconciliation.get("explicit_deferral_ledger_complete"), False, "deferral ledger")
    require_equal(reconciliation.get("restricted_source_final_audit"), "pending", "restricted-source audit")
    require_equal(reconciliation.get("continuity_recovery_final_reproducibility_audit"), "pending", "recovery audit")
    require_nonnegative_int(reconciliation.get("approved_deferral_count_snapshot"), "approved deferral count")

    tags = reconciliation.get("reconciliation_tag_snapshot", {})
    require_timestamp(tags.get("observed_at"), "tag snapshot observed_at")
    for key in ("total", "pass", "open", "blocked", "closed", "deferred", "authoritative", "scan_required", "reconcile_required"):
        require_nonnegative_int(tags.get(key), f"tag snapshot {key}")
    require_equal(tags["pass"] + tags["open"] + tags["blocked"] + tags["closed"] + tags["deferred"], tags["total"], "tag state arithmetic")
    require_equal(tags.get("authoritative"), tags["total"], "all reconciliation tags authoritative")
    require_equal(tags.get("scan_required"), tags["total"], "all reconciliation tags scan-required")
    require_equal(tags.get("reconcile_required"), tags["total"], "all reconciliation tags reconcile-required")
    require_equal(tags.get("pass_remains_drift_watched"), True, "PASS drift watch")
    require_equal(tags.get("deferral_is_not_pass"), True, "DEFERRAL not PASS")
    require_equal(tags.get("unknown_never_becomes_zero_or_pass"), True, "UNKNOWN semantics")

    scan = reconciliation.get("latest_reconciliation_scan", {})
    require_equal(scan.get("scanner_id"), "ct.reconciliation.lmno.agent-e", "latest scanner")
    require_equal(scan.get("status"), "partial", "latest reconciliation scan state")
    for key in ("tagged_scopes", "reconciled_scopes", "drift_scopes", "unresolved_scopes"):
        require_nonnegative_int(scan.get(key), f"latest scan {key}")
    require_equal(scan.get("tagged_scopes"), tags["total"], "scan/tag total")
    require_equal(scan.get("reconciled_scopes"), tags["total"], "scan reconciled total")
    if scan.get("unresolved_scopes", 0) <= 0:
        fail("latest reconciliation scan must preserve unresolved scopes while hard exit remains incomplete")
    require_timestamp(scan.get("completed_at"), "latest reconciliation scan completed_at")

    sequence = data.get("repository_security_sequence", {})
    require_equal(sequence.get("verification_baseline_main_sha"), data.get("observed_main_sha"), "repository baseline")
    require_equal(sequence.get("canonicalization_complete"), True, "repository canonicalization")
    require_equal(sequence.get("github_role"), "technical_defense_in_depth_not_sovereign_authority", "GitHub role")
    for key in ("pr_64", "pr_95", "pr_65", "pr_117", "pr_119"):
        require_equal(sequence.get(key, {}).get("state"), "merged_canonical", f"{key} state")
        require_sha40(sequence.get(key, {}).get("merge_sha"), f"{key} merge SHA")
    require_equal(sequence.get("issue_83", {}).get("state"), "closed_completed", "issue83 state")
    require_equal(sequence.get("issue_83", {}).get("behavioral_negative_proof_pr"), 93, "issue83 negative proof")
    require_equal(sequence["pr_119"]["merge_sha"], data.get("observed_main_sha"), "current main matches PR119")

    rls = sequence.get("pr_66_issue_79", {})
    require_equal(rls.get("issue_79_state"), "closed_completed", "issue79 state")
    require_equal(rls.get("critical_defense_in_depth_finding_resolved"), True, "RLS resolution")
    require_equal(rls.get("rls_enabled_on_all_six_tables"), True, "original six-table RLS remediation")
    require_equal(rls.get("original_remediation_table_count"), 6, "original RLS remediation table count")
    require_nonnegative_int(rls.get("current_integration_control_table_count"), "current integration-control table count")
    if rls["current_integration_control_table_count"] < rls["original_remediation_table_count"]:
        fail("current integration-control estate cannot be smaller than the preserved original remediation estate")
    require_nonnegative_int(rls.get("current_rls_policy_count"), "current RLS policy count")
    require_equal(rls.get("current_rls_policy_count"), rls.get("current_integration_control_table_count"), "one current RLS policy per current table")
    require_equal(rls.get("current_force_rls_enabled"), False, "current FORCE RLS state")
    require_timestamp(rls.get("current_snapshot_observed_at"), "RLS current snapshot observed_at")
    require_equal(rls.get("rls_enabled_on_all_current_tables"), True, "current RLS estate")
    require_equal(rls.get("client_acl_denial_preserved"), True, "RLS client denial")
    require_equal(rls.get("service_role_smoke_passed"), True, "RLS service smoke")
    require_equal(rls.get("supabase_security_advisor_lints"), 0, "security advisor")
    require_equal(rls.get("machine_gate_state"), "passed", "RLS machine gate")
    if "founder_authorized_D3" not in str(rls.get("production_mutation_authority", "")):
        fail("RLS remediation must retain founder-authorized D3 evidence")

    collab = data.get("collab_portal", {})
    require_equal(collab.get("state"), "fail_closed_deferred_point_of_use", "Collab state")
    require_equal(collab.get("canonical_predicate_count"), 7, "Collab predicate count")
    require_equal(collab.get("predicates_passed_count"), 6, "Collab passed count")
    require_equal(collab.get("all_seven_certification_predicates_passed"), False, "Collab all seven")
    for key in ("credential_exact_match", "project_meta_authenticated", "institutional_project_uid", "approved_field_map", "authenticated_project_read", "bounded_write_readback"):
        require_equal(collab.get(key), "passed", f"collab.{key}")
    require_equal(collab.get("webhook_sender_delivery_integrity"), "governed_deferred_not_passed", "Collab webhook disposition")
    require_equal(collab.get("technical_webhook_delivery_state"), "unproven", "Collab technical delivery")
    require_equal(collab.get("hard_exit_blocking_effect"), "deferred_accepted_by_explicit_founder_override", "Collab hard-exit effect")
    require_equal(collab.get("deferral_id"), "CT-DEF-GATE006-OVERRIDE-001", "Collab deferral ID")
    if "GitHub #120" not in str(collab.get("deferral_authority", "")):
        fail("Collab deferral must retain explicit founder #120 authority")
    if not str(collab.get("mandatory_reopen_trigger", "")).strip():
        fail("Collab deferral must retain a mandatory point-of-use reopen trigger")
    require_equal(collab.get("private_fallback_tracking"), "active", "Collab fallback tracking")
    collab_budget = collab.get("request_budget_august", {})
    require_nonnegative_int(collab_budget.get("consumed"), "Collab request snapshot")
    require_nonnegative_int(collab_budget.get("limit"), "Collab request limit")
    if collab_budget["limit"] <= 0 or collab_budget["consumed"] > collab_budget["limit"]:
        fail("Collab request snapshot must remain within a positive configured limit")
    require_equal(collab_budget.get("period_start"), "2026-08-01", "Collab request period")
    require_timestamp(collab_budget.get("observed_at"), "Collab request snapshot observed_at")
    require_equal(collab_budget.get("semantics"), VOLATILE_SNAPSHOT_SEMANTICS, "Collab request snapshot semantics")

    delivery = data.get("provider_delivery_deferrals", {})
    require_equal(set(delivery), {"collab_portal", "partnero", "stripe"}, "provider delivery deferral set")
    expected_ids = {
        "collab_portal": "CT-DEF-GATE006-OVERRIDE-001",
        "partnero": "CT-DEF-WEBHOOK-PARTNERO-001",
        "stripe": "CT-DEF-WEBHOOK-STRIPE-001",
    }
    for service, deferral_id in expected_ids.items():
        row = delivery[service]
        require_equal(row.get("deferral_id"), deferral_id, f"{service} deferral ID")
        require_equal(row.get("technical_state"), "unproven", f"{service} technical delivery")
        require_equal(row.get("blocking_effect"), "deferred_accepted_point_of_use", f"{service} blocking effect")
        require_equal(row.get("technical_pass_claimed"), False, f"{service} technical PASS claim")
        if not str(row.get("reopen_trigger", "")).strip():
            fail(f"{service} deferral must retain a non-empty reopen trigger")

    api = data.get("api_mcp_runtime_closure", {})
    io_state = api.get("crownthrive_io", {})
    require_equal(io_state.get("state"), "read_verified_write_closed", "IO state")
    require_nonnegative_int(io_state.get("august_request_count_observed"), "IO request snapshot")
    require_equal(io_state.get("request_period_start"), "2026-08-01", "IO request period")
    require_timestamp(io_state.get("request_count_observed_at"), "IO request snapshot observed_at")
    require_equal(io_state.get("request_count_semantics"), VOLATILE_SNAPSHOT_SEMANTICS, "IO request snapshot semantics")
    require_equal(io_state.get("monthly_request_budget_ceiling"), "passed_founder_unlimited_policy", "IO monthly request ceiling")
    require_equal(io_state.get("scheduled_health_probe_budget_policy"), "passed", "IO scheduled health budget policy")
    api_control = api.get("crownthrive_api_control", {})
    require_equal(api_control.get("write_gate"), False, "API write gate")
    require_equal(api_control.get("hard_exit_certified"), False, "API hard exit")
    require_nonnegative_int(api_control.get("august_request_count_observed"), "API request snapshot")
    require_timestamp(api_control.get("request_count_observed_at"), "API request snapshot observed_at")
    require_equal(api_control.get("request_count_semantics"), VOLATILE_SNAPSHOT_SEMANTICS, "API request snapshot semantics")
    open_acceptance = api.get("open_acceptance_items", [])
    if not open_acceptance:
        fail("API/MCP open acceptance items must remain explicit while hard exit is incomplete")
    for closed_item in ("monthly_request_budget_ceiling", "scheduled_health_probe_budget_policy"):
        if closed_item in open_acceptance:
            fail(f"closed IO acceptance item remains incorrectly open: {closed_item}")

    gates = data.get("open_hard_gates", [])
    require_equal(len(gates), 8, "hard-gate registry count")
    by_id = {row.get("gate_id"): row for row in gates}
    require_equal(len(by_id), 8, "unique hard-gate IDs")
    require_equal(by_id["CT-P299-GATE-004"].get("state"), "pass", "repository canonicalization gate")
    require_equal(by_id["CT-P299-GATE-005"].get("state"), "pass", "RLS gate")
    gate6 = by_id["CT-P299-GATE-006"]
    require_equal(gate6.get("state"), "deferred_accepted_not_passed", "Collab gate disposition")
    require_equal(gate6.get("blocking"), False, "Collab gate blocking effect")
    require_equal(gate6.get("progress"), "6_of_7_passed", "Collab gate progress")
    require_equal(gate6.get("deferral_id"), "CT-DEF-GATE006-OVERRIDE-001", "Collab gate deferral")
    require_equal(gate6.get("technical_state"), "unproven", "Collab gate technical state")
    if not str(gate6.get("reopen_trigger", "")).strip():
        fail("GATE-006 deferred disposition must preserve point-of-use reopen trigger")
    require_equal(by_id["CT-P299-GATE-008"].get("state"), "not_met", "GATE-008 fail closed")
    require_equal(by_id["CT-P299-GATE-008"].get("blocking"), True, "GATE-008 blocking")
    open_blocking = [row for row in gates if row.get("blocking") is True and row.get("state") != "pass"]
    require_equal(len(open_blocking), 5, "open blocking gate count")
    deferred_not_passed = [row for row in gates if str(row.get("state", "")).startswith("deferred_")]
    require_equal(len(deferred_not_passed), 1, "deferred-not-pass gate count")

    hard_exit = data.get("hard_exit", {})
    require_equal(hard_exit.get("state"), "not_met", "hard exit")
    require_equal(hard_exit.get("blocking_gate_count"), 5, "hard-exit blocker count")
    require_equal(hard_exit.get("deferred_not_passed_gate_count"), 1, "hard-exit deferred count")
    require_equal(hard_exit.get("phase_2_complete"), False, "Phase2 complete")
    require_equal(hard_exit.get("phase_3_entry_open"), False, "Phase3 open")
    require_equal(hard_exit.get("phase_3_entry"), "blocked_pending_phase_2_99_hard_exit", "Phase3 state")
    require_equal(hard_exit.get("final_certification_recorded"), False, "final certification")
    require_equal(hard_exit.get("gate_008_fail_closed_while_upstream_unresolved"), True, "GATE-008 upstream fail-closed rule")

    ladder = data.get("external_assessment_ladder", {})
    require_equal(ladder.get("authority"), "non_authoritative_progress_metric_only", "external ladder authority")
    require_equal(ladder.get("observation_semantics"), "volatile_non_authoritative_snapshot", "external ladder observation semantics")
    require_timestamp(ladder.get("observed_at"), "external assessment observed_at")
    require_equal(ladder.get("hard_exit_decision_input"), False, "external assessment hard-exit authority")
    grade = ladder.get("current_external_grade")
    if grade is not None and (isinstance(grade, bool) or not isinstance(grade, (int, float)) or not 0 <= grade <= 100):
        fail("external grade, when present, must be numeric in the range 0..100")
    letter = ladder.get("current_external_letter_grade")
    if letter is not None and (not isinstance(letter, str) or not letter.strip() or len(letter.strip()) > 4):
        fail("external letter grade, when present, must be a short non-empty string")
    for key in (
        "98_stable_id_provider_domain_api_export_identity_closure",
        "99_articleization_specialists_agents_collab_retroactive_final_reconciliation",
        "100_phase_2_99_hard_exit_certification",
    ):
        require_equal(ladder.get(key), "not_met", f"external ladder {key}")

    integration = data.get("integration", {})
    require_equal(integration.get("workflow_wiring_state"), "active_governed_ci", "workflow state")
    require_equal(integration.get("workflow_path"), ".github/workflows/phase-2-99-hard-exit-ledger.yml", "workflow path")
    require_equal(integration.get("rollback"), "revert_bounded_closure_ledger_packet", "rollback")

    if not check_files:
        return

    for rel in data.get("evidence_paths", []) + [integration["workflow_path"]]:
        if not (root / rel).is_file():
            fail(f"required evidence path missing: {rel}")

    phase = load_json(root / "developers/manifests/institutional-phase-namespace.v2.json")
    require_equal(phase.get("decision_id"), "CT-ADR-ROADMAP-010", "machine roadmap")
    require_equal(phase.get("top_level_phase_count"), 10, "machine phase count")
    require_equal(phase.get("current_phase"), 2, "machine current phase")
    require_equal(phase.get("current_subphase"), "2.99", "machine subphase")
    require_equal(phase.get("phase_3_entry"), "blocked_pending_phase_2_99_hard_exit", "machine Phase3")
    if not any(row.get("source_pr") == 62 and "superseded" in row.get("disposition", "") for row in phase.get("superseded_top_level_namespaces", [])):
        fail("PR #62 five-phase snapshot must remain superseded lineage")

    article_text = (root / article["evidence_path"]).read_text(encoding="utf-8")
    for fragment in ("source_inventory_count: 795", "P0_P1_disposition_completion: pending"):
        if fragment not in article_text:
            fail(f"article evidence missing: {fragment!r}")

    plan_text = (root / "changelog/phase-2-99-plan.mdx").read_text(encoding="utf-8")
    for fragment in ("## Exit criteria", "current hard-exit gate evaluates `pass`"):
        if fragment not in plan_text:
            fail(f"Phase 2.99 plan missing: {fragment!r}")


def expect_failure(data: dict, mutate, label: str) -> None:
    bad = copy.deepcopy(data)
    mutate(bad)
    try:
        validate(bad, ROOT, check_files=False)
    except ValueError:
        return
    raise AssertionError(f"{label} must fail")


def expect_success(data: dict, mutate, label: str) -> None:
    candidate = copy.deepcopy(data)
    mutate(candidate)
    try:
        validate(candidate, ROOT, check_files=False)
    except ValueError as exc:
        raise AssertionError(f"{label} must remain valid: {exc}") from exc


def self_test(data: dict) -> None:
    validate(data, ROOT, check_files=False)
    expect_failure(data, lambda d: d["authority"].__setitem__("top_level_phase_count", 5), "five-phase promotion")
    expect_failure(data, lambda d: d["hard_exit"].__setitem__("phase_3_entry_open", True), "premature Phase3")
    expect_failure(data, lambda d: d["macro_count_universes"]["holdings_domain_rows"].__setitem__("count", 68), "count collapse")
    expect_failure(data, lambda d: d["articleization"].__setitem__("terminal_disposition_assigned_795", True), "false article completion")
    expect_failure(data, lambda d: d["reconciliation"]["reconciliation_tag_snapshot"].__setitem__("total", 169), "reconciliation tag arithmetic drift")
    expect_failure(data, lambda d: d["reconciliation"]["reconciliation_tag_snapshot"].__setitem__("deferral_is_not_pass", False), "deferral promoted by tag semantics")
    expect_failure(data, lambda d: d["collab_portal"].__setitem__("all_seven_certification_predicates_passed", True), "false Collab 7/7")
    expect_failure(data, lambda d: d["collab_portal"].__setitem__("technical_webhook_delivery_state", "passed"), "deferred delivery promoted to technical pass")
    expect_failure(data, lambda d: d["provider_delivery_deferrals"]["stripe"].__setitem__("technical_pass_claimed", True), "provider deferral promoted to pass")
    expect_failure(data, lambda d: d["open_hard_gates"][5].__setitem__("state", "pass"), "GATE-006 falsely promoted to pass")
    expect_failure(data, lambda d: d["open_hard_gates"][5].__setitem__("reopen_trigger", ""), "GATE-006 missing reopen trigger")
    expect_failure(data, lambda d: d["open_hard_gates"][7].__setitem__("state", "pass"), "premature GATE-008")
    expect_failure(data, lambda d: d["repository_security_sequence"].__setitem__("canonicalization_complete", False), "repository regression")
    expect_failure(data, lambda d: d["repository_security_sequence"]["pr_66_issue_79"].__setitem__("rls_enabled_on_all_current_tables", False), "RLS regression")
    expect_failure(data, lambda d: d["repository_security_sequence"]["pr_66_issue_79"].__setitem__("current_rls_policy_count", 14), "RLS policy/table mismatch")
    expect_failure(data, lambda d: d["collab_portal"]["request_budget_august"].__setitem__("consumed", -1), "negative Collab snapshot")
    expect_failure(data, lambda d: d["api_mcp_runtime_closure"]["crownthrive_io"].__setitem__("request_count_observed_at", "not-a-timestamp"), "invalid IO snapshot timestamp")
    expect_failure(data, lambda d: d["external_assessment_ladder"].__setitem__("hard_exit_decision_input", True), "external assessment authority escalation")
    expect_failure(data, lambda d: d["external_assessment_ladder"].__setitem__("current_external_grade", 101), "external grade range")
    expect_success(data, lambda d: d["external_assessment_ladder"].update({"current_external_grade": 96, "current_external_letter_grade": "A"}), "external regrade is non-authoritative")
    expect_success(data, lambda d: d["api_mcp_runtime_closure"]["crownthrive_io"].__setitem__("august_request_count_observed", 42), "IO request counter is a volatile snapshot")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    data = load_json(LEDGER)
    if args.self_test:
        self_test(data)
        print("Phase 2.99 closure-ledger v1.3 self-test passed; deferred webhook proof remains NOT-PASS, GATE-008 stays fail-closed, and false phase/count/article/RLS promotion is blocked.")
        return 0
    validate(data, ROOT, check_files=True)
    blocking = sum(1 for row in data["open_hard_gates"] if row.get("blocking") is True and row.get("state") != "pass")
    deferred = sum(1 for row in data["open_hard_gates"] if str(row.get("state", "")).startswith("deferred_"))
    print("Phase 2.99 closure-ledger v1.3 consistency validation: PASS")
    print(f"Open blocking hard-exit gates preserved: {blocking}")
    print(f"Governed deferred / technically NOT-PASS gates: {deferred}")
    print("Repository canonicalization: PASS; RLS defense-in-depth: PASS; Collab: 6/7 technical with point-of-use deferral, not 7/7 PASS.")
    print("Institutional state: Phase 2 / 2.99; Phase 3 blocked_pending_phase_2_99_hard_exit.")
    print("Important: validator PASS != Phase 2.99 hard-exit PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
