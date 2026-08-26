#!/usr/bin/env python3
"""Validate preserved phase lineage and the sanitized API/MCP snapshot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PHASE_MANIFEST = ROOT / "developers/manifests/institutional-phase-namespace.v2.json"
API_MANIFEST = ROOT / "developers/manifests/api-mcp-control-plane-state.v1.json"
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
    require(data.get("state") == "historical_superseded_snapshot", "Ten-phase namespace must be a historical snapshot")
    require(data.get("record_state") == "historical_evidence", "Ten-phase namespace must be classified as historical evidence")
    require(data.get("historical_origin_phase") == "2.99", "Historical namespace origin must remain Phase 2.99")
    require(data.get("current_institutional_phase") == 3, "Current overlay must point to Phase 3")
    require(data.get("current_institutional_phase_name") == "Phase 3 — Execute", "Current overlay Phase 3 name drifted")
    require(data.get("current_successor") == "docs/phase-model/PENTA_PHASE_MODEL.md", "PENTA phase model must be the current successor")
    require(data.get("decision_id") == "CT-ADR-ROADMAP-010", "Ten-phase roadmap decision ID must remain CT-ADR-ROADMAP-010")
    require(data.get("top_level_phase_count") == 10, "Exactly ten top-level institutional phases are required")
    phases = data.get("phases")
    require(isinstance(phases, list) and len(phases) == 10, "Phase manifest must contain ten phase records")
    require([row.get("number") for row in phases] == list(range(1, 11)), "Phase numbers must be 1 through 10")
    require([row.get("name") for row in phases] == EXPECTED_PHASES, "Phase names do not match ten_phase_v1")
    require(data.get("current_phase") == 2, "Historical snapshot phase must remain Phase 2")
    require(data.get("current_subphase") == "2.99", "Historical snapshot subphase must remain 2.99")
    require(data.get("phase_3_entry") == "blocked_pending_phase_2_99_hard_exit", "Historical Phase 3 gate evidence drifted")

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

    docs = data.get("documentation_reconciliation", {})
    require(docs.get("state") == "historical_snapshot_superseded_by_penta", "Namespace must remain superseded by PENTA")


def validate_api_control(data: dict[str, Any]) -> None:
    require(data.get("record_state") == "historical_operational_snapshot", "API control evidence must be a historical snapshot")
    require(data.get("historical_origin_phase") == "2.99", "API control historical origin must remain 2.99")
    require(data.get("current_institutional_phase") == 3, "API control current overlay must point to Phase 3")
    require(data.get("current_successor") == "docs/phase3/CURRENT_STATE.md", "API control current successor drifted")
    require(data.get("source_class") == "dated_operational_control_plane_snapshot", "API source class must be dated evidence")
    phase = data.get("phase", {})
    require(phase.get("snapshot_semantics") == "historical_as_observed_2026_08_19", "API snapshot semantics drifted")
    require(phase.get("current_phase") == 2 and phase.get("current_subphase") == "2.99", "API historical snapshot must remain scoped to Phase 2 / 2.99")
    require(phase.get("phase_3_entry") == "blocked_pending_phase_2_99_hard_exit", "API historical gate evidence drifted")

    control = data.get("crownthrive_api_control", {})
    require(control.get("runtime_version") == 2, "API control runtime must be version 2")
    require(control.get("runtime_state") == "active", "API control runtime must be active")
    require(control.get("jwt_auth") == "passed", "API control JWT gate must be passed")
    require(control.get("admin_authorization") == "required", "API control must retain admin authorization")
    require(control.get("mcp_protocol") == "2026-07-28", "MCP protocol must be 2026-07-28")
    require(control.get("mcp_contract") == "passed", "MCP contract must be passed")
    require(control.get("mcp_methods") == ["server/discover", "tools/list", "tools/call"], "MCP method set changed unexpectedly")
    require(control.get("provider_writes_enabled") is False, "Provider writes must remain disabled")
    require(control.get("provider_write_gate") == "closed", "Provider write gate must remain closed")
    require(control.get("external_client_conformance_test") == "open", "External client conformance must remain explicitly open until certified")

    io_state = data.get("crownthrive_io", {})
    require(io_state.get("credential_state") == "verified", "CrownThrive IO credential state must be verified")
    require(io_state.get("credential_storage") == "runtime_vault_reference_only", "CrownThrive IO credential must remain runtime/Vault only")
    require(io_state.get("authenticated_read") == "passed", "CrownThrive IO authenticated read must be passed")
    require(io_state.get("integration_state") == "read_verified", "CrownThrive IO integration must remain read_verified")
    require(io_state.get("write_operations") == "closed", "CrownThrive IO writes must remain closed")
    require(io_state.get("provider_writes_enabled") is False, "CrownThrive IO provider writes must remain disabled")
    require(io_state.get("team_members_by_team_id") == "documented_not_certified", "Team-member-by-team-id state must not be promoted")

    collab = data.get("collab_portal", {})
    require(collab.get("credential_state") == "mismatch", "Collab credential mismatch must remain explicit")
    require(collab.get("credential_exact_match") == "blocked", "Collab exact credential gate must remain blocked")
    require(collab.get("authenticated_read") == "blocked", "Collab authenticated read must remain blocked")
    require(collab.get("bounded_write") == "closed", "Collab bounded write must remain closed")
    require(collab.get("provider_writes_enabled") is False, "Collab provider writes must remain disabled")
    require(collab.get("observed_request_count") == 0, "Collab request-count snapshot changed inside immutable evidence")

    secret_state = data.get("secret_handling", {})
    require(secret_state and all(value is False for value in secret_state.values()), "Secret exposure flags must all remain false")

    forbidden = walk_forbidden_keys(data)
    require(not forbidden, "Raw credential-shaped field names are prohibited in public-safe manifest: " + ", ".join(forbidden))

    docs = data.get("docs_impact", {})
    require(docs.get("state") == "historical_snapshot_with_current_delta_open", "API/MCP historical/current boundary must remain explicit")


def main() -> int:
    for path in (PHASE_MANIFEST, API_MANIFEST, CHECKPOINT, GOVERNANCE_ADR):
        require(path.is_file(), f"Missing {path.relative_to(ROOT)}")

    phase_data = load_json(PHASE_MANIFEST)
    api_data = load_json(API_MANIFEST)
    validate_phase_namespace(phase_data)
    validate_api_control(api_data)

    checkpoint = CHECKPOINT.read_text(encoding="utf-8")
    require("PR #62 five-phase machine assertion is superseded" in checkpoint, "Checkpoint must preserve and supersede the transient five-phase assertion")
    require("Phases 3–10" in checkpoint, "Checkpoint must propagate the ten-phase roadmap")

    print("Historical namespace and API/MCP control-plane validation: PASS")
    print("- preserved ten-phase snapshot: 10 phases")
    print("- historical phase snapshot: 2 / 2.99")
    print("- current institutional phase: 3 / Execute")
    print("- PR #62 five-phase snapshot: preserved as superseded lineage")
    print("- CrownThrive API/MCP provider writes: disabled")
    print("- CrownThrive IO: read_verified / writes closed")
    print("- Collab Portal: credential mismatch / read blocked / writes closed")
    print("- raw credential-shaped fields: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
