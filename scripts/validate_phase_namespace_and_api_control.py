#!/usr/bin/env python3
"""Validate the current five-phase namespace and sanitized API/MCP control-plane snapshot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PHASE_MANIFEST = ROOT / "developers/manifests/institutional-phase-namespace.v2.json"
API_MANIFEST = ROOT / "developers/manifests/api-mcp-control-plane-state.v1.json"
CHECKPOINT = ROOT / "changelog/phase-2-99-five-phase-api-mcp-control-plane-checkpoint.md"

EXPECTED_PHASES = [
    "Institutional Mapping",
    "Institutional Recovery, Reconciliation & Documentation",
    "Executable Institutional Core",
    "Federated Ecosystem Activation",
    "Institutional Scale, Licensing & Expansion",
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
    require(data.get("top_level_phase_count") == 5, "Exactly five top-level institutional phases are required")
    phases = data.get("phases")
    require(isinstance(phases, list) and len(phases) == 5, "Phase manifest must contain five phase records")
    require([row.get("number") for row in phases] == [1, 2, 3, 4, 5], "Phase numbers must be 1 through 5")
    require([row.get("name") for row in phases] == EXPECTED_PHASES, "Phase names do not match the governing five-phase namespace")
    require(data.get("current_phase") == 2, "Current institutional phase must remain Phase 2")
    require(data.get("current_subphase") == "2.99", "Current institutional subphase must remain 2.99")
    require(data.get("phase_3_entry") == "blocked_pending_phase_2_99_hard_exit", "Phase 3 must remain blocked")

    rules = data.get("rules", {})
    require(rules.get("future_phase_propagation_scope") == [3, 4, 5], "Future propagation must be limited to Phases 3-5")
    require(rules.get("historical_phase_records_preserved") is True, "Historical phase records must be preserved")
    require(rules.get("retroactive_renumbering_prohibited") is True, "Retroactive renumbering must remain prohibited")
    require(rules.get("phase_3_may_start_before_phase_2_99_hard_exit") is False, "Phase 3 may not start before the Phase 2.99 hard exit")

    superseded = data.get("superseded_top_level_namespaces", [])
    ten_phase = next((row for row in superseded if row.get("namespace") == "ten_phase_v1"), None)
    require(ten_phase is not None, "Historical ten-phase namespace disposition must be explicit")
    require(ten_phase.get("disposition") == "historical_operational_decomposition_not_current_top_level", "Ten-phase namespace must not remain current top-level authority")
    require(ten_phase.get("preserve_history") is True, "Ten-phase historical evidence must be preserved")

    docs = data.get("documentation_reconciliation", {})
    require(docs.get("state") == "docs_delta_opened", "Five-phase prose reconciliation delta must remain open until stale prose is reconciled")


def validate_api_control(data: dict[str, Any]) -> None:
    phase = data.get("phase", {})
    require(phase.get("current_phase") == 2 and phase.get("current_subphase") == "2.99", "API snapshot must remain scoped to Phase 2 / 2.99")
    require(phase.get("phase_3_entry") == "blocked_pending_phase_2_99_hard_exit", "API evidence must not advance Phase 3")

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
    require(docs.get("state") == "docs_delta_opened", "API/MCP prose reconciliation delta must remain explicit")


def main() -> int:
    require(PHASE_MANIFEST.is_file(), f"Missing {PHASE_MANIFEST.relative_to(ROOT)}")
    require(API_MANIFEST.is_file(), f"Missing {API_MANIFEST.relative_to(ROOT)}")
    require(CHECKPOINT.is_file(), f"Missing {CHECKPOINT.relative_to(ROOT)}")

    phase_data = load_json(PHASE_MANIFEST)
    api_data = load_json(API_MANIFEST)
    validate_phase_namespace(phase_data)
    validate_api_control(api_data)

    print("Five-phase namespace and API/MCP control-plane validation: PASS")
    print("- top-level institutional phases: 5")
    print("- current phase: 2 / 2.99")
    print("- Phase 3 entry: blocked")
    print("- CrownThrive API/MCP provider writes: disabled")
    print("- CrownThrive IO: read_verified / writes closed")
    print("- Collab Portal: credential mismatch / read blocked / writes closed")
    print("- raw credential-shaped fields: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
