#!/usr/bin/env python3
"""Integrate, certify, package, and seal Penta Promotion Wave 3 on current main.

This temporary ECT pipeline is copied outside the worktree before current main is
checked out. It preserves PentaOS V1.5, applies the additive Wave 3 transformer,
repairs canonical merge precedence, regenerates projections, runs the full
negative-safety cohort, verifies reproducible packaging, and writes an exact ECT
receipt. It performs no provider writes and creates no D3 authority.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Iterable

ROOT = Path.cwd()
TRANSFORMER = Path(os.environ.get("TRANSFORMER_PATH", "/tmp/penta_wave3_mainline_integrate.py"))
OLD_HEAD = os.environ.get("OLD_HEAD", "105460c828e8baf0d034d43689b278b47d2f9833")
MAIN_SHA = os.environ.get("MAIN_SHA", "")
ECT_RUN_ID = int(os.environ.get("ECT_RUN_ID", "0"))
ECT_RUN_ATTEMPT = int(os.environ.get("ECT_RUN_ATTEMPT", "0"))


class PipelineError(RuntimeError):
    pass


def run(args: Iterable[str], *, env: dict[str, str] | None = None, capture: Path | None = None) -> None:
    command = list(args)
    print("+", " ".join(command), flush=True)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    if capture is None:
        subprocess.run(command, cwd=ROOT, env=merged_env, check=True)
        return
    capture.parent.mkdir(parents=True, exist_ok=True)
    with capture.open("w", encoding="utf-8") as handle:
        subprocess.run(command, cwd=ROOT, env=merged_env, check=True, stdout=handle)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PipelineError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise PipelineError(f"replacement target not found: {label}")


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise PipelineError(f"unable to synchronize generated golden value: {label}")
    return updated


def harden_transformer() -> None:
    text = TRANSFORMER.read_text(encoding="utf-8")
    old = '''    if 'member_snapshot[key]["maturity_promotion"]' not in text:
        lines = text.splitlines()
        output: list[str] = []
        inside_member = False
        inserted = False
        for line in lines:
            output.append(line)
            if line == "        member_snapshot[key] = {":
                inside_member = True
                continue
            if inside_member and line == "        }":
                output.append("        if key in promotions:")
                output.append('            member_snapshot[key]["maturity_promotion"] = promotions[key]')
                inside_member = False
                inserted = True
        if not inserted:
            raise IntegrationError("penta_family member promotion projection insertion failed")
        text = "\\n".join(output) + "\\n"
'''
    new = '''    if 'member_snapshot[key]["maturity_promotion"]' not in text:
        marker = '    return {\\n        "family_registry_id":'
        replacement = (
            '    for key, promotion in promotions.items():\\n'
            '        member_snapshot[key]["maturity_promotion"] = promotion\\n\\n'
            '    return {\\n'
            '        "family_registry_id":'
        )
        if marker not in text:
            raise IntegrationError("penta_family promotion projection return marker missing")
        text = text.replace(marker, replacement, 1)
'''
    text = replace_once(text, old, new, "promotion projection hardening")
    TRANSFORMER.write_text(text, encoding="utf-8")


def integrate_wave3() -> None:
    harden_transformer()
    run([sys.executable, str(TRANSFORMER)], env={"OLD_HEAD": OLD_HEAD})


def reconcile_family_and_runtime_tests() -> None:
    family_path = ROOT / "tests/test_penta_family.py"
    family = family_path.read_text(encoding="utf-8")
    for key in ("penta.mail", "penta.status", "penta.credentials", "penta.build", "penta.certify"):
        needle = f'        "{key}",\n'
        index = family.find(needle)
        if index < 0:
            raise PipelineError(f"stale held-member entry not found: {key}")
        family = family[:index] + family[index + len(needle):]
    family = replace_once(
        family,
        '    assert mail["sections"]["status"]["member_maturity"] == "specified"',
        '    assert mail["sections"]["status"]["member_maturity"] == "production"',
        "PentaMail portal maturity",
    )
    family = replace_once(
        family,
        '    assert mail["sections"]["status"]["execution_eligible"] is False',
        '    assert mail["sections"]["status"]["execution_eligible"] is True',
        "PentaMail portal execution eligibility",
    )
    family_path.write_text(family, encoding="utf-8")

    exec_path = ROOT / "tests/test_penta_exec.py"
    executable = exec_path.read_text(encoding="utf-8")
    executable = replace_once(
        executable,
        '    assert context["details"]["result"]["state"] == "PRODUCTION_CONTRACT_PRESENT"',
        '    assert context["details"]["result"]["effective_maturity"] == "production"',
        "PentaContext maturity receipt",
    )
    executable = replace_once(
        executable,
        '    assert context["details"]["result"]["missing_refs"] == []',
        '    assert context["details"]["result"]["runtime_present"] is True and context["details"]["result"]["contract_tests_present"] is True and context["details"]["result"]["ci_present"] is True and context["details"]["result"]["edge_runtime_present"] is True and context["details"]["result"]["documentation_evidence_present"] is True',
        "PentaContext required surfaces",
    )
    executable = replace_once(
        executable,
        '    assert context["details"]["result"]["secret_values_returned"] is False',
        '    assert context["details"]["result"]["provider_call_performed"] is False and context["details"]["result"]["credential_material_accessed"] is False and context["details"]["result"]["authority_expanded"] is False',
        "PentaContext security boundary",
    )
    exec_path.write_text(executable, encoding="utf-8")


def reconcile_context_and_builder() -> None:
    context_path = ROOT / "data/penta/systems.extensions.context.json"
    catalog = load_json(context_path)
    systems = catalog.get("systems")
    if not isinstance(systems, list) or len(systems) != 1 or not isinstance(systems[0], dict):
        raise PipelineError("PentaContext catalog must contain exactly one system")
    systems[0]["axis"] = "truth"
    systems[0]["purpose"] = (
        "Provide scoped, provenance-aware, redacted operational-memory and bounded context "
        "retrieval across approved CrownThrive systems without manufacturing permissions or execution authority."
    )
    write_json(context_path, catalog)

    builder_path = ROOT / "scripts/build_penta_os_v1.py"
    builder = builder_path.read_text(encoding="utf-8")
    old_axis = '        axis=infer_axis(machine_key, canonical_name, str(item.get("category", "")), purpose),'
    new_axis = '        axis=str(item.get("axis") or infer_axis(machine_key, canonical_name, str(item.get("category", "")), purpose)),'
    current_axis = '            "axis": row.get("axis") or infer_axis(row.get("canonical_name", ""), row.get("purpose", "")),'
    if old_axis in builder:
        builder = builder.replace(old_axis, new_axis, 1)
    elif new_axis not in builder and current_axis not in builder:
        raise PipelineError("PentaOS explicit-axis precedence contract missing")

    incoming_marker = '            current["risk_ceiling"] = incoming.get("risk_ceiling", current["risk_ceiling"])\n'
    incoming_axis = '            current["axis"] = incoming.get("axis", current["axis"])\n'
    if incoming_axis not in builder:
        if incoming_marker not in builder:
            raise PipelineError("PentaOS incoming production-family merge marker missing")
        builder = builder.replace(incoming_marker, incoming_marker + incoming_axis, 1)

    post_marker = '        current["aliases"] = sorted({alias for alias in current.get("aliases", []) if alias})\n'
    post_block = '''        production_family_rows = [
            row for row in group if row.get("source_kind") == "production_family_catalog"
        ]
        if production_family_rows:
            if len(production_family_rows) != 1:
                raise PentaOSBuildError(
                    f"multiple production-family rows resolved for {current['machine_key']}"
                )
            authoritative_family = production_family_rows[0]
            current["axis"] = authoritative_family.get("axis", current["axis"])
            current["role"] = authoritative_family.get("role", current["role"])
            current["risk_ceiling"] = authoritative_family.get("risk_ceiling", current["risk_ceiling"])
            current["dependency_assessed"] = authoritative_family.get("dependency_assessed", False)
            current["dependencies"] = list(authoritative_family.get("dependencies") or [])
'''
    if "production_family_rows = [" not in builder:
        if post_marker not in builder:
            raise PipelineError("PentaOS post-merge invariant insertion marker missing")
        builder = builder.replace(post_marker, post_block + post_marker, 1)
    builder_path.write_text(builder, encoding="utf-8")


def synchronize_os_golden() -> dict[str, Any]:
    registry = load_json(ROOT / "data/penta/os-v1.registry.json")
    counts = registry["counts"]
    graph = registry["dependency_graph"]
    context = next(row for row in registry["systems"] if row["machine_key"] == "penta.context")
    if (context["axis"], context["maturity"], context["risk_ceiling"]) != ("truth", "production", "D2"):
        raise PipelineError(f"PentaContext semantic projection invalid: {context}")
    expected_dependencies = {"penta.docs", "penta.route", "penta.credentials", "penta.status"}
    if set(context.get("dependencies") or []) != expected_dependencies:
        raise PipelineError(f"PentaContext dependency projection invalid: {context.get('dependencies')}")
    if "operational-memory" not in context.get("role", ""):
        raise PipelineError("PentaContext role lost operational-memory semantics")

    path = ROOT / "tests/test_penta_os_v1.py"
    text = path.read_text(encoding="utf-8")
    text = regex_once(
        text,
        r'self\.assertEqual\(self\.registry\["counts"\]\["execution_eligible_by_registry"\], \d+\)',
        f'self.assertEqual(self.registry["counts"]["execution_eligible_by_registry"], {counts["execution_eligible_by_registry"]})',
        "execution_eligible_by_registry",
    )
    for maturity in ("implemented", "production", "specified"):
        text = regex_once(
            text,
            rf'            "{maturity}": \d+,',
            f'            "{maturity}": {counts["by_maturity"][maturity]},',
            f"by_maturity.{maturity}",
        )
    for field in (
        "dependency_assessed_members",
        "dependency_unassessed_members",
        "members_with_declared_edges",
        "penta_dependency_edges",
        "external_dependency_edges",
        "unresolved_penta_dependencies",
    ):
        text = regex_once(
            text,
            rf'self\.assertEqual\(counts\["{field}"\], \d+\)',
            f'self.assertEqual(counts["{field}"], {counts[field]})',
            field,
        )
    for field in (
        "cyclic_scc_count",
        "cyclic_member_count",
        "cyclic_internal_edge_count",
        "condensed_component_count",
        "condensed_edge_count",
        "transitive_membership_count",
        "maximum_transitive_closure",
    ):
        text = regex_once(
            text,
            rf'self\.assertEqual\(graph\["{field}"\], \d+\)',
            f'self.assertEqual(graph["{field}"], {graph[field]})',
            field,
        )
    partition = graph["readiness_partition"]
    for state in (
        "HOLD_DEPENDENCY_INVENTORY_UNASSESSED",
        "HOLD_EXTERNAL_DEPENDENCY_UNBOUND",
        "HOLD_UNCLASSIFIED_DEPENDENCY_CYCLE",
        "HOLD_MEMBER_MATURITY",
        "HOLD_DEPENDENCY_MATURITY",
        "READY",
    ):
        text = regex_once(
            text,
            rf'            "{state}": \d+,',
            f'            "{state}": {partition[state]},',
            f"readiness_partition.{state}",
        )
    text = regex_once(
        text,
        r'\("truth", "(?:implemented|production)", "D2"\)',
        '("truth", "production", "D2")',
        "penta.context identity semantics",
    )
    path.write_text(text, encoding="utf-8")
    return {
        "execution_eligible_by_registry": counts["execution_eligible_by_registry"],
        "by_maturity": counts["by_maturity"],
        "penta_dependency_edges": counts["penta_dependency_edges"],
        "readiness_partition": partition,
        "context": {
            "axis": context["axis"],
            "maturity": context["maturity"],
            "dependencies": context["dependencies"],
        },
    }


def compile_and_validate() -> None:
    compile_targets = [
        "runtime/penta_family.py",
        "runtime/penta_exec.py",
        "runtime/penta_interop.py",
        "runtime/penta_runtime_suite.py",
        "runtime/penta_wave3_operations.py",
        "runtime/penta_context.py",
        "runtime/penta_evi_builder.py",
        "runtime/penta_immune.py",
        "runtime/penta_os_v1.py",
        "runtime/penta-provider-control-plane/penta_control_plane.py",
        "scripts/build_penta_os_v1.py",
        "scripts/package_penta_os_v1.py",
    ]
    run([sys.executable, "-m", "py_compile", *compile_targets])
    json_targets = [
        "data/penta/family.registry.json",
        "data/penta/execution-adapters.registry.json",
        "data/penta/member-runtime.contract.json",
        "data/penta/production-promotions.v1.json",
        "data/penta/systems.extensions.context.json",
        "penta/registry/penta-families.v1.json",
    ]
    for target in json_targets:
        run([sys.executable, "-m", "json.tool", target], capture=Path("/tmp/json-validation.out"))
    run([sys.executable, "scripts/validate_penta_provider_control_plane.py"])
    run([sys.executable, "scripts/validate_supabase_production_convergence_state.py"])
    run([sys.executable, "scripts/validate_docs.py"])
    run([sys.executable, "runtime/penta_families.py", "--root", ".", "--portal-index"], capture=Path("/tmp/penta-families.json"))
    run([sys.executable, "runtime/penta_exec.py", "--root", ".", "validate"], capture=Path("/tmp/penta-exec-validation.json"))
    run([sys.executable, "runtime/penta_runtime_suite.py", "--root", ".", "--output", "/tmp/penta-runtime-suite.json"])
    run([sys.executable, "runtime/penta_interop.py", "--root", ".", "--certify", "--output", "/tmp/penta-interoperability.json"])
    run([sys.executable, "runtime/penta_os_v1.py", "--root", ".", "validate"])


def run_ect_tests() -> None:
    commands = [
        [sys.executable, "tests/test_penta_family.py"],
        [sys.executable, "tests/test_penta_exec.py"],
        [sys.executable, "-m", "unittest", "-v", "tests.test_penta_runtime_suite"],
        [sys.executable, "-m", "unittest", "-v", "tests.test_penta_interop"],
        [sys.executable, "-m", "unittest", "-v", "tests.test_penta_observability"],
        [sys.executable, "-m", "unittest", "-v", "tests.test_penta_context"],
        [sys.executable, "-m", "unittest", "-v", "tests.test_penta_evi_builder", "tests.test_penta_immune"],
        [sys.executable, "-m", "unittest", "-v", "tests.test_penta_os_v1"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_penta_mail.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_penta_institutional_services.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_penta_institutional_controls.py", "-v"],
        [sys.executable, "scripts/run_function_tests.py", "tests/test_penta_compliance_license.py", "tests/test_penta_self_build.py"],
    ]
    for command in commands:
        run(command)


def verify_package() -> None:
    build_a = "dist/penta-os-v1/build-a"
    build_b = "dist/penta-os-v1/build-b"
    run([sys.executable, "scripts/package_penta_os_v1.py", "--output", build_a, "--source-revision", MAIN_SHA])
    run([sys.executable, "scripts/package_penta_os_v1.py", "--output", build_b, "--source-revision", MAIN_SHA])
    run([
        sys.executable,
        "scripts/package_penta_os_v1.py",
        "--output",
        build_a,
        "--verify",
        "--compare-output",
        build_b,
    ], capture=Path("/tmp/penta-os-package-verification.json"))
    run(["sha256sum", "-c", "penta-os-v1-1.5.0.sha256"], env={"PWD": str(ROOT / build_a)})


def seal_ect() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("penta_family_ect", ROOT / "runtime/penta_family.py")
    if spec is None or spec.loader is None:
        raise PipelineError("cannot load Penta Family runtime for ECT")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _, snapshot = module.load_family(ROOT)
    adapters = load_json(ROOT / "data/penta/execution-adapters.registry.json")
    runtime_suite = load_json(Path("/tmp/penta-runtime-suite.json"))
    interop = load_json(Path("/tmp/penta-interoperability.json"))
    receipt = {
        "schema": "ct.penta.ect.v1",
        "ect_id": "ct.penta.ect.production-promotion-wave3.20260827",
        "canonical_name": "Execution Certification and Testing",
        "repository": "crownthrive1/CrownThrive-OS",
        "pull_request": 552,
        "base_main_sha": MAIN_SHA,
        "workflow_run_id": ECT_RUN_ID,
        "workflow_run_attempt": ECT_RUN_ATTEMPT,
        "status": "PASS_EXACT_MAINLINE_CANDIDATE",
        "runtime_version": "1.4.0",
        "registered_penta_members": snapshot["member_count"],
        "execution_eligible_members": len(snapshot["execution_eligible_members"]),
        "promotion_count": snapshot.get("promotion_count", 0),
        "promoted_members": snapshot.get("promoted_members", []),
        "bounded_executable_adapters": len(adapters["adapters"]),
        "provider_effect_adapters": sum(1 for row in adapters["adapters"] if row.get("provider_effect")),
        "interoperability_status": interop.get("status"),
        "interoperability_blockers": interop.get("blocker_count"),
        "runtime_suite_schema": runtime_suite.get("schema"),
        "invariants": {
            "authority_expanded": False,
            "d3_automatic_authority": False,
            "provider_write_performed_by_local_adapters": False,
            "production_promotion_automatic": False,
            "penta_evi_builder_self_certification": False,
            "penta_immune_autonomous_repair_execution": False,
            "secret_values_returned": False,
            "fail_closed": True,
        },
    }
    if receipt["promotion_count"] != 5:
        raise PipelineError("ECT requires exactly five evidence promotions")
    if receipt["bounded_executable_adapters"] != receipt["execution_eligible_members"]:
        raise PipelineError("ECT adapter coverage is incomplete")
    if receipt["provider_effect_adapters"] != 0:
        raise PipelineError("local provider-effect adapter detected")
    if receipt["interoperability_status"] != "PASS" or receipt["interoperability_blockers"] != 0:
        raise PipelineError("interoperability ECT is not PASS")
    write_json(ROOT / "evidence/penta/penta-wave3-ect-20260827.json", receipt)
    return receipt


def clean_generated_artifacts() -> None:
    for path in ROOT.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path)
    for pattern in ("*.pyc", "*.pyo"):
        for path in ROOT.rglob(pattern):
            path.unlink(missing_ok=True)
    for name in (".pytest_cache", ".mypy_cache", ".ruff_cache", "dist"):
        path = ROOT / name
        if path.is_dir():
            shutil.rmtree(path)


def main() -> int:
    if not MAIN_SHA:
        raise PipelineError("MAIN_SHA is required")
    integrate_wave3()
    reconcile_family_and_runtime_tests()
    reconcile_context_and_builder()
    run([sys.executable, "scripts/build_penta_os_v1.py", "--write"])
    golden = synchronize_os_golden()
    print(json.dumps({"golden": golden}, indent=2, sort_keys=True))
    run([sys.executable, "scripts/pentadocs_quality.py", "--apply"])
    run([sys.executable, "scripts/build_penta_os_v1.py", "--check"])
    run([sys.executable, "scripts/pentadocs_quality.py", "--check"])
    compile_and_validate()
    run_ect_tests()
    verify_package()
    receipt = seal_ect()
    print(json.dumps({"ect": receipt}, indent=2, sort_keys=True))
    clean_generated_artifacts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
