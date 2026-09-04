#!/usr/bin/env python3
"""Restore exact provider-applied CHLOM agent-runtime migrations into Git custody.

The script reads only Supabase's migration ledger through the management API, verifies
provider name, exact UTF-8 byte length, SHA-256, and a bounded secret-pattern denylist,
then writes the canonical source files. It never mutates the provider database.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
RECEIPT = ROOT / "supabase" / "migration_lineage" / "chlom_agent_runtime_custody_v6.json"
PROJECT_REF = "tzajnzshmtzjenqulehq"

EXPECTED: dict[str, dict[str, Any]] = {
    "20260821022535": {
        "name": "chlom_fluid_module_agent_oracle_registry_v1",
        "file": "20260821022535_chlom_fluid_module_agent_oracle_registry_v1.sql",
        "bytes": 24867,
        "sha256": "081d1898846830b7eb954a6c25f5b9c673a4f105b6cb1599ffd192bfafc04eb8",
        "write": True,
    },
    "20260821030452": {
        "name": "chlom_construction_work_queue_v1",
        "file": "20260821030452_chlom_construction_work_queue_v1.sql",
        "bytes": 16864,
        "sha256": "e7c6567c6b459996ba0d96c4807d63b9ca70093dc4f813bd11ae16e1983c9b41",
        "write": True,
    },
    "20260821050436": {
        "name": "agent_capability_master_suite_v1",
        "file": "20260821050436_agent_capability_master_suite_v1.sql",
        "bytes": 44773,
        "sha256": "61d7303de12b8748a8277bfbe11e5f49f6affbd398be40fde7e0e81db18ad54e",
        "write": True,
    },
    "20260822193302": {
        "name": "institutional_capability_runtime_v1",
        "file": "20260822193302_institutional_capability_runtime_v1.sql",
        "bytes": 25676,
        "sha256": "8cae8a4e8d067bcdaa6104746b25272e38aaa8e8f0430f8aba3f5407e72b835f",
        "write": True,
    },
    "20260823203546": {
        "name": "execution_builder_capability_contract_identity_v1",
        "file": "20260823203546_execution_builder_capability_contract_identity_v1.sql",
        "bytes": 1262,
        "sha256": "3cf1a5887757740a14aeb75e17bea093b47886fa8f89d20982b5b5456817acb8",
        "write": False,
    },
    "20260823203649": {
        "name": "execution_builder_agent_v1_0_1",
        "file": "20260823203649_execution_builder_agent_v1_0_1.sql",
        "bytes": 21980,
        "sha256": "722b86270ca57b837ffb62e91a71d673cd76d7f72cb90891cb439f2d0b8cbc5a",
        "write": False,
    },
}

RETIRE = (
    "20260821022535_remote_applied_lineage.sql",
    "20260821030452_remote_applied_lineage.sql",
    "20260821050436_remote_applied_lineage.sql",
    "20260822193302_remote_applied_lineage.sql",
    "20260823202950_execution_builder_capability_contract_identity_v1.sql",
    "20260823203100_execution_builder_agent_v1_0_1.sql",
    "20260823203546_remote_applied_lineage.sql",
    "20260823203649_remote_applied_lineage.sql",
)

PROHIBITED = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bsbp_[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"(?i)(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*'[^']{8,}'"
    ),
)


def hold(reason: str) -> None:
    print(f"HOLD_CHLOM_PROVIDER_CUSTODY: {reason}", file=sys.stderr)
    raise SystemExit(1)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("result") or payload.get("data") or payload.get("rows")
    else:
        rows = None
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        hold("unexpected Supabase database/query response shape")
    return rows


def fetch_provider_rows(token: str) -> list[dict[str, Any]]:
    versions = ",".join(f"'{version}'" for version in EXPECTED)
    query = (
        "select version,name,array_to_string(statements,E'\\n') as sql_text "
        "from supabase_migrations.schema_migrations "
        f"where version in ({versions}) order by version"
    )
    request = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=json.dumps({"query": query}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "CrownThrive-CHLOM-Custody/6.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return extract_rows(json.load(response))
    except urllib.error.HTTPError as exc:
        body = exc.read(500).decode("utf-8", errors="replace")
        hold(f"Supabase management API HTTP {exc.code}: {body}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        hold(f"Supabase management API unavailable: {exc}")
    return []


def verify_raw(version: str, name: str, raw: bytes) -> None:
    contract = EXPECTED[version]
    if name != contract["name"]:
        hold(
            f"provider name mismatch for {version}: expected={contract['name']} actual={name}"
        )
    if len(raw) != contract["bytes"]:
        hold(
            f"byte mismatch for {version}: expected={contract['bytes']} actual={len(raw)}"
        )
    actual = sha256(raw)
    if actual != contract["sha256"]:
        hold(
            f"SHA-256 mismatch for {version}: expected={contract['sha256']} actual={actual}"
        )
    text = raw.decode("utf-8")
    for pattern in PROHIBITED:
        if pattern.search(text):
            hold(f"prohibited credential-like literal in provider body {version}")


def main() -> None:
    token = (
        os.environ.get("SUPABASE_ACCESS_TOKEN")
        or os.environ.get("SUPABASE_MANAGEMENT_TOKEN")
        or os.environ.get("SUPABASE_TOKEN")
    )
    if not token:
        hold("Supabase management credential is not available to the workflow")

    rows = fetch_provider_rows(token)
    by_version = {str(row.get("version")): row for row in rows}
    if set(by_version) != set(EXPECTED):
        hold(
            "provider identity set mismatch: "
            f"expected={sorted(EXPECTED)} actual={sorted(by_version)}"
        )

    evidence: list[dict[str, Any]] = []
    for version, contract in EXPECTED.items():
        row = by_version[version]
        sql_text = row.get("sql_text")
        if not isinstance(sql_text, str):
            hold(f"provider SQL body missing for {version}")
        raw = sql_text.encode("utf-8")
        verify_raw(version, str(row.get("name")), raw)
        path = MIGRATIONS / contract["file"]
        if contract["write"]:
            path.write_bytes(raw)
        elif not path.exists():
            hold(f"pre-staged canonical file missing: {path.name}")
        else:
            local = path.read_bytes()
            verify_raw(version, contract["name"], local)
            if local != raw:
                hold(f"local/provider byte divergence for {version}")
        evidence.append(
            {
                "version": version,
                "provider_name": contract["name"],
                "path": str(path.relative_to(ROOT)),
                "bytes": len(raw),
                "sha256": sha256(raw),
            }
        )

    for filename in RETIRE:
        path = MIGRATIONS / filename
        if path.exists():
            path.unlink()

    for version, contract in EXPECTED.items():
        matches = sorted(path.name for path in MIGRATIONS.glob(f"{version}_*.sql"))
        if matches != [contract["file"]]:
            hold(
                f"non-unique canonical provider version {version}: expected={contract['file']} "
                f"actual={matches}"
            )
    if list(MIGRATIONS.glob("20260823203100_*.sql")):
        hold("non-provider Execution Builder version 20260823203100 remains active")

    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    receipt.update(
        {
            "source_state": "EXACT_PROVIDER_BODIES_MATERIALIZED_PREVIEW_PENDING",
            "provider_project_ref": PROJECT_REF,
            "materialized_from_head_sha": os.environ.get("GITHUB_SHA"),
            "materialization_workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "materialized_at_utc": datetime.now(timezone.utc).isoformat(),
            "custody_points": evidence,
            "production_history_mutated": False,
            "production_schema_mutated": False,
            "production_data_copied": False,
            "dependent_penta_advance": "HOLD_PENDING_SECOND_FRESH_PREVIEW_PASS",
        }
    )
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "provider_versions": sorted(EXPECTED),
                "production_mutated": False,
                "dependent_penta_advance": receipt["dependent_penta_advance"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
