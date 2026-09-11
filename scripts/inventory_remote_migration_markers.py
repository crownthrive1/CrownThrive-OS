#!/usr/bin/env python3
"""Inventory active remote-applied lineage markers in the bounded CHLOM replay interval.

This is source-only discovery. It does not contact Supabase, mutate migrations, or infer
that every marker should be replaced. The resulting receipt drives an exact provider
lookup and digest-bound recovery wave.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
OUTPUT = ROOT / "supabase" / "migration_lineage" / "active_remote_marker_inventory_v8.json"
LOWER = "20260819000000"
UPPER = "20260823203649"
VERSION_RE = re.compile(r"^(\d{14})_(.+)\.sql$")
REMOTE_NAME_RE = re.compile(r"remote_applied_name\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
REMOTE_VERSION_RE = re.compile(r"remote_applied_version\s*:\s*(\d{14})", re.IGNORECASE)
SQL_LEAD_RE = re.compile(
    r"^\s*(?:--[^\n]*(?:\n|$)|/\*.*?\*/\s*)*(?P<lead>[a-zA-Z]+(?:\s+[a-zA-Z]+){0,3})?",
    re.DOTALL,
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def classify(text: str) -> tuple[str, str | None]:
    match = SQL_LEAD_RE.match(text)
    lead = (match.group("lead") if match else None) or None
    normalized = (lead or "").strip().lower()
    if not normalized:
        return "COMMENT_ONLY_MARKER", None
    if normalized in {"begin", "commit", "begin commit", "select null", "do"}:
        return "NO_OP_OR_ASSERTION_MARKER", normalized
    return "EXECUTABLE_OR_UNKNOWN_MARKER", normalized


def main() -> None:
    entries: list[dict[str, object]] = []
    by_version: dict[str, list[str]] = {}

    for path in sorted(MIGRATIONS.glob("*_remote_applied_lineage.sql")):
        match = VERSION_RE.match(path.name)
        if not match:
            continue
        version = match.group(1)
        if not (LOWER <= version <= UPPER):
            continue

        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
        marker_class, sql_lead = classify(text)
        declared_version_match = REMOTE_VERSION_RE.search(text)
        declared_name_match = REMOTE_NAME_RE.search(text)
        declared_version = declared_version_match.group(1) if declared_version_match else None
        declared_name = declared_name_match.group(1).strip() if declared_name_match else None
        comment_headers = [
            line.strip()[2:].strip()
            for line in text.splitlines()
            if line.strip().startswith("--")
        ][:12]

        entry = {
            "version": version,
            "path": str(path.relative_to(ROOT)),
            "bytes": len(raw),
            "sha256": sha256(raw),
            "declared_remote_version": declared_version,
            "declared_remote_name": declared_name,
            "marker_class": marker_class,
            "first_sql_lead": sql_lead,
            "comment_headers": comment_headers,
        }
        entries.append(entry)
        by_version.setdefault(version, []).append(path.name)

    duplicates = {
        version: paths
        for version, paths in sorted(by_version.items())
        if len(paths) > 1
    }
    declared_version_mismatches = [
        entry
        for entry in entries
        if entry["declared_remote_version"] not in {None, entry["version"]}
    ]

    receipt = {
        "schema": "crownthrive.supabase.remote-marker-inventory/v1",
        "receipt_id": "ct.supabase.remote-marker-inventory.20260904.v8",
        "repository": "crownthrive1/CrownThrive-OS",
        "bounded_interval": {"lower": LOWER, "upper": UPPER},
        "source_head_sha": os.environ.get("GITHUB_SHA"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "marker_count": len(entries),
        "distinct_version_count": len(by_version),
        "duplicate_versions": duplicates,
        "declared_version_mismatches": declared_version_mismatches,
        "entries": entries,
        "production_mutated": False,
        "provider_read_performed": False,
        "dependent_penta_advance": "HOLD_PENDING_BOUNDED_MARKER_RECOVERY_AND_FRESH_REPLAY",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "PASS",
                "marker_count": len(entries),
                "distinct_version_count": len(by_version),
                "duplicate_version_count": len(duplicates),
                "declared_version_mismatch_count": len(declared_version_mismatches),
                "output": str(OUTPUT.relative_to(ROOT)),
                "production_mutated": False,
                "dependent_penta_advance": receipt["dependent_penta_advance"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
