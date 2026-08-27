#!/usr/bin/env python3
"""Validate the fail-closed Supabase production convergence snapshot."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/supabase-production-convergence-state.v1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(data.get("schema_version") == "1.0.0", "Supabase convergence schema drifted")
    require(data.get("institutional_phase") == "3", "Supabase convergence state must remain Phase 3")
    require(data.get("evidence_scope") == "connected_provider_read_only_snapshot", "Provider evidence scope drifted")

    project = data.get("project", {})
    require(project.get("project_ref") == "tzajnzshmtzjenqulehq", "Supabase project ref drifted")
    require(project.get("status") == "ACTIVE_HEALTHY", "Observed project health changed without snapshot reconciliation")

    migration = data.get("migration_custody", {})
    local_count = len(list((ROOT / "supabase/migrations").glob("*.sql")))
    expected_count = migration.get("repository_migration_file_count")
    provider_count = migration.get("provider_migration_count", 0)
    require(
        local_count == expected_count,
        f"Repository migration count changed; refresh repository inventory evidence (expected={expected_count}, actual={local_count})",
    )
    require(
        provider_count >= local_count,
        f"Repository migration inventory exceeds the last provider snapshot (provider={provider_count}, repository={local_count})",
    )
    require(
        migration.get("count_parity_is_not_custody_proof") is True,
        "Migration-count parity must never be treated as replay, synchronization, or custody proof",
    )
    if provider_count == local_count:
        require(
            migration.get("count_parity_observed") is True,
            "Observed provider/repository migration-count parity is not recorded",
        )
    require(migration.get("default_branch_status") == "MIGRATIONS_FAILED", "Default branch status changed without accepted readback")
    require(migration.get("gate") == "HOLD", "Migration custody must remain held")
    require("not found in local migrations directory" in migration.get("last_observed_error", ""), "Migration failure cause drifted")

    security = data.get("security_advisors", {})
    require(security.get("total") == 173, "Security advisor count changed without snapshot reconciliation")
    require(security.get("info") == 173, "Security INFO count changed without snapshot reconciliation")
    require(security.get("warn") == 0, "Security warning count changed without snapshot reconciliation")
    require(security.get("info_lint") == "rls_enabled_no_policy", "Expected RLS policy-intent INFO set drifted")
    require(security.get("gate") == "HOLD_PENDING_RLS_POLICY_INTENT_REVIEW", "RLS policy intent must remain held")
    require(security.get("accepted_exception_evidence") is None, "No accepted security exception is recorded")
    lints = {item.get("lint") for item in security.get("warnings", [])}
    require(lints == set(), "No security WARN advisories were observed in the refreshed provider snapshot")

    sacred = data.get("sacred_history_api", {})
    require(sacred.get("function_version") == 3, "Sacred History observed function version drifted")
    for endpoint in ("status_get", "sources_get", "texts_get", "claims_get", "routes_get", "entities_get"):
        require(sacred.get(endpoint) == 200, f"Sacred History observed read evidence drifted: {endpoint}")
    require(sacred.get("state") == "PASS_OBSERVED_READ_SURFACE", "Sacred History read surface state drifted")
    require(sacred.get("blanket_release_certification") is False, "Observed reads may not become blanket certification")

    authority = data.get("audit_authority", {})
    for key in (
        "external_state_mutated_by_this_audit",
        "provider_snapshot_is_repository_truth",
        "provider_health_implies_migration_custody",
        "advisor_info_implies_outage",
        "warning_may_be_silently_accepted",
    ):
        require(authority.get(key) is False, f"Supabase false-promotion guard drifted: {key}")
    require(authority.get("d3_human_reserved") is True, "D3 must remain human-reserved")

    print(json.dumps({
        "status": "PASS",
        "project_health": "ACTIVE_HEALTHY",
        "sacred_history_reads": "PASS_OBSERVED",
        "repository_migrations": local_count,
        "provider_snapshot_migrations": provider_count,
        "count_parity": provider_count == local_count,
        "count_parity_is_custody_proof": False,
        "migration_custody": "HOLD",
        "security_warnings": 0,
        "security_policy_intent": "HOLD",
        "external_mutation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
