#!/usr/bin/env python3
"""Validate the reversible ThriveBase legacy compatibility wrapper contract."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "developers/reference/thrivebase/runtime/thrivebase-legacy-compatibility-wrappers-v1.sql"
READBACK = ROOT / "developers/reference/thrivebase/runtime/thrivebase-legacy-compatibility-readback-v1.sql"
MANIFEST = ROOT / "developers/manifests/thrivebase-legacy-compatibility-wrappers.v1.json"
DOC = ROOT / "developers/thrivebase-legacy-compatibility-wrappers.mdx"
WORKFLOW = ROOT / ".github/workflows/thrivebase-legacy-compatibility-wrappers.yml"

CANONICAL_FUNCTIONS = (
    "thrivebase_async_queue_complete_v1",
    "thrivebase_async_queue_complete_v2",
    "thrivebase_async_queue_read_v1",
    "thrivebase_async_queue_status_v1",
    "thrivebase_async_webhook_authorize_v1",
    "thrivebase_health_snapshot",
    "thrivebase_self_diagnostic_run_v1",
    "thrivebase_self_diagnostic_status_v1",
)
RETIRED_TOKEN = "thi" + "vebase"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing required source: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def main() -> int:
    migration = read(MIGRATION)
    readback = read(READBACK)
    manifest_text = read(MANIFEST)
    documentation = read(DOC)
    workflow = read(WORKFLOW)
    manifest = json.loads(manifest_text)

    for path, text in (
        (MIGRATION, migration),
        (READBACK, readback),
        (MANIFEST, manifest_text),
        (DOC, documentation),
        (WORKFLOW, workflow),
    ):
        if RETIRED_TOKEN in text.lower():
            fail(f"{path.relative_to(ROOT)} contains the retired missing-r token")

    lower = migration.lower()
    if lower.count("create or replace function public.thrivebase") != 8:
        fail("migration must create exactly eight canonical wrappers")
    if lower.count("security invoker") != 8:
        fail("all canonical wrappers must remain SECURITY INVOKER")
    if "security definer" in lower:
        fail("canonical compatibility wrappers may not be SECURITY DEFINER")
    if lower.count("grant execute on function public.thrivebase") != 7:
        fail("migration must grant exactly seven service-role wrapper functions")
    if lower.count("'thi' || 'vebase") < 8:
        fail("legacy delegation must remain dynamically constructed and explicit")

    for function_name in CANONICAL_FUNCTIONS:
        if f"function public.{function_name}" not in lower:
            fail(f"canonical wrapper missing: {function_name}")
        if function_name not in readback:
            fail(f"readback does not cover: {function_name}")

    forbidden_patterns = {
        "destructive function drop": r"\bdrop\s+function\b",
        "destructive schema drop": r"\bdrop\s+schema\b",
        "destructive table drop": r"\bdrop\s+table\b",
        "trigger rebinding": r"\balter\s+trigger\b|\bcreate\s+trigger\b",
        "queue creation": r"\bpgmq\.create\b|\bcreate\s+table\s+pgmq\.",
        "schema creation": r"\bcreate\s+schema\b",
        "consumer rebinding": r"\bupdate\s+.*consumer\b",
        "edge deployment": r"\bdeploy[_ -]?function\b",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, lower, re.IGNORECASE | re.DOTALL):
            fail(f"migration crosses prohibited boundary: {label}")

    if "PASS_THRIVEBASE_LEGACY_COMPATIBILITY_WRAPPER_READBACK" not in readback:
        fail("readback PASS identity missing")
    for required in (
        "'canonical_wrapper_count',8",
        "'legacy_alias_count',8",
        "'safe_behavior_parity_canaries',2",
        "'trigger_rebinding',false",
        "'queue_rebinding',false",
        "'consumer_rebinding',false",
        "'edge_rebinding',false",
        "'legacy_alias_retired',false",
        "'destructive_rename',false",
    ):
        if required not in readback:
            fail(f"readback invariant missing: {required}")

    if manifest.get("manifest_id") != "ct.manifest.thrivebase-legacy-compatibility-wrappers.v1":
        fail("manifest identity drifted")
    if manifest.get("state") not in {
        "CONTROLLED_TEST_SOURCE_READY_RUNTIME_PENDING",
        "CONTROLLED_TEST_RUNTIME_ACTIVE_LEGACY_REBINDING_DEFERRED",
    }:
        fail("manifest state is not governed")
    if manifest.get("phase") != "2.99":
        fail("institutional phase must remain 2.99")

    canonical = manifest.get("canonical", {})
    if canonical.get("human_label") != "ThriveBase":
        fail("canonical human label must be ThriveBase")
    if canonical.get("machine_token") != "thrivebase":
        fail("canonical machine token must be thrivebase")
    if canonical.get("wrapper_count") != 8:
        fail("manifest wrapper count must be eight")
    if canonical.get("service_role_wrapper_count") != 7:
        fail("manifest service-role wrapper count must be seven")
    if canonical.get("safe_readback_canary_count") != 2:
        fail("manifest safe canary count must be two")

    model = manifest.get("compatibility_model", {})
    for key in (
        "canonical_public_wrappers",
        "legacy_aliases_retained",
        "security_invoker_wrappers",
        "service_role_parity",
    ):
        if model.get(key) is not True:
            fail(f"compatibility model must preserve {key}")
    for key in ("public_execute", "anon_execute", "authenticated_execute", "complete_v1_new_execute_grant"):
        if model.get(key) is not False:
            fail(f"compatibility model must keep {key}=false")

    cutover = manifest.get("runtime_cutover", {})
    for key in (
        "trigger_rebinding",
        "queue_rebinding",
        "consumer_rebinding",
        "vault_secret_renamed",
        "edge_rebinding",
        "legacy_alias_retired",
        "destructive_rename",
    ):
        if cutover.get(key) is not False:
            fail(f"runtime cutover boundary drifted: {key}")

    if any(value is not False for value in manifest.get("hard_boundaries", {}).values()):
        fail("hard boundary became active")

    if "python scripts/validate_thrivebase_compatibility_wrappers.py" not in workflow:
        fail("workflow does not execute the compatibility validator")
    if "actions/checkout@" not in workflow or "actions/setup-python@" not in workflow:
        fail("workflow supply-chain pins are incomplete")

    print(json.dumps({
        "result": "PASS_THRIVEBASE_LEGACY_COMPATIBILITY_WRAPPER_SOURCE_CONTRACT",
        "canonical_wrappers": 8,
        "service_role_wrappers": 7,
        "safe_readback_canaries": 2,
        "security_invoker": True,
        "legacy_aliases_retained": True,
        "trigger_rebinding": False,
        "queue_rebinding": False,
        "consumer_rebinding": False,
        "edge_rebinding": False,
        "destructive_rename": False,
        "phase_advancement": False,
        "merge_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
