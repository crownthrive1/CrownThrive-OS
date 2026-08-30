#!/usr/bin/env python3
"""Adversarial static validation for the COS V1 Phase 15 D3 release gate."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORWARD = ROOT / "supabase/migrations/20260830021500_cos_v1_phase15_d3_release_gate_v1.sql"
ROLLBACK = ROOT / "supabase/rollbacks/20260830021500_cos_v1_phase15_d3_release_gate_v1.rollback.sql"


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> None:
    forward = FORWARD.read_text(encoding="utf-8")
    rollback = ROLLBACK.read_text(encoding="utf-8")

    checks = {
        "generic_path_denied": "use_cos_phase_bind_d3_approval_v1" in forward,
        "phase15_only": "d3_release_approval_phase15_only" in forward,
        "canonical_founder": "b.founder_ref='ct.person.founder.kavonte-jones-sr'" in forward,
        "directive_id_required": "nullif(btrim(coalesce(b.directive_id,'')),'') is not null" in forward,
        "directive_digest_required": "b.directive_source_sha256 ~ '^[0-9a-f]{64}$'" in forward,
        "scope_digest_required": "b.scope_sha256 ~ '^[0-9a-f]{64}$'" in forward,
        "zero_cost_authority": "b.max_cost_minor=0" in forward,
        "exact_action": "'cos.production_release' = any(b.authorized_actions)" in forward,
        "exact_repository": "'repository','crownthrive1/CrownThrive-OS'" in forward,
        "exact_source_sha": "'source_sha',v_source_sha" in forward,
        "current_window_start": "clock_timestamp() >= b.starts_at" in forward,
        "current_window_end": "clock_timestamp() < b.expires_at" in forward,
        "nonrenewing": "b.nonrenewing is true" in forward,
        "independent_evidence": "b.independent_evidence_required is true" in forward,
        "no_provider_writes": "b.provider_write_authority is false" in forward,
        "no_money": "b.money_movement_authority is false" in forward,
        "no_rights": "b.rights_disposition_authority is false" in forward,
        "no_credentials": "b.credential_authority is false" in forward,
        "holds_honored": "d3_campaign_holds_v1" in forward,
        "canonical_founder_recheck": "canonical_d3_founder_ref_required" in forward,
        "campaign_swap_denied": "d3_release_approval_already_bound" in forward,
        "replay_lookup": "select receipt_id into v_receipt_id" in forward,
        "replay_returns_existing": "return v_receipt_id;" in forward,
        "d3_unique_index": "cos_phase_gate_receipts_d3_once_idx" in forward,
        "finalizer_revalidates": "phase15_d3_approval_expired_held_or_drifted" in forward,
        "finalizer_requires_binding": "phase15_d3_approval_not_bound" in forward,
        "standing_campaign_not_hardcoded": "ct.penta.flow-control.20260826.v1" not in forward,
        "rollback_blocks_existing_phase15_history": "rollback_blocked_phase15_execution_history_exists" in rollback,
        "rollback_drops_d3_unique_index": "drop index if exists integration_control.cos_phase_gate_receipts_d3_once_idx" in rollback,
        "rollback_disables_phase15_release": "phase15_release_disabled_after_d3_hardening_rollback" in rollback,
        "rollback_does_not_release": "state='released'" not in rollback,
    }

    failures = [name for name, passed in checks.items() if not passed]
    require(not failures, "D3 release gate validation failed: " + ", ".join(failures))
    print(f"COS V1 Phase 15 D3 release gate: PASS ({len(checks)} adversarial invariants)")


if __name__ == "__main__":
    main()
