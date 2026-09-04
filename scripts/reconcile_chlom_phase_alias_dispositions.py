#!/usr/bin/env python3
"""Reconcile exact retired phase-alias dispositions introduced by CHLOM custody.

This utility is intentionally narrow and fail-closed. It adds only the two reviewed
paths identified by the Phase 3 convergence validator, preserves every existing
registry record, sorts each lane deterministically, and rejects conflicting counts
or duplicate cross-lane ownership.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers" / "manifests" / "penta-phase-alias-dispositions.v1.json"

REQUIRED: dict[str, dict[str, int]] = {
    "historical_alias_evidence": {
        "supabase/migrations/20260819164517_credential_continuity_registry_v1.sql": 1,
    },
    "current_record_contextual_reference": {
        "supabase/migrations/20260820192640_institutional_master_registry_20260820_v1.sql": 1,
    },
}


def hold(message: str) -> None:
    print(f"HOLD_CHLOM_ALIAS_DISPOSITION_RECONCILIATION: {message}", file=sys.stderr)
    raise SystemExit(1)


def normalize_record(path: str, retired_alias_hits: int) -> dict[str, Any]:
    return {
        "path": path,
        "retired_alias_hits": retired_alias_hits,
        "stale_current_claim_hits": 0,
    }


def main() -> None:
    try:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        hold(f"cannot read manifest: {exc}")

    dispositions = payload.get("dispositions")
    if not isinstance(dispositions, dict):
        hold("manifest dispositions is not an object")

    all_owners: dict[str, str] = {}
    for lane, records in dispositions.items():
        if not isinstance(records, list):
            hold(f"lane {lane!r} is not a list")
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                hold(f"lane {lane!r} contains an invalid record")
            path = record["path"]
            prior = all_owners.get(path)
            if prior is not None:
                hold(f"path {path!r} already appears in both {prior!r} and {lane!r}")
            all_owners[path] = lane

    changed = False
    for lane, requirements in REQUIRED.items():
        records = dispositions.get(lane)
        if not isinstance(records, list):
            hold(f"required lane {lane!r} is absent")
        by_path = {record["path"]: record for record in records}
        for path, expected_hits in requirements.items():
            existing_lane = all_owners.get(path)
            if existing_lane is not None and existing_lane != lane:
                hold(
                    f"path {path!r} is governed by {existing_lane!r}; expected {lane!r}"
                )
            record = by_path.get(path)
            if record is None:
                record = normalize_record(path, expected_hits)
                records.append(record)
                by_path[path] = record
                all_owners[path] = lane
                changed = True
                continue
            actual = (
                record.get("retired_alias_hits"),
                record.get("stale_current_claim_hits"),
            )
            expected = (expected_hits, 0)
            if actual != expected:
                hold(f"count conflict for {path!r}: expected={expected} actual={actual}")
        records.sort(key=lambda item: item["path"])

    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if changed:
        MANIFEST.write_text(rendered, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "PASS",
                "manifest": str(MANIFEST.relative_to(ROOT)),
                "changed": changed,
                "required_dispositions": REQUIRED,
                "production_mutated": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
