#!/usr/bin/env python3
"""Validate the fail-closed Supabase production convergence snapshot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/supabase-production-convergence-state.v1.json"
HISTORICAL = ROOT / "developers/manifests/supabase-production-convergence-state.2026-08-26.v1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(data.get("schema_version") == "1.1.0", "Supabase convergence schema drifted")
    require(data.get("institutional_phase") == "3", "Supabase convergence state must remain Phase 3")
    require(
        data.get("evidence_scope")
        == "authenticated_read_only_provider_readback_and_repository_reconciliation",
        "Provider evidence scope drifted",
    )
    require(
        data.get("supersedes_historical_evidence")
        == "developers/manifests/supabase-production-convergence-state.2026-08-26.v1.json",
        "Historical Supabase evidence lineage drifted",
    )
    require(
        data.get("superseded_historical_evidence_sha256")
        == hashlib.sha256(HISTORICAL.read_bytes()).hexdigest(),
        "Historical Supabase evidence digest drifted",
    )

    project = data.get("project", {})
    require(project.get("project_ref") == "tzajnzshmtzjenqulehq", "Supabase project ref drifted")
    require(project.get("status") == "ACTIVE_HEALTHY", "Observed project health changed without snapshot reconciliation")
    require(project.get("postgres_version") == "17.6.1", "Observed Postgres version drifted")

    migration = data.get("migration_custody", {})
    local_count = len(list((ROOT / "supabase/migrations").glob("*.sql")))
    require(local_count == migration.get("repository_migration_file_count"), "Repository migration count changed; refresh provider custody evidence")
    require(migration.get("provider_migration_count") == 962, "Provider migration readback count drifted")
    require(migration.get("provider_migration_count", 0) > local_count, "Migration custody hold must not be closed by count inference")
    require(migration.get("provider_applied_versions_differ_from_local_source_filename_versions") is True, "Provider/local version divergence must remain explicit")
    require(migration.get("local_to_provider_one_to_one_lineage_proven") is False, "Migration lineage may not self-certify")
    require(migration.get("semantic_and_checksum_mapping_complete") is False, "Migration mapping is not complete")
    require(migration.get("zero_unintended_pending_migrations_dry_run_proven") is False, "No zero-pending dry run is proven")
    require(migration.get("database_push_allowed") is False, "Database push must remain prohibited")
    require(migration.get("gate") == "HOLD_NO_DB_PUSH", "Migration custody must remain HOLD_NO_DB_PUSH")
    require(len(migration.get("required_resolution", [])) == 6, "Migration closure evidence is incomplete")

    security = data.get("security_advisors", {})
    require(security.get("total") == 188, "Security advisor count changed without snapshot reconciliation")
    require(security.get("info") == 188, "Security INFO count changed without snapshot reconciliation")
    require(security.get("warn") == 0, "Security warning count changed without snapshot reconciliation")
    require(security.get("info_lint") == "rls_enabled_no_policy", "Expected RLS policy-intent INFO set drifted")
    require(security.get("gate") == "HOLD_PENDING_RLS_POLICY_INTENT_REVIEW", "RLS policy intent must remain held")
    require(security.get("accepted_exception_evidence") is None, "No accepted security exception is recorded")

    performance = data.get("performance_advisors", {})
    require(
        performance
        == {
            "total_info": 877,
            "unindexed_foreign_keys": 409,
            "tables_without_primary_key": 3,
            "unused_indexes": 464,
            "auth_db_connections_absolute": 1,
            "gate": "HOLD_INHERITED_PERFORMANCE_REVIEW",
        },
        "Performance advisor snapshot drifted",
    )

    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    require(historical.get("schema_version") == "1.0.0", "Historical Supabase snapshot schema drifted")
    require(historical.get("migration_custody", {}).get("provider_migration_count") == 919, "Historical provider count drifted")
    require(historical.get("migration_custody", {}).get("repository_migration_file_count") == 49, "Historical repository count drifted")
    require(historical.get("security_advisors", {}).get("total") == 173, "Historical security count drifted")

    authority = data.get("audit_authority", {})
    for key in (
        "external_state_mutated_by_this_audit",
        "provider_snapshot_is_repository_truth",
        "provider_health_implies_migration_custody",
        "advisor_info_implies_outage",
        "warning_may_be_silently_accepted",
        "database_push_performed",
    ):
        require(authority.get(key) is False, f"Supabase false-promotion guard drifted: {key}")
    require(authority.get("d3_human_reserved") is True, "D3 must remain human-reserved")

    print(json.dumps({
        "status": "PASS",
        "project_health": "ACTIVE_HEALTHY",
        "provider_migrations": 962,
        "repository_migrations": local_count,
        "migration_custody": "HOLD_NO_DB_PUSH",
        "security_warnings": 0,
        "security_info": 188,
        "performance_info": 877,
        "security_policy_intent": "HOLD",
        "external_mutation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
