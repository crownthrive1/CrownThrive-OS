#!/usr/bin/env python3
"""Fail-closed source verifier for the CHLOM Git/Supabase replay custody repair."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
RECEIPT = ROOT / "supabase" / "migration_lineage" / "chlom_replay_custody_20260903.json"
BASELINE = MIGRATIONS / "20260821231328_remote_applied_lineage.sql"
ASSERTION = MIGRATIONS / "20260823203546_execution_builder_capability_contract_identity_v1.sql"
LEGACY_ASSERTION = MIGRATIONS / "20260823202950_execution_builder_capability_contract_identity_v1.sql"
CANONICAL_RE = re.compile(r"^(\d{14})_.+\.sql$")

EXPECTED_SHA256 = {
    BASELINE: "d380b37f211cccab9af5f98381e34d125372c7783f8d90afec1d1d7bea04e85b",
    ASSERTION: "3cf1a5887757740a14aeb75e17bea093b47886fa8f89d20982b5b5456817acb8",
}

REQUIRED_BASELINE_TOKENS = (
    "create schema if not exists chlom_secrets",
    "create schema if not exists chlom_runtime",
    "create table if not exists chlom_secrets.trade_secret_assets",
    "create table if not exists chlom_runtime.vaulted_capability_registry",
    "create or replace view chlom_runtime.capability_contracts",
    "primary key",
    "force row level security",
    "revoke all",
    "service_role",
)

REQUIRED_ASSERTION_TOKENS = (
    "HOLD_EXECUTION_BUILDER_CAPABILITY_DEPENDENCY_MISSING",
    "HOLD_CAPABILITY_VIEW_STORAGE_DRIFT",
    "HOLD_CAPABILITY_BASE_PRIMARY_KEY_MISSING",
    "pg_get_viewdef",
    "pg_get_constraintdef",
)

PROHIBITED_LITERAL_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]+\b"),
    re.compile(r"\bsbp_[A-Za-z0-9]+\b"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,}\b"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(errors: list[str]) -> None:
    print(json.dumps({"status": "HOLD", "errors": errors}, indent=2, sort_keys=True))
    raise SystemExit(1)


def main() -> None:
    errors: list[str] = []
    active_by_version: dict[str, Path] = {}

    for path in sorted(MIGRATIONS.glob("*.sql")):
        match = CANONICAL_RE.match(path.name)
        if not match:
            errors.append(f"noncanonical migration filename: {path.name}")
            continue
        version = match.group(1)
        if version in active_by_version:
            errors.append(
                f"duplicate migration version {version}: "
                f"{active_by_version[version].name}, {path.name}"
            )
        active_by_version[version] = path

    if LEGACY_ASSERTION.exists():
        errors.append(f"non-provider assertion timestamp remains active: {LEGACY_ASSERTION.name}")

    for path, expected in EXPECTED_SHA256.items():
        if not path.exists():
            errors.append(f"required custody file missing: {path.relative_to(ROOT)}")
            continue
        actual = sha256(path)
        if actual != expected:
            errors.append(
                f"custody digest mismatch for {path.name}: expected={expected} actual={actual}"
            )

    if BASELINE.exists():
        text = BASELINE.read_text(encoding="utf-8")
        for token in REQUIRED_BASELINE_TOKENS:
            if token.lower() not in text.lower():
                errors.append(f"baseline token missing: {token}")
        for pattern in PROHIBITED_LITERAL_PATTERNS:
            if pattern.search(text):
                errors.append(f"prohibited literal in baseline: {pattern.pattern}")

    if ASSERTION.exists():
        text = ASSERTION.read_text(encoding="utf-8")
        for token in REQUIRED_ASSERTION_TOKENS:
            if token not in text:
                errors.append(f"assertion token missing: {token}")
        for pattern in PROHIBITED_LITERAL_PATTERNS:
            if pattern.search(text):
                errors.append(f"prohibited literal in assertion: {pattern.pattern}")

    if not RECEIPT.exists():
        errors.append(f"custody receipt missing: {RECEIPT.relative_to(ROOT)}")
    else:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        if receipt.get("production_history_mutated") is not False:
            errors.append("receipt must declare production_history_mutated=false")
        if receipt.get("secret_bodies_published") is not False:
            errors.append("receipt must declare secret_bodies_published=false")
        if receipt.get("dependent_penta_advance") not in {
            "HOLD_PENDING_FRESH_PREVIEW_PASS",
            "AUTHORIZED_AFTER_FRESH_PREVIEW_PASS",
        }:
            errors.append("receipt has invalid dependent_penta_advance state")

    if errors:
        fail(errors)

    result = {
        "status": "PASS",
        "active_migration_count": len(active_by_version),
        "baseline_version": "20260821231328",
        "assertion_version": "20260823203546",
        "legacy_assertion_active": False,
        "production_history_mutated": False,
        "secret_bodies_published": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        fail([f"verifier exception: {exc}"])
