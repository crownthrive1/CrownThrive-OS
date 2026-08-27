#!/usr/bin/env python3
"""Final exact-main overrides for Penta Wave 3 ECT.

This wrapper preserves the existing v2 provider-ledger, context, builder, package,
and ECT behavior. It adds two order-independent production invariants:

1. maturity backed by an explicit production-evidence object survives every
   registry merge order; and
2. the authority-anchor golden assertion is synchronized from the exact
   generated candidate graph rather than a stale historical constant.

No provider write, migration apply, automatic promotion, D3 authority, secret
access, autonomous repair, or self-certification is introduced here.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
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


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise base.PipelineError(f"ECT source contract not found: {label}")


def reconcile_context_and_builder() -> None:
    # Apply v2 first: exact provider-ledger evidence, context semantics, explicit
    # axis precedence, dependency ownership, and provider-safe HOLD handling.
    v2_reconcile_context_and_builder()

    builder_path = ROOT / "scripts/build_penta_os_v1.py"
    builder = builder_path.read_text(encoding="utf-8")

    # Preserve an evidence-backed maturity even when the production-family row
    # is the first source encountered for a normalized identity.
    init_marker = (
        '                "explicit_registration_state": incoming.get("registration_state"),\n'
    )
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
        builder = _replace_once(
            builder,
            init_marker,
            init_marker + init_extension,
            "evidence-backed maturity initialization",
        )

    # Preserve the same maturity when the production-family row arrives after a
    # prior institutional/component/discovery row.
    production_dependency_marker = (
        '            current["dependencies"] = sorted(set(incoming.get("dependencies", [])))\n'
    )
    production_maturity_extension = (
        '            if isinstance(incoming.get("production_evidence"), dict) and incoming.get("production_evidence"):\n'
        '                current["_evidence_backed_maturity"] = incoming.get("maturity")\n'
    )
    if 'current["_evidence_backed_maturity"] = incoming.get("maturity")' not in builder:
        builder = _replace_once(
            builder,
            production_dependency_marker,
            production_dependency_marker + production_maturity_extension,
            "evidence-backed maturity production merge",
        )

    # Apply the authoritative maturity after all normalized-name merge sources
    # have been processed, then remove the private merge-only field before the
    # public registry is hashed and emitted.
    final_marker = (
        '    for row in by_token.values():\n'
        '        key = row["machine_key"]\n'
    )
    final_extension = (
        '    for row in by_token.values():\n'
        '        evidence_backed_maturity = row.pop("_evidence_backed_maturity", None)\n'
        '        if evidence_backed_maturity in MATURITY_ORDER:\n'
        '            row["maturity"] = evidence_backed_maturity\n'
        '        key = row["machine_key"]\n'
    )
    if 'evidence_backed_maturity = row.pop("_evidence_backed_maturity", None)' not in builder:
        builder = _replace_once(
            builder,
            final_marker,
            final_extension,
            "evidence-backed maturity finalization",
        )

    builder_path.write_text(builder, encoding="utf-8")


def _find_authority_anchor_depth(value: Any) -> dict[str, int]:
    matches: list[dict[str, int]] = []
    expected_keys = {"chlom", "chlom/dail", "neither"}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if set(node) == expected_keys and all(
                isinstance(node[key], int) and not isinstance(node[key], bool)
                for key in expected_keys
            ):
                matches.append({key: int(node[key]) for key in expected_keys})
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    unique = {
        (row["chlom"], row["chlom/dail"], row["neither"]): row
        for row in matches
    }
    if len(unique) != 1:
        raise base.PipelineError(
            "exact generated authority-anchor census was not uniquely resolvable: "
            f"{sorted(unique)}"
        )
    return next(iter(unique.values()))


def synchronize_os_golden() -> dict[str, Any]:
    result = base_synchronize_os_golden()
    registry = base.load_json(ROOT / "data/penta/os-v1.registry.json")
    anchor = _find_authority_anchor_depth(registry)

    test_path = ROOT / "tests/test_penta_os_v1.py"
    test_text = test_path.read_text(encoding="utf-8")
    pattern = (
        r'\{"chlom":\s*\d+,\s*"chlom/dail":\s*\d+,\s*"neither":\s*\d+\}'
    )
    replacement = (
        '{"chlom": '
        f'{anchor["chlom"]}, '
        '"chlom/dail": '
        f'{anchor["chlom/dail"]}, '
        '"neither": '
        f'{anchor["neither"]}'
        '}'
    )
    updated, count = re.subn(pattern, replacement, test_text, count=1)
    if count != 1:
        raise base.PipelineError(
            "PentaOS authority-anchor golden assertion was not found exactly once"
        )
    test_path.write_text(updated, encoding="utf-8")

    result["authority_anchor_depth"] = anchor
    return result


base.reconcile_context_and_builder = reconcile_context_and_builder
base.synchronize_os_golden = synchronize_os_golden


if __name__ == "__main__":
    raise SystemExit(base.main())
