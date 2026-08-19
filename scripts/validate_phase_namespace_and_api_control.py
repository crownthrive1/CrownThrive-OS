#!/usr/bin/env python3
"""Validate the ten-phase namespace and sanitized API/MCP control-plane evidence.

S107 is immutable historical evidence. Current-state validation is performed only
against the separately designated current sanitized snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PHASE_MANIFEST = ROOT / "developers/manifests/institutional-phase-namespace.v2.json"
HISTORICAL_API_MANIFEST = ROOT / "developers/manifests/api-mcp-control-plane-state.v1.json"
CURRENT_API_MANIFEST = ROOT / "developers/manifests/api-mcp-current-control-state.v1.json"
CHECKPOINT = ROOT / "changelog/phase-2-99-five-phase-api-mcp-control-plane-checkpoint.md"
GOVERNANCE_ADR = ROOT / "changelog/adr-agent-sovereign-governance-quorum-security.md"

EXPECTED_PHASES = [
    "Institutional Mapping",
    "Institutional Recovery, Reconciliation & Documentation",
    "Executable Institutional Core",
    "Federated Ecosystem Activation",
    "Revenue & Market Activation",
    "Licensing, IP & Developer Economy",
    "Physical, Phygital & Regional Expansion",
    "Holdings, Capital & Portfolio Scale",
    "Advanced CHLOM & Interoperable Infrastructure",
    "Generational Continuity, Sovereign Scale & Institutional Permanence",
]

FORBIDDEN_RAW_CREDENTIAL_KEYS = {
    "secret",
    "secret_key",
    "api_key",
    "authorization",
    "bearer_token",
    "access_token",
    "refresh_token",
    "public_id",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise AssertionError(f"Expected object in {path.relative_to(ROOT)}")
    return value


def walk_forbidden_keys(value: Any, trail: tuple[str, ...] = ()) -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_RAW_CREDENTIAL_KEYS:
                findings.append(".".join((*trail, str(key))))
            findings.extend(walk_forbidden_keys(child, (*trail, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(walk_forbidden_keys(child, (*trail, str(index))))
    return findings


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_phase_namespace(data: dict[str, Any]) -> None:
    require(data.get("state") == "current", "Phase namespace must be current")
    require(data.get("decision_id") == "CT-ADR-ROADMAP-010", "Ten-phase roadmap decision ID must remain CT-ADR-ROADMAP-010")
    require(data.get("top_level_phase_count") == 10, "Exactly ten top-level institutional phases are required")
    phases = data.get("phases")
    require(isinstance(phases, list) and len(phases) == 10, "Phase manifest must contain ten phase records")
    require([row.get("number") for row in phases] == list(range(1, 11)), "Phase numbers must be 1 through 10")
    require([row.get("name") for row in phases] == EXPECTED_PHASES, "Phase names do not match ten_phase_v1")
    require(data.get("current_phase") == 2, "Current institutional phase must remain Phase 2")
    require(data.get("current_subphase") == "2.99", "Current institutional subphase must remain 2.99")
    require(data.get("phase_3_entry") == "blocked_pending_phase_2_99_hard_exit", "Phase 3 must remain blocked")

    rules = data.get("rules", {})
    require(rules.get("future_phase_propagation_scope") == list(range(3, 11)), "Future propagation must cover Phases 3-10")
    require(rules.get("historical_phase_records_preserved") is True, "Historical phase records must be preserved")
    require(rules.get("retroactive_renumbering_prohibited") is True, "Retroactive renumbering must remain prohibited")
    require(rules.get("phase_3_may_start_before_phase_2_99_hard_exit") is False, "Phase 3 may not start before the Phase 2.99 hard exit")
    require(rules.get("future_roadmap_is_fluid") is True, "Future roadmap must remain fluid")
    require(rules.get("material_pass_must_reconcile_downstream_impacts") is True, "Material passes must reconcile downstream impacts")

    superseded = data.get("superseded_top_level_namespaces", [])
    five_phase_snapshot = next((row for row in superseded if row.get("namespace") == "five_phase_v2_2026_08_19_transient_machine_snapshot"), None)
    require(five_phase_snapshot is not None, "PR #62 five-phase machine snapshot must be preserved as superseded lineage")
    require(five_phase_snapshot.get("disposition") == "superseded_during_concurrency_reconciliation", "Five-phase transient snapshot disposition drifted")
    require(five_phase_snapshot.get("preserve_history") is True, "Five-phase transient history must be preserved")
    require(data.get("documentation_reconciliation", {}).get("state") == "docs_updated", "Namespace conflict must remain reconciled")


def validate_historical_api_snapshot(data: dict[str, Any]) -> None:
    require(data.get("manifest_id") == "ct.manifest.api-mcp-control-plane-state.v1", "Historical API snapshot ID drifted")
    require(data.get("evidence_id") == "S107", "S107 historical evidence ID must be preserved")
    require(data.get("source_class") == "historical_operational_control_plane_snapshot", "S107 may not be labeled current")
    require(data.get("snapshot_state") == "superseded_historical_evidence", "S107 must remain superseded historical evidence")
    require(data.get("superseded_by") == "ct.manifest.api-mcp-current-control-state.v1", "S107 must point to the designated-current manifest")
    require(data.get("may_satisfy_current_state_validation") is False, "S107 must never satisfy a current-state gate")
    phase = data.get("phase", {})
    require(phase.get("current_phase") == 2 and phase.get("current_subphase") == "2.99", "Historical snapshot phase lineage drifted")
    require(phase.get("phase_3_entry") == "blocked_pending_phase_2_99_hard_exit", "Historical evidence must not advance Phase 3")
    require(not walk_forbidden_keys(data), "Historical snapshot contains prohibited raw credential-shaped field names")


def validate_current_api_control(data: dict[str, Any]) -> None:
    require(data.get("manifest_id") == "ct.manifest.api-mcp-current-control-state.v1", "Only the designated-current API/MCP manifest may satisfy current-state validation")
    require(data.get("evidence_class") == "designated_current_sanitized_control_plane_snapshot", "Current API/MCP evidence class is not designated-current")
    require(data.get("historical_snapshots_may_satisfy_current_validation") is False, "Historical snapshots must remain excluded from current-state validation")
    require("S107" in data.get("supersedes_for_current_validation", []), "Current snapshot must explicitly supersede S107 for current validation")

    phase = data.get("phase", {})
    require(phase.get("current_phase") == 2 and phase.get("current_subphase") == "2.99", "Current API snapshot must remain scoped to Phase 2 / 2.99")
    require(phase.get("phase_3_entry") == "blocked_pending_phase_2_99_hard_exit", "Current API evidence must not advance Phase 3")

    security = data.get("security_boundary", {})
    require(security.get("integration_control_base_tables") == 12, "Current integration_control base-table count must be 12")
    require(security.get("rls_enabled_tables") == 12, "All current integration_control base tables must have RLS enabled")
    require(security.get("force_rls_tables") == 0, "FORCE RLS is not part of the current certified boundary")
    require(security.get("tables_with_explicit_policy") == 12, "Every current integration_control base table must have an explicit policy")
    require(security.get("policies_service_role_only") is True, "Current integration_control policies must remain service-role only")
    require(security.get("anon_authenticated_table_crud_observed") is False, "Anon/authenticated CRUD exposure must not be observed")
    require(security.get("security_advisor_lint_count") == 0, "Current Supabase Security Advisor must remain clean in the designated snapshot")

    control = data.get("crownthrive_api_control", {})
    require(control.get("runtime_version") == 3, "Current crownthrive-api-control runtime must be v3")
    require(control.get("runtime_state") == "active", "Current crownthrive-api-control runtime must be active")
    require(control.get("jwt_auth") == "passed", "API control JWT gate must remain passed")
    require(control.get("admin_authorization") == "required", "API control must retain admin authorization")
    require(control.get("mcp_protocol_target") == "2026-07-28", "MCP protocol target must remain 2026-07-28")
    require(control.get("mcp_full_contract") == "open", "Full MCP conformance must remain open until the outstanding protocol/runtime gates pass")
    require(control.get("mcp_registered_tools") == 32 and control.get("mcp_enabled_tools") == 20, "Current MCP registry counts drifted")
    require(control.get("mcp_enabled_mutations") == 0, "No MCP mutation may be enabled")
    require(control.get("provider_writes_enabled") is False and control.get("provider_write_gate") == "closed", "API provider writes must remain closed")
    require(control.get("external_client_conformance_test") == "open", "External MCP client conformance must remain open")

    io_state = data.get("crownthrive_io", {})
    require(io_state.get("credential_state") == "verified", "CrownThrive IO credential state must be verified")
    require(io_state.get("integration_state") == "read_verified", "CrownThrive IO must remain read_verified")
    require(io_state.get("write_operations") == "closed" and io_state.get("provider_writes_enabled") is False, "CrownThrive IO writes must remain closed")
    require(isinstance(io_state.get("observed_request_count"), int) and io_state.get("observed_request_count") >= 0, "CrownThrive IO request count must be a nonnegative observation")
    require(io_state.get("request_counter_semantics") == "telemetry_not_monthly_exhaustion_authority", "CrownThrive IO counter semantics must remain telemetry-only under founder unlimited policy")
    require(io_state.get("monthly_request_budget_ceiling") == "passed_founder_unlimited_policy", "CrownThrive IO monthly call policy must reflect founder unlimited policy")
    require(io_state.get("scheduled_health_probe_budget_policy") == "passed_founder_unlimited_policy", "CrownThrive IO scheduled-probe budget policy must reflect founder unlimited policy")

    seo = data.get("thrivetools_seo", {})
    require(seo.get("credential_state") == "verified" and seo.get("integration_state") == "read_verified", "ThriveTools SEO must remain credential-verified/read-verified")
    require(seo.get("credential_vault_binding") == "passed" and seo.get("authenticated_read") == "passed" and seo.get("mcp_adapter") == "passed", "ThriveTools SEO certified read path must remain passed")
    require(seo.get("provider_writes_enabled") is False and seo.get("provider_write_gate") == "closed", "ThriveTools SEO writes must remain closed")
    require(seo.get("monthly_request_budget_ceiling") == "passed_founder_unlimited_policy", "ThriveTools SEO monthly call policy must reflect founder unlimited policy")
    require(seo.get("scheduled_health_probe_budget_policy") == "passed_founder_unlimited_policy", "ThriveTools SEO scheduled-probe budget policy must reflect founder unlimited policy")
    require(seo.get("scheduled_health_probe_policy") == "open", "ThriveTools SEO SRE probe semantics must remain explicitly open")
    require(seo.get("endpoint_path_reconciliation") == "open" and seo.get("external_mcp_client_conformance") == "open", "ThriveTools SEO unresolved path/external-client gates must remain open")

    collab = data.get("collab_portal", {})
    require(collab.get("credential_state") == "verified" and collab.get("integration_state") == "read_verified", "Collab must remain credential-verified/read-verified")
    require(collab.get("provider_writes_enabled") is False and collab.get("write_gate") is False, "Collab general write authority must remain disabled")
    cert = collab.get("canonical_certification", {})
    require(cert.get("passed_predicates") == 6 and cert.get("required_predicates") == 7 and cert.get("state") == "fail_closed", "Collab canonical certification must remain 6/7 fail-closed")
    require(cert.get("credential_binding") == "passed", "Collab credential binding must remain passed")
    require(cert.get("authenticated_project_metadata") == "passed", "Collab authenticated metadata must remain passed")
    require(cert.get("institutional_project_uid") == "passed", "Collab institutional UID must remain passed")
    require(cert.get("authenticated_project_read") == "passed", "Collab project read must remain passed")
    require(cert.get("approved_field_map") == "passed", "Collab approved field map must remain passed")
    require(cert.get("bounded_write_readback") == "passed", "Collab bounded write/readback certification must remain passed")
    require(cert.get("webhook_sender_delivery_integrity") == "blocked", "Collab sender/delivery integrity must remain blocked until real provider delivery is proven")
    require(collab.get("live_provider_sender_delivery") == "unproven" and collab.get("event_driven_sync") == "closed", "Collab event-driven sync must remain fail-closed")

    reward = data.get("reward_loyalty", {})
    require(reward.get("current_production_major") == 4, "Reward Loyalty production must remain v4 absent deployment evidence")
    require(reward.get("vendor_target_reference") == "5.27.0" and reward.get("vendor_target_is_deployment_evidence") is False, "Reward Loyalty v5.27.0 must remain target/reference only")
    require(reward.get("v5_production_deployment") == "blocked_no_deployment_evidence", "Reward Loyalty v5 production deployment must remain blocked")
    require(reward.get("provider_writes_enabled") is False and reward.get("provider_write_gate") == "closed", "Reward Loyalty provider writes must remain closed")
    require(reward.get("partnero_is_separate_engine") is True and reward.get("adluxe_is_separate_network") is True, "Reward Loyalty/Partnero/AdLuxe boundaries must remain explicit")

    secret_state = data.get("secret_handling", {})
    require(secret_state and all(value is False for value in secret_state.values()), "Secret/fingerprint exposure flags must all remain false")
    authority = data.get("authority", {})
    require(authority.get("snapshot_is_observational") is True and authority.get("snapshot_is_not_sovereign_vote") is True, "Current snapshot must remain observational and non-sovereign")
    require(authority.get("snapshot_cannot_enable_provider_writes") is True and authority.get("snapshot_cannot_advance_phase_3") is True, "Current snapshot may not create write or phase authority")

    forbidden = walk_forbidden_keys(data)
    require(not forbidden, "Raw credential-shaped field names are prohibited in public-safe manifest: " + ", ".join(forbidden))
    require(data.get("docs_impact", {}).get("state") == "docs_updated", "Current API/MCP state must reconcile documentation impact")


def test_superseded_evidence_rejected(historical: dict[str, Any]) -> None:
    """TEVV: historical S107 can never be reused as designated-current evidence."""
    try:
        validate_current_api_control(historical)
    except AssertionError:
        return
    raise AssertionError("ct.tevv.control-state.current-snapshot-superseded-evidence-rejected failed: historical S107 was accepted as current")


def main() -> int:
    for path in (PHASE_MANIFEST, HISTORICAL_API_MANIFEST, CURRENT_API_MANIFEST, CHECKPOINT, GOVERNANCE_ADR):
        require(path.is_file(), f"Missing {path.relative_to(ROOT)}")

    phase_data = load_json(PHASE_MANIFEST)
    historical_api = load_json(HISTORICAL_API_MANIFEST)
    current_api = load_json(CURRENT_API_MANIFEST)
    validate_phase_namespace(phase_data)
    validate_historical_api_snapshot(historical_api)
    validate_current_api_control(current_api)
    test_superseded_evidence_rejected(historical_api)

    checkpoint = CHECKPOINT.read_text(encoding="utf-8")
    require("PR #62 five-phase machine assertion is superseded" in checkpoint, "Checkpoint must preserve and supersede the transient five-phase assertion")
    require("Phases 3–10" in checkpoint, "Checkpoint must propagate the ten-phase roadmap")

    print("Ten-phase namespace and API/MCP control-plane validation: PASS")
    print("- top-level institutional phases: 10")
    print("- current phase: 2 / 2.99")
    print("- Phase 3 entry: blocked")
    print("- S107 API/MCP snapshot: historical/superseded; rejected for current-state validation")
    print("- designated-current API control: v3 / provider writes closed / full MCP conformance open")
    print("- CrownThrive IO: read_verified / founder unlimited-call budget policy passed / writes closed")
    print("- ThriveTools SEO: read_verified / MCP read adapter passed / remaining SRE/path/external-client gates open")
    print("- Collab Portal: 6/7 fail-closed; webhook sender/delivery integrity blocked")
    print("- Reward Loyalty: production v4 preserved; v5.27.0 target only; writes closed")
    print("- integration_control RLS: 12/12; security advisor lints: 0")
    print("- ct.tevv.control-state.current-snapshot-superseded-evidence-rejected: PASS")
    print("- raw credential-shaped fields: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
