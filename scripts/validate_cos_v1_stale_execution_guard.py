#!/usr/bin/env python3
"""Static validation for COS V1 stale-execution protections."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORWARD = ROOT / "supabase/migrations/20260830021700_cos_v1_stale_execution_guard_v1.sql"
ROLLBACK = ROOT / "supabase/rollbacks/20260830021700_cos_v1_stale_execution_guard_v1.rollback.sql"


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> None:
    forward = FORWARD.read_text(encoding="utf-8")
    rollback = ROLLBACK.read_text(encoding="utf-8")
    checks = {
        "gate_receipt_current_guard": "cos_phase_gate_receipt_current_execution_guard_v1" in forward,
        "stale_receipt_denied": "stale_phase_execution_gate_receipt" in forward,
        "terminal_receipt_denied": "terminal_phase_execution_rejects_gate_receipt" in forward,
        "execution_mutation_guard": "cos_phase_execution_current_mutation_guard_v1" in forward,
        "stale_mutation_denied": "stale_phase_execution_mutation" in forward,
        "release_source_drift_denied": "phase_execution_release_source_drift" in forward,
        "d3_mutation_guarded": "new.d3_approval_ref is distinct from old.d3_approval_ref" in forward,
        "pass_mutation_guarded": "new.state='passed'" in forward,
        "rollback_history_safe": "rollback_blocked_cos_phase_execution_history_exists" in rollback,
        "rollback_drops_gate_trigger": "drop trigger if exists cos_phase_gate_receipt_current_execution_guard_v1" in rollback,
        "rollback_drops_execution_trigger": "drop trigger if exists cos_phase_execution_current_mutation_guard_v1" in rollback,
    }
    failures = [name for name, passed in checks.items() if not passed]
    require(not failures, "stale-execution guard validation failed: " + ", ".join(failures))
    print(f"COS V1 stale-execution guard: PASS ({len(checks)} invariants)")


if __name__ == "__main__":
    main()
