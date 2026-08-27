#!/usr/bin/env python3
"""Direct overrides for the Penta Wave 3 exact-main ECT pipeline.

The base pipeline remains responsible for integration, projection generation,
validation, tests, ECT sealing, and cleanup. This wrapper replaces only the
current-main-sensitive builder reconciliation and package checksum functions.
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


def load_base():
    spec = importlib.util.spec_from_file_location("penta_wave3_ect_pipeline_base", BASE_PIPELINE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base ECT pipeline: {BASE_PIPELINE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()


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
    # axis, and dependencies. These assignments are order-independent because
    # later institutional/component rows are explicitly prevented from
    # overriding production-family axis state.
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

    # Provider custody evidence is a repository-exact statement. Reconcile the
    # recorded migration count to the exact current-main inventory before the
    # convergence validator runs; do not infer provider application state.
    convergence_path = ROOT / "developers/manifests/supabase-production-convergence-state.v1.json"
    convergence = base.load_json(convergence_path)
    custody = convergence.get("migration_custody")
    if not isinstance(custody, dict):
        raise base.PipelineError("Supabase convergence migration_custody must be an object")
    migration_count = len(list((ROOT / "supabase/migrations").glob("*.sql")))
    if migration_count <= 0:
        raise base.PipelineError("repository migration inventory is empty")
    custody["repository_migration_file_count"] = migration_count
    base.write_json(convergence_path, convergence)


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


base.reconcile_context_and_builder = reconcile_context_and_builder
base.verify_package = verify_package


if __name__ == "__main__":
    raise SystemExit(base.main())
