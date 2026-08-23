#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/agent-a-emergency-execution-bridge.v2.json"
DOC = ROOT / "automation/agent-a-emergency-execution-bridge-v2.mdx"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    doc = DOC.read_text(encoding="utf-8")

    require(m["bridge_id"] == "ct.control.agent-a.execution-bridge.v2", "bridge id drift")
    require(m["agent_id"] == "ct.relay.agent-a", "Agent A identity drift")
    require(m["target_wip"] == 4 and m["hard_max_wip"] == 6, "WIP contract drift")
    require(m["continuation_before_dispatch"] is True, "continuation-first required")
    require(m["runtime_function"] == "chlom_runtime.agent_a_emergency_portfolio_cycle_v2", "runtime function drift")
    require(m["stale_actuator_function"] == "chlom_runtime.gen7_actuate_stale_portfolio_v2", "stale actuator drift")
    require(m["measurement"]["scope"] == "packet_only_for_throughput", "packet-only metric scope required")
    require(m["measurement"]["control_plane_runs_excluded"] is True, "control runs must be excluded")
    require(m["l_p_telemetry"]["agents"] == ["ct.gen6.agent-l", "ct.gen6.agent-m", "ct.gen6.agent-n", "ct.gen6.agent-o", "ct.gen6.agent-p"], "L-P identities drift")
    require(m["l_p_telemetry"]["count_as_packets_closed"] is False, "L-P telemetry cannot count as packet closure")
    require(m["force_test_2026_08_23"]["active_wip"] == 4, "force test WIP mismatch")
    require(m["force_test_2026_08_23"]["available_slots"] == 0, "force test slot mismatch")
    require(m["force_test_2026_08_23"]["new_dispatches"] == 0, "full-WIP test must not dispatch")
    require(m["force_test_2026_08_23"]["packet_metrics"]["packets_done"] == 0, "control runs cannot become closed packets")
    require(m["force_test_2026_08_23"]["packet_metrics"]["packets_closed_per_hour"] == 0, "packet closure rate must be zero")
    require(m["force_test_2026_08_23"]["progress_fabricated"] is False, "progress cannot be fabricated")
    for key in ("progress_requires_new_evidence", "progress_requires_positive_work_units", "rebind_preserves_progress", "rebind_preserves_blockers", "owner_verifier_must_differ", "no_gate_weakening", "no_self_certification"):
        require(m["invariants"][key] is True, f"{key} must remain true")
    for key in ("provider_write_enabled", "money_movement", "rights_grant", "D3_auto", "sovereign_vote_effect", "direct_main_write", "force_push", "silent_delete"):
        require(m["invariants"][key] is False, f"{key} must remain false")

    for phrase in (
        "Target WIP",
        "Hard maximum WIP",
        "Sensor-to-actuator correction",
        "Packet-scoped measurement",
        "do not independently prove packet closure",
        "did not manufacture a new blocker reduction",
    ):
        require(phrase.lower() in doc.lower(), f"documentation missing: {phrase}")

    print("Agent A emergency execution bridge v2 invariants: PASS")


if __name__ == "__main__":
    main()
