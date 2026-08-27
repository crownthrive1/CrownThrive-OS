#!/usr/bin/env python3
"""Final exact-main overrides for Penta Wave 3 ECT.

This layer keeps the Wave 3 restack compatible with current ``main`` while
preserving the hard boundaries around provider writes, migration application,
secret access, autonomous promotion, and D3 authority.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
from typing import Any

V2_PIPELINE = Path(
    os.environ.get("V2_PIPELINE_PATH", "/tmp/penta_wave3_ect_pipeline_v2.py")
)


def load_v2():
    spec = importlib.util.spec_from_file_location(
        "penta_wave3_ect_pipeline_v2_loaded", V2_PIPELINE
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load v2 ECT pipeline: {V2_PIPELINE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v2 = load_v2()
base = v2.base
ROOT = v2.ROOT
v2_reconcile_context_and_builder = v2.reconcile_context_and_builder
base_synchronize_os_golden = base.synchronize_os_golden

# Exact point-in-time provider readback captured from
# supabase_migrations.schema_migrations. This is evidence, not an instruction to
# apply migrations or rewrite either ledger.
v2.PROVIDER_MIGRATION_COUNT = 1072
v2.PROVIDER_LAST_MIGRATION_VERSION = "20260827233619"
v2.PROVIDER_LAST_MIGRATION_NAME = "penta_pm_vercel_mesh_binding_v1"
v2.PROVIDER_LEDGER_MD5 = "1e90316367c05b2cc12db75cbe48f3a4"
v2.PROVIDER_OBSERVED_AT_UTC = "2026-08-27T23:36:53.441604Z"
v2.PROVIDER_TAIL = [
    {"version": "20260827233619", "name": "penta_pm_vercel_mesh_binding_v1"},
    {"version": "20260827233112", "name": "penta_wire_secure_read_receipts_v1"},
    {"version": "20260827233051", "name": "penta_wire_secure_provider_read_plane_v1"},
    {"version": "20260827232815", "name": "penta_wire_public_discovery_adapters_v1"},
    {"version": "20260827232249", "name": "penta_wire_resolved_gap_closeout_v1_0_1"},
    {"version": "20260827232043", "name": "penta_wire_resolved_gap_closeout_v1"},
    {"version": "20260827231840", "name": "penta_wire_v3_registry_reconciliation"},
    {"version": "20260827231627", "name": "penta_wire_internal_status_projection_v1"},
    {"version": "20260827231539", "name": "penta_wire_developer_marketplace_worker_status_v1"},
    {"version": "20260827231433", "name": "penta_factory_replica_adapter_binding_v1"},
]


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise base.PipelineError(f"ECT source contract not found: {label}")


def provider_ledger_evidence(repository_migration_count: int) -> dict[str, Any]:
    """Classify the two migration inventories without one-sided assumptions.

    Counts are useful drift signals, but they cannot prove that the two ordered
    ledgers are identical. Every non-reconciled relationship therefore remains
    an explicit provider-custody HOLD while the Wave 3 software ECT continues.
    """

    if repository_migration_count <= 0:
        raise base.PipelineError("repository migration inventory is empty")
    if v2.PROVIDER_MIGRATION_COUNT <= 0:
        raise base.PipelineError("provider migration ledger readback is empty")

    delta = v2.PROVIDER_MIGRATION_COUNT - repository_migration_count
    if delta > 0:
        relationship = "PROVIDER_AHEAD"
        status = "PROVIDER_AHEAD_REPOSITORY_HISTORY_HOLD"
        required_resolution = (
            "Recover and review the provider-applied migration lineage missing "
            "from the repository, prove clean replay on a non-production "
            "environment, and then rerun exact ordered-ledger reconciliation."
        )
    elif delta < 0:
        relationship = "REPOSITORY_AHEAD"
        status = "REPOSITORY_AHEAD_PROVIDER_APPLICATION_HOLD"
        required_resolution = (
            "Review the repository-only migration set, certify its dependency "
            "order, apply it only through the governed provider migration lane, "
            "and verify provider readback before closing custody."
        )
    else:
        relationship = "COUNT_ALIGNED"
        status = "COUNT_ALIGNED_LEDGER_IDENTITY_REVIEW_HOLD"
        required_resolution = (
            "Compare the complete ordered version/name sets and their canonical "
            "digest. Equal counts alone do not prove migration-lineage parity."
        )

    return {
        "schema": "ct.supabase.migration-ledger-readback.v1",
        "evidence_id": "ct.supabase.migration-ledger-readback.20260827.v2",
        "project": {
            "project_ref": v2.PROVIDER_PROJECT_ID,
            "name": v2.PROVIDER_PROJECT_NAME,
            "region": v2.PROVIDER_PROJECT_REGION,
            "status": "ACTIVE_HEALTHY",
            "postgres_version": v2.PROVIDER_POSTGRES_VERSION,
        },
        "observed_at": v2.PROVIDER_OBSERVED_AT_UTC,
        "source": "supabase_migrations.schema_migrations",
        "provider_readback": True,
        "provider_migration_count": v2.PROVIDER_MIGRATION_COUNT,
        "provider_last_migration_version": v2.PROVIDER_LAST_MIGRATION_VERSION,
        "provider_last_migration_name": v2.PROVIDER_LAST_MIGRATION_NAME,
        "provider_ledger_md5": v2.PROVIDER_LEDGER_MD5,
        "provider_tail": v2.PROVIDER_TAIL,
        "repository_migration_file_count": repository_migration_count,
        "provider_repository_count_delta": delta,
        "inventory_relationship": relationship,
        "count_alignment_proves_lineage": False,
        "repository_history_reconciled": False,
        "migration_apply_performed": False,
        "provider_write_performed": False,
        "external_state_mutated": False,
        "authority_expanded": False,
        "status": status,
        "gate": "HOLD",
        "required_resolution": required_resolution,
    }


# Replace the stale v2 one-sided comparison before its reconciliation function
# runs. The rest of v2 continues to preserve the provider-safe HOLD envelope.
v2.provider_ledger_evidence = provider_ledger_evidence


def reconcile_supabase_validator() -> None:
    """Upgrade the convergence validator to a finite fail-closed state model."""

    path = ROOT / "scripts/validate_supabase_production_convergence_state.py"
    text = path.read_text(encoding="utf-8")
    start_marker = "    # Count direction is evidence, not authority."
    end_marker = '    security = data.get("security_advisors", {})'
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0 or end <= start:
        raise base.PipelineError(
            "Supabase validator migration-custody block could not be located"
        )

    replacement = '''    # Migration inventory direction is evidence, never custody authority.
    # The provider readback and repository inventory must agree on their signed
    # delta and finite relationship classification, while every unresolved state
    # remains explicitly held.
    readback = migration.get("provider_ledger_readback")
    require(isinstance(readback, dict), "Provider migration-ledger readback is missing")
    require(readback.get("readback") is True, "Provider migration-ledger readback was not observed")

    readback_provider_count = readback.get("provider_migration_count")
    readback_repository_count = readback.get("repository_migration_file_count")
    require(
        type(readback_provider_count) is int and readback_provider_count > 0,
        "Provider migration-ledger count must be a positive integer",
    )
    require(
        type(readback_repository_count) is int and readback_repository_count > 0,
        "Repository migration inventory count must be a positive integer",
    )
    require(
        readback_provider_count == provider_count,
        "Top-level and readback provider migration counts diverged",
    )
    require(
        readback_repository_count == local_count,
        "Readback and exact repository migration counts diverged",
    )

    delta = readback_provider_count - readback_repository_count
    require(
        readback.get("provider_repository_count_delta") == delta,
        "Provider/repository migration count delta is inconsistent",
    )
    relationship = (
        "COUNT_ALIGNED"
        if delta == 0
        else ("PROVIDER_AHEAD" if delta > 0 else "REPOSITORY_AHEAD")
    )
    expected_status = {
        "PROVIDER_AHEAD": "PROVIDER_AHEAD_REPOSITORY_HISTORY_HOLD",
        "REPOSITORY_AHEAD": "REPOSITORY_AHEAD_PROVIDER_APPLICATION_HOLD",
        "COUNT_ALIGNED": "COUNT_ALIGNED_LEDGER_IDENTITY_REVIEW_HOLD",
    }[relationship]
    require(
        readback.get("inventory_relationship") == relationship,
        "Migration inventory relationship does not match the signed count delta",
    )
    require(
        migration.get("default_branch_status") == expected_status,
        "Default-branch migration status does not match verified custody evidence",
    )
    require(migration.get("gate") == "HOLD", "Migration custody must remain held")
    require(
        readback.get("count_alignment_proves_lineage") is False,
        "Count alignment may not be promoted to migration-lineage proof",
    )
    require(
        readback.get("repository_history_reconciled") is False,
        "Repository migration history may not be marked reconciled by this audit",
    )
    require(
        readback.get("provider_write_performed") is False,
        "Provider migration state may not be mutated by this audit",
    )
    observed_error = migration.get("last_observed_error", "")
    require(
        "no migration was applied" in observed_error,
        "Migration no-apply boundary is missing from the custody evidence",
    )
    require(
        "no provider or repository history was rewritten" in observed_error,
        "Migration history no-rewrite boundary is missing from the custody evidence",
    )

'''
    path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")


def reconcile_context_and_builder() -> None:
    v2_reconcile_context_and_builder()

    # Rewrite the convergence projection with the exact symmetric disposition;
    # v2 historically emitted MIGRATIONS_FAILED for every relationship.
    evidence_path = (
        ROOT / "evidence/supabase/supabase-migration-ledger-readback-20260827.json"
    )
    convergence_path = (
        ROOT / "developers/manifests/supabase-production-convergence-state.v1.json"
    )
    evidence = base.load_json(evidence_path)
    convergence = base.load_json(convergence_path)
    custody = convergence.get("migration_custody")
    if not isinstance(custody, dict):
        raise base.PipelineError("Supabase convergence migration_custody must be an object")

    relationship = evidence["inventory_relationship"]
    custody.update(
        {
            "provider_migration_count": evidence["provider_migration_count"],
            "provider_last_migration_version": evidence[
                "provider_last_migration_version"
            ],
            "provider_last_migration_name": evidence["provider_last_migration_name"],
            "repository_migration_file_count": evidence[
                "repository_migration_file_count"
            ],
            "count_parity_observed": (
                evidence["provider_migration_count"]
                == evidence["repository_migration_file_count"]
            ),
            "count_parity_is_not_custody_proof": True,
            "default_branch_status": evidence["status"],
            "last_observed_error": (
                f"Migration custody is not reconciled: relationship={relationship}; "
                f"provider_count={evidence['provider_migration_count']}; "
                f"repository_count={evidence['repository_migration_file_count']}; "
                "no migration was applied and no provider or repository history was rewritten."
            ),
            "gate": "HOLD",
        }
    )
    provider_readback = custody.get("provider_ledger_readback")
    if not isinstance(provider_readback, dict):
        provider_readback = {}
        custody["provider_ledger_readback"] = provider_readback
    provider_readback.update(
        {
            "observed_at": evidence["observed_at"],
            "provider_migration_count": evidence["provider_migration_count"],
            "provider_last_migration_version": evidence[
                "provider_last_migration_version"
            ],
            "provider_last_migration_name": evidence["provider_last_migration_name"],
            "provider_ledger_md5": evidence["provider_ledger_md5"],
            "provider_tail": evidence["provider_tail"],
            "repository_migration_file_count": evidence[
                "repository_migration_file_count"
            ],
            "provider_repository_count_delta": evidence[
                "provider_repository_count_delta"
            ],
            "inventory_relationship": relationship,
            "count_alignment_proves_lineage": False,
            "readback": True,
            "repository_history_reconciled": False,
            "provider_write_performed": False,
        }
    )
    base.write_json(convergence_path, convergence)
    reconcile_supabase_validator()

    builder_path = ROOT / "scripts/build_penta_os_v1.py"
    builder = builder_path.read_text(encoding="utf-8")
    initialization_marker = (
        '                "explicit_registration_state": incoming.get("registration_state"),\n'
    )
    initialization_extension = (
        '                "_evidence_backed_maturity": (\n'
        '                    incoming.get("maturity")\n'
        '                    if incoming.get("source_kind") == "production_family_catalog"\n'
        '                    and isinstance(incoming.get("production_evidence"), dict)\n'
        '                    and bool(incoming.get("production_evidence"))\n'
        '                    else None\n'
        '                ),\n'
    )
    if '"_evidence_backed_maturity": (' not in builder:
        builder = _replace_once(
            builder,
            initialization_marker,
            initialization_marker + initialization_extension,
            "evidence-backed maturity initialization",
        )

    production_marker = (
        '            current["dependencies"] = sorted(set(incoming.get("dependencies", [])))\n'
    )
    production_extension = (
        '            if isinstance(incoming.get("production_evidence"), dict) and incoming.get("production_evidence"):\n'
        '                current["_evidence_backed_maturity"] = incoming.get("maturity")\n'
    )
    if 'current["_evidence_backed_maturity"] = incoming.get("maturity")' not in builder:
        builder = _replace_once(
            builder,
            production_marker,
            production_marker + production_extension,
            "evidence-backed maturity production merge",
        )

    finalization_marker = (
        '    for row in by_token.values():\n'
        '        key = row["machine_key"]\n'
    )
    finalization_extension = (
        '    for row in by_token.values():\n'
        '        evidence_backed_maturity = row.pop("_evidence_backed_maturity", None)\n'
        '        if evidence_backed_maturity in MATURITY_ORDER:\n'
        '            row["maturity"] = evidence_backed_maturity\n'
        '        key = row["machine_key"]\n'
    )
    if 'evidence_backed_maturity = row.pop("_evidence_backed_maturity", None)' not in builder:
        builder = _replace_once(
            builder,
            finalization_marker,
            finalization_extension,
            "evidence-backed maturity finalization",
        )
    builder_path.write_text(builder, encoding="utf-8")


def synchronize_os_golden() -> dict[str, Any]:
    result = base_synchronize_os_golden()
    path = ROOT / "tests/test_penta_os_v1.py"
    text = path.read_text(encoding="utf-8")
    stale = '("truth", "implemented", "D2")'
    production = '("truth", "production", "D2")'
    text = text.replace(stale, production)
    if stale in text:
        raise base.PipelineError("stale PentaContext implemented-state assertion remains")
    if text.count(production) < 1:
        raise base.PipelineError("canonical PentaContext production assertion is missing")
    path.write_text(text, encoding="utf-8")
    result["penta_context_production_assertion_count"] = text.count(production)
    result["authority_anchor_scope"] = "unchanged_by_wave3"
    return result


def reconcile_packager() -> None:
    """Verify the current-main deterministic package contract."""

    path = ROOT / "scripts/package_penta_os_v1.py"
    text = path.read_text(encoding="utf-8")
    required = (
        "from typing import Any, Mapping",
        "def file_records(files: Mapping[str, bytes])",
        "def collect(root: Path, metadata: Mapping[str, Any] | None = None)",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise base.PipelineError(
            f"current-main packager contract incomplete: {missing}"
        )


base.reconcile_context_and_builder = reconcile_context_and_builder
base.synchronize_os_golden = synchronize_os_golden
_original_main = base.main


def main() -> int:
    reconcile_packager()
    return _original_main()


if __name__ == "__main__":
    raise SystemExit(main())
