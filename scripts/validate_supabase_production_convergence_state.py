#!/usr/bin/env python3
"""Validate historical Supabase snapshot plus current candidate lineage custody.

The v1 convergence manifest is intentionally preserved as the provider truth that
originally opened the migration HOLD. PentaRuntimeCustody is the successor evidence
for the repair candidate. A passing candidate does not manufacture a Supabase main
or Preview PASS; provider readback remains an independent promotion requirement.
"""
from __future__ import annotations

import json
from pathlib import Path

from penta_runtime_custody import assert_lineage, load

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/supabase-production-convergence-state.v1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    historical = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(historical.get("schema_version") == "1.0.0", "Supabase convergence schema drifted")
    require(historical.get("institutional_phase") == "3", "historical snapshot must remain Phase 3")
    require(historical.get("evidence_scope") == "connected_provider_read_only_snapshot", "historical evidence scope drifted")
    project = historical.get("project", {})
    require(project.get("project_ref") == "tzajnzshmtzjenqulehq", "Supabase project ref drifted")
    require(project.get("status") == "ACTIVE_HEALTHY", "historical project health evidence drifted")

    old = historical.get("migration_custody", {})
    require(old.get("provider_migration_count") == 919, "historical provider migration count mutated")
    require(old.get("repository_migration_file_count") == 49, "historical repository count mutated")
    require(old.get("default_branch_status") == "MIGRATIONS_FAILED", "historical default-branch status mutated")
    require(old.get("gate") == "HOLD", "historical migration HOLD mutated")
    require("not found in local migrations directory" in old.get("last_observed_error", ""), "historical failure cause drifted")

    current = load()
    assert_lineage(current)
    ledger = current.get("migration_ledger", {})
    require(ledger.get("count") == 1007, "current candidate migration count drifted")
    require(ledger.get("last_version") == "20260827183832", "current candidate migration head drifted")
    require(ledger.get("versions_sha256") == "78bfc513916d9b90ccc95808be074f233cdd8cb4b0097762e1558302b6e71fbe", "current candidate lineage digest drifted")
    require(ledger.get("production_history_mutated") is False, "candidate may not rewrite production history")

    security = historical.get("security_advisors", {})
    require(security.get("warn") == 0, "historical security warning count drifted")
    require(security.get("gate") == "HOLD_PENDING_RLS_POLICY_INTENT_REVIEW", "historical RLS policy-intent state drifted")
    sacred = historical.get("sacred_history_api", {})
    require(sacred.get("state") == "PASS_OBSERVED_READ_SURFACE", "historical Sacred History read evidence drifted")
    require(sacred.get("blanket_release_certification") is False, "observed reads may not become blanket certification")
    authority = historical.get("audit_authority", {})
    for key in ("external_state_mutated_by_this_audit","provider_snapshot_is_repository_truth","provider_health_implies_migration_custody","advisor_info_implies_outage","warning_may_be_silently_accepted"):
        require(authority.get(key) is False, f"historical false-promotion guard drifted: {key}")

    print(json.dumps({
        "status": "PASS",
        "historical_provider_snapshot": "PRESERVED",
        "historical_migration_gate": "HOLD",
        "candidate_lineage": "PASS",
        "candidate_migration_count": 1007,
        "candidate_last_version": "20260827183832",
        "production_main_provider_readback": "REQUIRED",
        "supabase_preview_provider_readback": "REQUIRED",
        "production_history_mutated": False,
        "blanket_release_certification": False
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
