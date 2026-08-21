#!/usr/bin/env python3
"""Fail-closed validator for CT-P10-GATE-001 Full Ecosystem Convergence."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONVERGENCE = ROOT / "developers/manifests/phase-10-ecosystem-convergence.v1.json"
PHASES = ROOT / "developers/manifests/institutional-phase-namespace.v2.json"

EXPECTED_GATE_ID = "CT-P10-GATE-001"
EXPECTED_GATE_NAME = "FULL_ECOSYSTEM_CONVERGENCE"
EXPECTED_TERMINAL = {
    "CONVERGED_NATIVE",
    "CONVERGED_ADAPTER",
    "GOVERNED_ISOLATED",
    "RETIRED_PRESERVED",
    "RESEARCH_NOT_OPERATIONAL",
}
EXPECTED_MILESTONES = {"2.99", "3", "4", "5", "6", "7", "8", "9", "10"}
EXPECTED_DIMENSIONS = {
    "canonical_identity",
    "repository_runtime_identity",
    "crownthrive_id_authority",
    "chlom_rights_governance",
    "data_event_crownlytics",
    "api_mcp_webhook_federation",
    "commerce_entitlements_value_routing",
    "support_knowledge_operations",
    "security_privacy_resilience",
    "domain_provider_vendor_custody",
    "backup_export_recovery",
    "thrive_flywheel_relationship",
    "observability_heartbeat",
    "documentation_public_truth",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path.name}: root must be an object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate() -> None:
    gate = load(CONVERGENCE)
    phase_ns = load(PHASES)

    require(gate.get("gate_id") == EXPECTED_GATE_ID, "unexpected Phase-10 gate ID")
    require(gate.get("gate_name") == EXPECTED_GATE_NAME, "unexpected Phase-10 gate name")
    require(gate.get("owner_issue") == 193, "Phase-10 convergence must remain owned by issue #193")
    require(gate.get("count_independent") is True, "convergence gate must remain count-independent")
    require(gate.get("deferral_is_pass") is False, "deferral must never equal PASS")

    terminal = gate.get("terminal_states")
    require(isinstance(terminal, list), "terminal_states must be an array")
    require(set(terminal) == EXPECTED_TERMINAL, "terminal convergence state set drifted")
    require(len(terminal) == len(set(terminal)), "terminal_states contains duplicates")

    dimensions = gate.get("dimensions")
    require(isinstance(dimensions, list), "dimensions must be an array")
    require(set(dimensions) == EXPECTED_DIMENSIONS, "required convergence dimensions drifted")

    milestones = gate.get("retroactive_milestones")
    require(isinstance(milestones, dict), "retroactive_milestones must be an object")
    require(set(milestones) == EXPECTED_MILESTONES, "Phase 2.99 through Phase 10 milestones must all exist")
    for phase, packet in milestones.items():
        require(isinstance(packet, dict), f"milestone {phase} must be an object")
        outputs = packet.get("outputs")
        require(isinstance(outputs, list) and outputs, f"milestone {phase} must have outputs")

    operating_set = gate.get("operating_set")
    require(isinstance(operating_set, dict), "operating_set contract missing")
    require(operating_set.get("research_enters_only_by_deliberate_promotion") is True,
            "research must not enter convergence scope by registry growth alone")
    require(operating_set.get("registry_growth_alone_creates_failure") is False,
            "raw registry growth cannot create convergence failure by itself")
    require(operating_set.get("active_unknown_allowed_at_phase_10_exit") is False,
            "active UNKNOWN cannot be allowed at Phase-10 exit")
    require(operating_set.get("orphan_active_node_allowed_at_phase_10_exit") is False,
            "orphan active nodes cannot be allowed at Phase-10 exit")

    phase_numbers = {p.get("number") for p in phase_ns.get("phases", []) if isinstance(p, dict)}
    require(10 in phase_numbers, "institutional phase namespace must contain Phase 10")
    propagation = set(phase_ns.get("rules", {}).get("future_phase_propagation_scope", []))
    require(10 in propagation, "Phase 10 must remain in downstream propagation scope")

    current_phase = phase_ns.get("current_phase")
    require(isinstance(current_phase, int) and current_phase >= 1, "invalid current institutional phase")

    gate_state = gate.get("gate_state")
    exit_allowed = gate.get("phase_10_exit_allowed")
    require(gate_state in {"OPEN", "BLOCKED", "PASS"}, "unsupported convergence gate state")

    if gate_state != "PASS":
        require(exit_allowed is False, "Phase-10 exit cannot be allowed while convergence gate is not PASS")
    else:
        require(exit_allowed is True, "PASS convergence gate must explicitly allow Phase-10 exit")
        snapshot = gate.get("acceptance_snapshot")
        require(isinstance(snapshot, dict), "PASS requires an immutable acceptance_snapshot")
        require(snapshot.get("terminal_coverage_percent") == 100, "PASS requires 100% terminal coverage")
        require(snapshot.get("unaccepted_orphan_active_nodes") == 0, "PASS requires zero orphan active nodes")
        require(snapshot.get("unresolved_active_identity_collisions") == 0,
                "PASS requires zero active identity collisions")
        require(snapshot.get("unowned_critical_active_dependencies") == 0,
                "PASS requires zero unowned critical dependencies")
        require(snapshot.get("connected_active_graph") is True, "PASS requires connected active convergence graph")
        require(snapshot.get("continuity_drills_passed") is True, "PASS requires continuity drills")
        require(snapshot.get("documentation_reconciled") is True, "PASS requires docs/public-truth reconciliation")
        require(snapshot.get("agent_b_accepted") is True, "PASS requires Agent B acceptance")
        require(snapshot.get("agent_s_accepted") is True, "PASS requires Agent S acceptance")
        require(snapshot.get("agent_d_accepted") is True, "PASS requires Agent D acceptance")
        require(snapshot.get("required_specialists_accepted") is True, "PASS requires specialist acceptance")
        require(snapshot.get("sovereign_quorum_accepted") is True, "PASS requires sovereign quorum")
        commit = str(snapshot.get("exact_commit_sha", ""))
        digest = str(snapshot.get("evidence_sha256", ""))
        require(bool(GIT_SHA_RE.fullmatch(commit)), "PASS requires exact 40-character Git commit SHA")
        require(bool(SHA256_RE.fullmatch(digest)), "PASS requires evidence SHA-256")

    if current_phase > 10:
        require(gate_state == "PASS" and exit_allowed is True,
                "institution may not progress beyond Phase 10 without accepted full ecosystem convergence")

    acceptance = gate.get("phase_10_acceptance")
    require(isinstance(acceptance, dict), "phase_10_acceptance contract missing")
    require(acceptance.get("requires_terminal_coverage_percent") == 100,
            "Phase-10 acceptance must require 100% terminal coverage")
    for key in (
        "requires_zero_unaccepted_orphans",
        "requires_zero_unresolved_active_identity_collisions",
        "requires_zero_unowned_critical_active_dependencies",
        "requires_connected_active_graph",
        "requires_continuity_drills",
        "requires_documentation_reconciliation",
        "requires_agent_b",
        "requires_agent_s",
        "requires_required_specialists",
        "requires_sovereign_quorum",
        "requires_agent_d",
        "d3_human_reserved",
    ):
        require(acceptance.get(key) is True, f"Phase-10 acceptance invariant missing: {key}")

    print(
        json.dumps(
            {
                "ok": True,
                "gate_id": EXPECTED_GATE_ID,
                "gate_state": gate_state,
                "current_phase": current_phase,
                "milestones": sorted(EXPECTED_MILESTONES),
                "phase_10_exit_allowed": exit_allowed,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    validate()
