#!/usr/bin/env python3
"""PentaRuntimeCustody™ local verifier for connected Supabase provider readback.

The checked-in receipt is provider evidence, never authority. It binds current
runtime objects and applied migration versions without reconstructing protected
historical SQL. Local migration lineage must independently match the same digest.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "developers/manifests/supabase-runtime-custody-readback-20260827.v1.json"
SNAPSHOT = ROOT / "supabase/migration_lineage/current_remote_snapshot_20260827_v3.json"
CANONICAL = re.compile(r"^(\d{14})_(.+)\.sql$")


def load() -> dict[str, Any]:
    data = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert data.get("schema") == "ct.penta.supabase-runtime-custody-readback/v1"
    assert data.get("project_ref") == "tzajnzshmtzjenqulehq"
    assert data.get("project_status") == "ACTIVE_HEALTHY"
    assert data.get("evidence_class") == "connected_provider_readback_not_blanket_release_authority"
    authority = data.get("authority", {})
    assert authority.get("provider_readback_is_blanket_release_authority") is False
    assert authority.get("historical_source_sql_reconstructed") is False
    assert authority.get("production_history_mutated") is False
    assert authority.get("d3_auto") is False
    return data


def local_versions() -> list[str]:
    versions: list[str] = []
    for path in sorted((ROOT / "supabase/migrations").glob("*.sql")):
        m = CANONICAL.fullmatch(path.name)
        assert m, f"noncanonical active migration filename: {path.name}"
        versions.append(m.group(1))
        if path.name.endswith("_remote_applied_lineage.sql"):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                assert not line.strip() or line.lstrip().startswith("--"), f"executable lineage marker: {path}:{line_no}"
    assert len(versions) == len(set(versions)), "duplicate active migration version"
    return versions


def digest(versions: list[str]) -> str:
    return hashlib.sha256(("\n".join(versions) + "\n").encode("utf-8")).hexdigest()


def assert_lineage(data: dict[str, Any]) -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    ledger = data["migration_ledger"]
    versions = local_versions()
    observed_digest = digest(versions)
    for source in (ledger, snapshot):
        assert int(source["migration_count"] if "migration_count" in source else source["count"]) == len(versions)
        assert source["versions_sha256"] == observed_digest
        assert source["last_version"] == versions[-1]
    assert ledger.get("production_history_mutated") is False


def assert_migration(data: dict[str, Any], name: str, version: str) -> None:
    assert data.get("migration_bindings", {}).get(name) == version, f"provider migration binding drift: {name}"
    assert version in set(local_versions()), f"applied migration version absent from local lineage: {version}"


def assert_function(data: dict[str, Any], qualified_name: str) -> None:
    item = data.get("runtime_functions", {}).get(qualified_name)
    assert isinstance(item, dict), f"runtime function missing from provider receipt: {qualified_name}"
    assert item.get("security_definer") is True
    assert item.get("service_role_execute") is True
    assert item.get("anon_execute") is False
    assert item.get("authenticated_execute") is False
    assert re.fullmatch(r"[0-9a-f]{32}", str(item.get("definition_md5", "")))


def assert_object(data: dict[str, Any], qualified_name: str) -> None:
    assert data.get("runtime_objects", {}).get(qualified_name) is True, f"runtime object missing: {qualified_name}"


def assert_cron(data: dict[str, Any], name: str, expected_prefix: str) -> None:
    value = str(data.get("cron_readback", {}).get(name, ""))
    assert value.startswith(expected_prefix) and value.endswith("| true"), f"cron readback drift: {name}"


if __name__ == "__main__":
    receipt = load()
    assert_lineage(receipt)
    print(json.dumps({"status": "PASS", "software": "PentaRuntimeCustody", "migration_count": len(local_versions())}, sort_keys=True))
