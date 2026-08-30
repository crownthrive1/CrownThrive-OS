#!/usr/bin/env python3
"""Static validation for the transactional COS V1 phase DAIL evidence spine."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORWARD = ROOT / "supabase/migrations/20260830021800_cos_v1_phase_dail_spine_v1.sql"
ROLLBACK = ROOT / "supabase/rollbacks/20260830021800_cos_v1_phase_dail_spine_v1.rollback.sql"


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> None:
    forward = FORWARD.read_text(encoding="utf-8")
    rollback = ROLLBACK.read_text(encoding="utf-8")
    checks = {
        "execution_begin_binding": "cos_phase_execution_begin_dail_v1" in forward,
        "gate_binding": "cos_phase_gate_receipt_dail_v1" in forward,
        "state_binding": "cos_phase_execution_state_dail_v1" in forward,
        "canonical_dail": forward.count("chlom_runtime.append_dail_event") >= 3,
        "begin_receipt_required": "phase_begin_dail_receipt_missing" in forward,
        "gate_receipt_required": "phase_gate_dail_receipt_missing" in forward,
        "state_receipt_required": "phase_state_dail_receipt_missing" in forward,
        "prestate_hashed": "pre_state_sha256" in forward,
        "rollback_hashed": "rollback_point_sha256" in forward,
        "scope_hashed": "mutation_scope_sha256" in forward,
        "gate_evidence_digest_only": "'evidence_sha256',new.evidence_sha256" in forward,
        "protected_body_not_projected": "evidence_refs,new.evidence_refs" not in forward,
        "begin_id_persisted": "new.begin_dail_event_id:=v_receipt->>'event_id'" in forward,
        "gate_id_persisted": "new.dail_event_id:=v_receipt->>'event_id'" in forward,
        "state_id_persisted": "new.last_state_dail_event_id:=v_receipt->>'event_id'" in forward,
        "rollback_history_safe": "rollback_blocked_cos_phase_evidence_history_exists" in rollback,
        "rollback_drops_all_triggers": all(name in rollback for name in (
            "cos_phase_execution_state_dail_v1",
            "cos_phase_gate_receipt_dail_v1",
            "cos_phase_execution_begin_dail_v1",
        )),
    }
    failures = [name for name, passed in checks.items() if not passed]
    require(not failures, "phase DAIL spine validation failed: " + ", ".join(failures))
    print(f"COS V1 phase DAIL spine: PASS ({len(checks)} invariants)")


if __name__ == "__main__":
    main()
