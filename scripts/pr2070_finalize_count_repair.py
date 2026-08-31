#!/usr/bin/env python3
"""Repair the Penta portal finalizer census invariant for governed extensions.

Temporary helper for PR #2070. It modifies the durable finalizer so its expected
identity set comes from the same registry-driven generator that produced the
census. The helper itself is removed before the repair commit is published.
"""
from __future__ import annotations

from pathlib import Path

PATH = Path("scripts/penta_portal_finalize.py")
OLD = '''    expected_total = int(os_registry["counts"]["total"]) + int(seed["candidate_count"])
    if len(records) != expected_total:
        raise ValueError(f"single-identity census mismatch: {len(records)} != {expected_total}")
'''
NEW = '''    # Derive the expected single-identity namespace from the same governed
    # registry/family/extension inputs used by the portal generator. A frozen
    # canonical count + seed count is insufficient once governed extensions are
    # admitted through systems*.json or the family registry.
    portal_path = ROOT / "scripts/penta_portal_docs.py"
    portal_spec = importlib.util.spec_from_file_location("penta_portal_docs_for_finalize", portal_path)
    if portal_spec is None or portal_spec.loader is None:
        raise RuntimeError("cannot load Penta portal generator")
    portal = importlib.util.module_from_spec(portal_spec)
    sys.modules[portal_spec.name] = portal
    portal_spec.loader.exec_module(portal)
    expected_records, _, _ = portal.build_records()
    expected_records = [
        r for r in expected_records
        if isinstance(r, dict) and single_identity(str(r.get("name", "")))
    ]
    expected_names = {str(r.get("normalized_name") or "") for r in expected_records}
    actual_names = {str(r.get("normalized_name") or "") for r in records}
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unexpected = sorted(actual_names - expected_names)
        raise ValueError(
            "single-identity census membership mismatch: "
            f"missing={missing[:20]} unexpected={unexpected[:20]}"
        )
    expected_total = len(expected_records)
    if len(records) != expected_total:
        raise ValueError(f"single-identity census mismatch: {len(records)} != {expected_total}")
'''

text = PATH.read_text(encoding="utf-8")
if OLD not in text:
    raise SystemExit("expected frozen-count block not found; refuse blind patch")
PATH.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
print("PASS: finalizer now derives expected census from governed generator inputs")
