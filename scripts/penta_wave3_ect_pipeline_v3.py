#!/usr/bin/env python3
"""Final exact-main overrides for Penta Wave 3 ECT.

Preserves v2 provider-ledger/context/package behavior and makes evidence-backed
PentaContext maturity merge-order independent. Wave 3 does not mutate unrelated
CHLOM/DAIL authority-anchor census expectations.
"""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import sys
from typing import Any

V2_PIPELINE = Path(os.environ.get("V2_PIPELINE_PATH", "/tmp/penta_wave3_ect_pipeline_v2.py"))

def load_v2():
    spec = importlib.util.spec_from_file_location("penta_wave3_ect_pipeline_v2_loaded", V2_PIPELINE)
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

def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise base.PipelineError(f"ECT source contract not found: {label}")

def reconcile_context_and_builder() -> None:
    v2_reconcile_context_and_builder()
    builder_path = ROOT / "scripts/build_penta_os_v1.py"
    builder = builder_path.read_text(encoding="utf-8")
    init_marker = '                "explicit_registration_state": incoming.get("registration_state"),\n'
    init_extension = (
        '                "_evidence_backed_maturity": (\n'
        '                    incoming.get("maturity")\n'
        '                    if incoming.get("source_kind") == "production_family_catalog"\n'
        '                    and isinstance(incoming.get("production_evidence"), dict)\n'
        '                    and bool(incoming.get("production_evidence"))\n'
        '                    else None\n'
        '                ),\n'
    )
    if '"_evidence_backed_maturity": (' not in builder:
        builder = _replace_once(builder, init_marker, init_marker + init_extension, "evidence-backed maturity initialization")
    production_dependency_marker = '            current["dependencies"] = sorted(set(incoming.get("dependencies", [])))\n'
    production_maturity_extension = (
        '            if isinstance(incoming.get("production_evidence"), dict) and incoming.get("production_evidence"):\n'
        '                current["_evidence_backed_maturity"] = incoming.get("maturity")\n'
    )
    if 'current["_evidence_backed_maturity"] = incoming.get("maturity")' not in builder:
        builder = _replace_once(builder, production_dependency_marker, production_dependency_marker + production_maturity_extension, "evidence-backed maturity production merge")
    final_marker = '    for row in by_token.values():\n        key = row["machine_key"]\n'
    final_extension = (
        '    for row in by_token.values():\n'
        '        evidence_backed_maturity = row.pop("_evidence_backed_maturity", None)\n'
        '        if evidence_backed_maturity in MATURITY_ORDER:\n'
        '            row["maturity"] = evidence_backed_maturity\n'
        '        key = row["machine_key"]\n'
    )
    if 'evidence_backed_maturity = row.pop("_evidence_backed_maturity", None)' not in builder:
        builder = _replace_once(builder, final_marker, final_extension, "evidence-backed maturity finalization")
    builder_path.write_text(builder, encoding="utf-8")

def synchronize_os_golden() -> dict[str, Any]:
    result = base_synchronize_os_golden()
    test_path = ROOT / "tests/test_penta_os_v1.py"
    test_text = test_path.read_text(encoding="utf-8")
    stale_context = '("truth", "implemented", "D2")'
    production_context = '("truth", "production", "D2")'
    test_text = test_text.replace(stale_context, production_context)
    if stale_context in test_text:
        raise base.PipelineError("stale PentaContext implemented-state assertion remains")
    if test_text.count(production_context) < 2:
        raise base.PipelineError("PentaContext production semantics are not asserted by both identity and runtime tests")
    test_path.write_text(test_text, encoding="utf-8")
    result["penta_context_production_assertion_count"] = test_text.count(production_context)
    result["authority_anchor_scope"] = "unchanged_by_wave3"
    return result

base.reconcile_context_and_builder = reconcile_context_and_builder
base.synchronize_os_golden = synchronize_os_golden

if __name__ == "__main__":
    raise SystemExit(base.main())
