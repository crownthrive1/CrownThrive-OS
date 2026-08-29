from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data/penta/pentaself-permanent-repair-fabric.v2.json"
MIGRATIONS = [
    ROOT / "supabase/migrations/20260829021000_penta_marketer_event_derived_projection_v2.sql",
    ROOT / "supabase/migrations/20260829021400_pentaself_current_truth_and_phase_reconciliation_v2.sql",
    ROOT / "supabase/migrations/20260829021800_pentaself_monotonic_permanent_repair_fabric_v2.sql",
]


def test_permanent_repair_contract_is_fail_closed() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    invariants = contract["invariants"]
    assert contract["contract"] == "ct.penta.self.permanent-repairs.v2"
    assert contract["status"] == "production_applied"
    assert invariants["scheduler_desired_state_generation_monotonic"] is True
    assert invariants["stale_generation_rejected"] is True
    assert invariants["resolved_problem_stale_reopen_blocked"] is True
    assert invariants["genuinely_new_evidence_may_reopen"] is True
    assert invariants["repair_classes_allowlisted"] is True
    assert invariants["repair_receipts_append_only"] is True
    assert invariants["d3_human_reserved"] is True
    assert invariants["credential_material_exposed"] is False
    assert invariants["provider_authority_manufactured"] is False
    assert invariants["money_movement_authority"] is False


def test_source_carries_monotonic_and_stale_reopen_guards() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in MIGRATIONS)
    required = [
        "stale_repair_generation_rejected",
        "explicit_higher_generation_rollback_ticket_required",
        "stale_or_identical_evidence_cannot_reopen_resolved_problem",
        "repair_class_not_allowlisted",
        "scheduler_permanence_reconcile_v2",
        "penta_marketer_refresh_event_projection_v2",
        "current_truth_receipts_v2 is append-only",
        "permanent_repair_events_v2 is append-only",
        "problem_regression_blocks_v2 is append-only",
        "from public, anon, authenticated",
    ]
    for marker in required:
        assert marker in text


def test_no_implicit_rollback_or_authority_expansion() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    rollback = contract["rollback"]
    assert rollback["implicit_or_stale"] == "forbidden"
    assert "higher generation" in rollback["required"]
    assert rollback["emergency_kill_switches"] == "remain independently authoritative"
