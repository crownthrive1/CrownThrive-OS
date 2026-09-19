#!/usr/bin/env python3
"""Fail-closed source verifier for CHLOM provider agent-runtime replay custody v6."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
RECEIPT = ROOT / "supabase" / "migration_lineage" / "chlom_agent_runtime_custody_v6.json"

EXPECTED = {
    "20260821022535_chlom_fluid_module_agent_oracle_registry_v1.sql": (
        24867,
        "081d1898846830b7eb954a6c25f5b9c673a4f105b6cb1599ffd192bfafc04eb8",
    ),
    "20260821030452_chlom_construction_work_queue_v1.sql": (
        16864,
        "e7c6567c6b459996ba0d96c4807d63b9ca70093dc4f813bd11ae16e1983c9b41",
    ),
    "20260821050436_agent_capability_master_suite_v1.sql": (
        44773,
        "61d7303de12b8748a8277bfbe11e5f49f6affbd398be40fde7e0e81db18ad54e",
    ),
    "20260821231328_remote_applied_lineage.sql": (
        None,
        "d380b37f211cccab9af5f98381e34d125372c7783f8d90afec1d1d7bea04e85b",
    ),
    "20260822193302_institutional_capability_runtime_v1.sql": (
        25676,
        "8cae8a4e8d067bcdaa6104746b25272e38aaa8e8f0430f8aba3f5407e72b835f",
    ),
    "20260823203546_execution_builder_capability_contract_identity_v1.sql": (
        1262,
        "3cf1a5887757740a14aeb75e17bea093b47886fa8f89d20982b5b5456817acb8",
    ),
    "20260823203649_execution_builder_agent_v1_0_1.sql": (
        21980,
        "722b86270ca57b837ffb62e91a71d673cd76d7f72cb90891cb439f2d0b8cbc5a",
    ),
}

TARGET_VERSION_TO_FILE = {
    "20260821022535": "20260821022535_chlom_fluid_module_agent_oracle_registry_v1.sql",
    "20260821030452": "20260821030452_chlom_construction_work_queue_v1.sql",
    "20260821050436": "20260821050436_agent_capability_master_suite_v1.sql",
    "20260821231328": "20260821231328_remote_applied_lineage.sql",
    "20260822193302": "20260822193302_institutional_capability_runtime_v1.sql",
    "20260823203546": "20260823203546_execution_builder_capability_contract_identity_v1.sql",
    "20260823203649": "20260823203649_execution_builder_agent_v1_0_1.sql",
}

PROHIBITED_ACTIVE = {
    "20260821022535_remote_applied_lineage.sql",
    "20260821030452_remote_applied_lineage.sql",
    "20260821050436_remote_applied_lineage.sql",
    "20260822193302_remote_applied_lineage.sql",
    "20260823202950_execution_builder_capability_contract_identity_v1.sql",
    "20260823203100_execution_builder_agent_v1_0_1.sql",
    "20260823203546_remote_applied_lineage.sql",
    "20260823203649_remote_applied_lineage.sql",
}

PROHIBITED_LITERALS = (
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"\bsk_(?:live|test)_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bsbp_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bgh[opusr]_[A-Za-z0-9_-]{20,}\b"),
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fail(errors: list[str]) -> None:
    print(json.dumps({"status": "HOLD", "errors": errors}, indent=2, sort_keys=True))
    raise SystemExit(1)


def main() -> None:
    errors: list[str] = []
    evidence: list[dict[str, object]] = []

    for filename, (expected_bytes, expected_sha) in EXPECTED.items():
        path = MIGRATIONS / filename
        if not path.exists():
            errors.append(f"required migration missing: {filename}")
            continue
        raw = path.read_bytes()
        actual_sha = sha256(raw)
        if expected_bytes is not None and len(raw) != expected_bytes:
            errors.append(
                f"byte mismatch {filename}: expected={expected_bytes} actual={len(raw)}"
            )
        if actual_sha != expected_sha:
            errors.append(
                f"SHA-256 mismatch {filename}: expected={expected_sha} actual={actual_sha}"
            )
        for pattern in PROHIBITED_LITERALS:
            if pattern.search(raw):
                errors.append(f"credential-like literal detected in {filename}")
        evidence.append(
            {"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": actual_sha}
        )

    for filename in sorted(PROHIBITED_ACTIVE):
        if (MIGRATIONS / filename).exists():
            errors.append(f"superseded migration remains active: {filename}")

    for version, expected_file in TARGET_VERSION_TO_FILE.items():
        matches = sorted(path.name for path in MIGRATIONS.glob(f"{version}_*.sql"))
        if matches != [expected_file]:
            errors.append(
                f"version identity divergence {version}: expected={[expected_file]} actual={matches}"
            )

    if not RECEIPT.exists():
        errors.append(f"custody receipt missing: {RECEIPT.relative_to(ROOT)}")
        receipt: dict[str, object] = {}
    else:
        try:
            receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"custody receipt is invalid JSON: {exc}")
            receipt = {}
        if receipt.get("source_state") not in {
            "EXACT_PROVIDER_BODIES_MATERIALIZED_PREVIEW_PENDING",
            "SECOND_FRESH_PREVIEW_MIGRATIONS_PASSED_TOPOLOGY_PENDING",
            "SECOND_FRESH_PREVIEW_VALIDATED",
        }:
            errors.append(f"invalid source_state: {receipt.get('source_state')!r}")
        if receipt.get("production_history_mutated") is not False:
            errors.append("production_history_mutated must remain false")
        if receipt.get("production_schema_mutated") is not False:
            errors.append("production_schema_mutated must remain false")
        if receipt.get("production_data_copied") is not False:
            errors.append("production_data_copied must remain false")
        if receipt.get("dependent_penta_advance") not in {
            "HOLD_PENDING_SECOND_FRESH_PREVIEW_PASS",
            "AUTHORIZED_AFTER_SECOND_FRESH_PREVIEW_PASS",
            "ADVANCED_TO_DEPENDENT_VALIDATION",
        }:
            errors.append(
                f"invalid dependent_penta_advance: {receipt.get('dependent_penta_advance')!r}"
            )
        points = receipt.get("custody_points")
        if not isinstance(points, list) or len(points) != 6:
            errors.append("receipt must contain six exact provider custody points")

    if errors:
        fail(errors)

    print(
        json.dumps(
            {
                "status": "PASS",
                "scope": "CHLOM_PROVIDER_AGENT_RUNTIME_REPLAY_CUSTODY_V6",
                "source_state": receipt.get("source_state"),
                "dependent_penta_advance": receipt.get("dependent_penta_advance"),
                "production_mutated": False,
                "evidence": evidence,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except OSError as exc:
        fail([f"verifier filesystem error: {exc}"])
