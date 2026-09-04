#!/usr/bin/env python3
"""Materialize the pre-consumer institutional replay supplement at 20260820003352.

The migration is composed deterministically from:
1. the already-reviewed institutional replay baseline SQL body; and
2. the exact provider-applied `preserve_future_credential_pending_state` body.

The provider component remains byte-for-byte intact. Production already records this
version as applied, so this operation changes Git custody and preview replay only.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
BASELINE = MIGRATIONS / "20260820192640_institutional_master_registry_20260820_v1.sql"
PROVIDER = (
    ROOT
    / "supabase"
    / "migration_lineage"
    / "provider_custody"
    / "20260820003352"
    / "provider.sqlpart"
)
TARGET = MIGRATIONS / "20260820003352_preserve_future_credential_pending_state.sql"
MARKER = MIGRATIONS / "20260820003352_remote_applied_lineage.sql"
RECEIPT = (
    ROOT
    / "supabase"
    / "migration_lineage"
    / "replay_diagnostics"
    / "20260904_preconsumer_institutional_replay_supplement_v10.json"
)

BASELINE_BYTES = 8637
BASELINE_SHA256 = "ddfcdc5d72e01316a49e94b982b3135f7b8de58810daabeb10815a86384d72b8"
BASELINE_GIT_BLOB = "7457b9e80944fee8db85b06903aff9fbbac75417"
PROVIDER_BYTES = 2803
PROVIDER_SHA256 = "d774bd53a6114267fc6bbc1270b773acdc8050ea041be0341be605fe5a4d0c3b"
PROVIDER_GIT_BLOB = "44457542bfcc2e8826f37b9b8da59c6c531f7d16"

HEADER = b"""-- CrownThrive pre-consumer institutional replay supplement v1.
-- Source version: 20260820003352 / preserve_future_credential_pending_state.
-- Production already records this provider version as applied; it will not be rerun there.
-- The institutional prefix reconstructs a manually provisioned production prerequisite
-- for data-less Git replay. The exact provider-applied body follows unchanged.
-- Production schema/history/data mutation: false.

"""

SEPARATOR = b"""

-- BEGIN EXACT PROVIDER-APPLIED BODY
-- version: 20260820003352
-- name: preserve_future_credential_pending_state
-- exact_body_sha256: d774bd53a6114267fc6bbc1270b773acdc8050ea041be0341be605fe5a4d0c3b
"""

PROHIBITED = (
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"\bsk_(?:live|test)_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bsbp_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bgh[opusr]_[A-Za-z0-9_-]{20,}\b"),
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()


def hold(reason: str) -> None:
    print(f"HOLD_PRECONSUMER_INSTITUTIONAL_REPLAY: {reason}", file=sys.stderr)
    raise SystemExit(1)


def verify_component(
    label: str,
    raw: bytes,
    expected_bytes: int,
    expected_sha256: str,
    expected_git_blob: str,
) -> None:
    if len(raw) != expected_bytes:
        hold(f"{label} bytes expected={expected_bytes} actual={len(raw)}")
    actual_sha = sha256(raw)
    if actual_sha != expected_sha256:
        hold(f"{label} SHA-256 expected={expected_sha256} actual={actual_sha}")
    actual_git = git_blob_sha(raw)
    if actual_git != expected_git_blob:
        hold(f"{label} Git blob expected={expected_git_blob} actual={actual_git}")
    for pattern in PROHIBITED:
        if pattern.search(raw):
            hold(f"{label} contains credential-like literal")


def main() -> None:
    baseline = BASELINE.read_bytes()
    provider = PROVIDER.read_bytes()
    verify_component(
        "institutional replay baseline",
        baseline,
        BASELINE_BYTES,
        BASELINE_SHA256,
        BASELINE_GIT_BLOB,
    )
    verify_component(
        "exact provider body",
        provider,
        PROVIDER_BYTES,
        PROVIDER_SHA256,
        PROVIDER_GIT_BLOB,
    )

    start = baseline.find(b"begin;")
    if start < 0:
        hold("institutional replay baseline transaction body not found")
    baseline_sql = baseline[start:]
    if not baseline_sql.rstrip().endswith(b"commit;"):
        hold("institutional replay baseline does not terminate with commit")

    combined = HEADER + baseline_sql + SEPARATOR + provider
    if not combined.endswith(provider):
        hold("provider body is not an exact suffix of generated migration")
    if combined[-len(provider) :] != provider:
        hold("provider suffix diverged during assembly")

    TARGET.write_bytes(combined)
    if MARKER.exists():
        MARKER.unlink()

    matches = sorted(path.name for path in MIGRATIONS.glob("20260820003352_*.sql"))
    if matches != [TARGET.name]:
        hold(f"version 20260820003352 is not unique after assembly: {matches}")

    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    receipt.update(
        {
            "source_state": "PRECONSUMER_SUPPLEMENT_MATERIALIZED_REPLAY_PENDING",
            "canonical_path": str(TARGET.relative_to(ROOT)),
            "retired_marker": str(MARKER.relative_to(ROOT)),
            "institutional_prefix": {
                "source_path": str(BASELINE.relative_to(ROOT)),
                "source_bytes": len(baseline),
                "source_sha256": sha256(baseline),
                "source_git_blob_sha": git_blob_sha(baseline),
                "extracted_sql_bytes": len(baseline_sql),
                "classification": "SANITIZED_REPLAY_COMPATIBILITY_SUPPLEMENT",
            },
            "provider_body": {
                "version": "20260820003352",
                "name": "preserve_future_credential_pending_state",
                "source_path": str(PROVIDER.relative_to(ROOT)),
                "bytes": len(provider),
                "sha256": sha256(provider),
                "git_blob_sha": git_blob_sha(provider),
                "preserved_as_exact_suffix": True,
            },
            "combined_source": {
                "bytes": len(combined),
                "sha256": sha256(combined),
                "git_blob_sha": git_blob_sha(combined),
            },
            "materialized_at_utc": datetime.now(timezone.utc).isoformat(),
            "production_history_mutated": False,
            "production_schema_mutated": False,
            "production_data_copied": False,
            "dependent_penta_wave": "HOLD_PENDING_TERMINAL_MIGRATIONS_PASSED",
        }
    )
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "status": "PASS",
                "version": "20260820003352",
                "combined_bytes": len(combined),
                "combined_sha256": sha256(combined),
                "provider_body_exact": True,
                "production_mutated": False,
                "dependent_penta_wave": receipt["dependent_penta_wave"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        hold(f"materialization exception: {exc}")
