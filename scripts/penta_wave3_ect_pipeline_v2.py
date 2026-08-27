#!/usr/bin/env python3
"""Direct overrides for the Penta Wave 3 exact-main ECT pipeline.

The base pipeline remains responsible for integration, projection generation,
validation, tests, ECT sealing, and cleanup. This wrapper replaces only the
current-main-sensitive builder reconciliation, provider-custody evidence, and
package checksum functions.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

BASE_PIPELINE = Path(os.environ.get("BASE_PIPELINE_PATH", "/tmp/penta_wave3_ect_pipeline.py"))
ROOT = Path.cwd()

PROVIDER_PROJECT_ID = "tzajnzshmtzjenqulehq"
PROVIDER_PROJECT_NAME = "CrownThrive"
PROVIDER_PROJECT_REGION = "us-west-2"
PROVIDER_POSTGRES_VERSION = "17.6.1.155"
PROVIDER_MIGRATION_COUNT = 1006
PROVIDER_LAST_MIGRATION_VERSION = "20260827175750"
PROVIDER_LAST_MIGRATION_NAME = "pentafactory_final_production_proof_v1"
PROVIDER_LEDGER_MD5 = "74e4e2e22478e375af8662f4bbe5fa51"
PROVIDER_OBSERVED_AT_UTC = "2026-08-27T18:23:10.602519Z"
PROVIDER_TAIL = [
    {"version": "20260827175750", "name": "pentafactory_final_production_proof_v1"},
    {"version": "20260827175124", "name": "cie_authority_delegate_v1"},
    {"version": "20260827174900", "name": "cie_founder_direct_authority_compatibility_v1"},
    {"version": "20260827174622", "name": "os20_readiness_accept_certified_cie_v1"},
    {"version": "20260827174609", "name": "pentafactory_github_oidc_dispatch_receipts_v1"},
    {"version": "20260827174511", "name": "control_plane_explicit_rls_deny_policies_v1"},
    {"version": "20260827173935", "name": "developer_marketplace_surface_replica_certification_v1"},
    {"version": "20260827172622", "name": "canonical_os_repository_function_rebind"},
    {"version": "20260827172606", "name": "os20_release_cost_binding_v2"},
    {"version": "20260827172449", "name": "pentamarket_certified_rate_cards_v1"},
]


def load_base():
    spec = importlib.util.spec_from_file_location("penta_wave3_ect_pipeline_base", BASE_PIPELINE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base ECT pipeline: {BASE_PIPELINE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
base_seal_ect = base.seal_ect


def provider_ledger_evidence(repository_migration_count: int) -> dict[str, Any]:
    if repository_migration_count <= 0:
        raise base.PipelineError("repository migration inventory is empty")
    if PROVIDER_MIGRATION_COUNT <= repository_migration_count:
        raise base.PipelineError(
            "provider custody hold cannot be closed by count inference; expected provider ledger to exceed repository inventory"
        )
    return {
        "schema": "ct.supabase.migration-ledger-readback.v1",
        "evidence_id": "ct.supabase.migration-ledger-readback.20260827",
        "project": {
            "project_ref": PROVIDER_PROJECT_ID,
            "name": PROVIDER_PROJECT_NAME,
            "region": PROVIDER_PROJECT_REGION,
            "status": "ACTIVE_HEALTHY",
            "postgres_version": PROVIDER_POSTGRES_VERSION,
        },
        "observed_at": PROVIDER_OBSERVED_AT_UTC,
        "source": "supabase_migrations.schema_migrations",
        "provider_readback": True,
        "provider_migration_count": PROVIDER_MIGRATION_COUNT,
        "provider_last_migration_version": PROVIDER_LAST_MIGRATION_VERSION,
        "provider_last_migration_name": PROVIDER_LAST_MIGRATION_NAME,
        "provider_ledger_md5": PROVIDER_LEDGER_MD5,
        "provider_tail": PROVIDER_TAIL,
        "repository_migration_file_count": repository_migration_count,
        "provider_repository_count_delta": PROVIDER_MIGRATION_COUNT - repository_migration_count,
        "repository_history_reconciled": False,
        "migration_apply_performed": False,
        "provider_write_performed": False,
        "external_state_mutated": False,
        "authority_expanded": False,
        "status": "PROVIDER_LEDGER_READBACK_VERIFIED_REPOSITORY_HISTORY_HOLD",
        "gate": "HOLD",
        "required_resolution": (
            "Recover the authoritative provider migration history into a reviewed repository baseline, "
            "prove clean replay on a non-production environment, and only then rerun branch synchronization."
        ),
    }


def reconcile_context_and_builder() -> None:
    context_path = ROOT / "data/penta/systems.extensions.context.json"
    catalog = base.load_json(context_path)
    systems = catalog.get("systems")
    if not isinstance(systems, list) or len(systems) != 1 or not isinstance(systems[0], dict):
        raise base.PipelineError("PentaContext catalog must contain exactly one system")
    systems[0]["axis"] = "truth"
    systems[0]["purpose"] = (
        "Provide scoped, provenance-aware, redacted operational-memory and bounded context "
        "retrieval across approved CrownThrive systems without manufacturing permissions or execution authority."
    )
    base.write_json(context_path, catalog)

    builder_path = ROOT / "scripts/build_penta_os_v1.py"
    builder = builder_path.read_text(encoding="utf-8")

    # Preserve explicit axis declarations at source normalization.
    old_normalizer = (
        '        axis=infer_axis(machine_key, canonical_name, str(item.get("category", "")), purpose),'
    )
    new_normalizer = (
        '        axis=str(item.get("axis") or infer_axis(machine_key, canonical_name, str(item.get("category", "")), purpose)),'
    )
    current_normalizer = (
        '            "axis": row.get("axis") or infer_axis(row.get("canonical_name", ""), row.get("purpose", "")),'
    )
    if old_normalizer in builder:
        builder = builder.replace(old_normalizer, new_normalizer, 1)
    elif new_normalizer not in builder and current_normalizer not in builder:
        raise base.PipelineError("PentaOS explicit-axis normalization contract missing")

    # A production-family row is the canonical semantic source for role, risk,
    # axis, and dependencies. Later institutional/component rows cannot erase it.
    production_marker = (
        '            current["risk_ceiling"] = incoming.get("risk_ceiling", current["risk_ceiling"])\n'
    )
    production_extension = (
        '            current["axis"] = incoming.get("axis", current["axis"])\n'
        '            current["dependency_assessed"] = incoming.get("dependency_assessed") is True\n'
        '            current["dependencies"] = sorted(set(incoming.get("dependencies", [])))\n'
    )
    if 'current["dependency_assessed"] = incoming.get("dependency_assessed") is True' not in builder:
        if production_marker not in builder:
            raise base.PipelineError("PentaOS production-family merge branch missing")
        builder = builder.replace(production_marker, production_marker + production_extension, 1)

    institutional_old = (
        '        elif incoming.get("source_kind") == "institutional_registry":\n'
        '            current["operator_route"] = incoming["operator_route"]\n'
        '            current["axis"] = incoming.get("axis", current["axis"])\n'
    )
    institutional_new = (
        '        elif incoming.get("source_kind") == "institutional_registry":\n'
        '            current["operator_route"] = incoming["operator_route"]\n'
        '            if "production_family_catalog" not in current["source_kinds"]:\n'
        '                current["axis"] = incoming.get("axis", current["axis"])\n'
    )
    if institutional_old in builder:
        builder = builder.replace(institutional_old, institutional_new, 1)
    elif institutional_new not in builder:
        raise base.PipelineError("PentaOS institutional-axis guard missing")

    component_old = (
        '        if incoming.get("axis") in AXES and "component_registry" in '
        '{incoming.get("source_kind"), *current["source_kinds"]} and not (\n'
    )
    component_new = (
        '        if "production_family_catalog" not in current["source_kinds"] and '
        'incoming.get("axis") in AXES and "component_registry" in '
        '{incoming.get("source_kind"), *current["source_kinds"]} and not (\n'
    )
    if component_old in builder:
        builder = builder.replace(component_old, component_new, 1)
    elif component_new not in builder:
        raise base.PipelineError("PentaOS component-axis guard missing")

    builder_path.write_text(builder, encoding="utf-8")

    # Record exact point-in-time provider readback while preserving the
    # repository/provider history HOLD. No migration is applied by this pipeline.
    convergence_path = ROOT / "developers/manifests/supabase-production-convergence-state.v1.json"
    convergence = base.load_json(convergence_path)
    custody = convergence.get("migration_custody")
    if not isinstance(custody, dict):
        raise base.PipelineError("Supabase convergence migration_custody must be an object")
    repository_migration_count = len(list((ROOT / "supabase/migrations").glob("*.sql")))
    evidence = provider_ledger_evidence(repository_migration_count)

    convergence["observed_at"] = PROVIDER_OBSERVED_AT_UTC
    project = convergence.get("project")
    if not isinstance(project, dict):
        raise base.PipelineError("Supabase convergence project must be an object")
    project.update(evidence["project"])

    custody.update(
        {
            "observed_at": PROVIDER_OBSERVED_AT_UTC,
            "inventory_observed_at": PROVIDER_OBSERVED_AT_UTC,
            "provider_readback_scope": evidence["source"],
            "provider_migration_count": PROVIDER_MIGRATION_COUNT,
            "provider_last_migration_version": PROVIDER_LAST_MIGRATION_VERSION,
            "provider_last_migration_name": PROVIDER_LAST_MIGRATION_NAME,
            "repository_migration_file_count": repository_migration_count,
            "default_branch_status": "MIGRATIONS_FAILED",
            "last_observed_error": (
                "Remote provider migration versions are not found in local migrations directory: "
                f"provider ledger has {PROVIDER_MIGRATION_COUNT} applied entries while the exact default-branch "
                f"repository has {repository_migration_count} SQL migration files. No migration was applied and "
                "no production migration history was rewritten by this ECT run."
            ),
            "gate": "HOLD",
            "provider_ledger_readback": {
                "observed_at": PROVIDER_OBSERVED_AT_UTC,
                "provider_migration_count": PROVIDER_MIGRATION_COUNT,
                "provider_last_migration_version": PROVIDER_LAST_MIGRATION_VERSION,
                "provider_last_migration_name": PROVIDER_LAST_MIGRATION_NAME,
                "provider_ledger_md5": PROVIDER_LEDGER_MD5,
                "provider_tail": PROVIDER_TAIL,
                "readback": True,
                "repository_history_reconciled": False,
                "provider_write_performed": False,
            },
        }
    )
    base.write_json(convergence_path, convergence)
    base.write_json(
        ROOT / "evidence/supabase/supabase-migration-ledger-readback-20260827.json",
        evidence,
    )


def verify_package() -> None:
    build_a = "dist/penta-os-v1/build-a"
    build_b = "dist/penta-os-v1/build-b"
    base.run([
        sys.executable,
        "scripts/package_penta_os_v1.py",
        "--output",
        build_a,
        "--source-revision",
        base.MAIN_SHA,
    ])
    base.run([
        sys.executable,
        "scripts/package_penta_os_v1.py",
        "--output",
        build_b,
        "--source-revision",
        base.MAIN_SHA,
    ])
    base.run([
        sys.executable,
        "scripts/package_penta_os_v1.py",
        "--output",
        build_a,
        "--verify",
        "--compare-output",
        build_b,
    ], capture=Path("/tmp/penta-os-package-verification.json"))
    subprocess.run(
        ["sha256sum", "-c", "penta-os-v1-1.5.0.sha256"],
        cwd=ROOT / build_a,
        check=True,
    )


def seal_ect() -> dict[str, Any]:
    receipt = base_seal_ect()
    provider_evidence = base.load_json(
        ROOT / "evidence/supabase/supabase-migration-ledger-readback-20260827.json"
    )
    receipt["supabase_provider_ledger"] = {
        "evidence_ref": "evidence/supabase/supabase-migration-ledger-readback-20260827.json",
        "provider_migration_count": provider_evidence["provider_migration_count"],
        "provider_last_migration_version": provider_evidence["provider_last_migration_version"],
        "provider_last_migration_name": provider_evidence["provider_last_migration_name"],
        "provider_ledger_md5": provider_evidence["provider_ledger_md5"],
        "repository_migration_file_count": provider_evidence["repository_migration_file_count"],
        "repository_history_reconciled": False,
        "migration_apply_performed": False,
        "gate": "HOLD",
    }
    base.write_json(ROOT / "evidence/penta/penta-wave3-ect-20260827.json", receipt)
    return receipt


base.reconcile_context_and_builder = reconcile_context_and_builder
base.verify_package = verify_package
base.seal_ect = seal_ect


if __name__ == "__main__":
    raise SystemExit(base.main())
