#!/usr/bin/env python3
"""Repair the Penta portal finalizer census invariant for governed extensions.

Temporary helper for PR #2070. It modifies the durable finalizer so both apply
and check derive the expected identity set from the same registry-driven portal
generator that produced the census. The helper itself is removed before the
repair commit is published.
"""
from __future__ import annotations

from pathlib import Path

PATH = Path("scripts/penta_portal_finalize.py")

OLD_APPLY = '''    expected_total = int(os_registry["counts"]["total"]) + int(seed["candidate_count"])
    if len(records) != expected_total:
        raise ValueError(f"single-identity census mismatch: {len(records)} != {expected_total}")
'''

NEW_APPLY = '''    # Derive the expected single-identity namespace from the same governed
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

OLD_CHECK = '''    expected_total = int(os_registry["counts"]["total"]) + int(seed["candidate_count"])
    errors: list[str] = []
    if len(records) != expected_total:
        errors.append(f"census total {len(records)} != {expected_total}")
'''

NEW_CHECK = '''    portal_path = ROOT / "scripts/penta_portal_docs.py"
    portal_spec = importlib.util.spec_from_file_location("penta_portal_docs_for_finalize_check", portal_path)
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
    actual_names = {
        str(r.get("normalized_name") or "")
        for r in records
        if isinstance(r, dict)
    }
    expected_total = len(expected_records)
    errors: list[str] = []
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unexpected = sorted(actual_names - expected_names)
        errors.append(
            "census membership drift: "
            f"missing={missing[:20]} unexpected={unexpected[:20]}"
        )
    if len(records) != expected_total:
        errors.append(f"census total {len(records)} != {expected_total}")
'''

text = PATH.read_text(encoding="utf-8")
if OLD_APPLY not in text:
    raise SystemExit("expected apply frozen-count block not found; refuse blind patch")
if OLD_CHECK not in text:
    raise SystemExit("expected check frozen-count block not found; refuse blind patch")
text = text.replace(OLD_APPLY, NEW_APPLY, 1)
text = text.replace(OLD_CHECK, NEW_CHECK, 1)
PATH.write_text(text, encoding="utf-8")
print("PASS: finalizer apply/check now derive the same governed identity census")
