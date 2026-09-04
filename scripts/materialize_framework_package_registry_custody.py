#!/usr/bin/env python3
"""Materialize exact provider migration 20260820221308 from verified Git chunks."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PART_ROOT = ROOT / "supabase/migration_lineage/provider_custody/20260820221308"
MIGRATIONS = ROOT / "supabase/migrations"
TARGET = MIGRATIONS / "20260820221308_framework_package_registry_v1.sql"
MARKER = MIGRATIONS / "20260820221308_remote_applied_lineage.sql"
RECEIPT = ROOT / "supabase/migration_lineage/replay_diagnostics/20260904_framework_package_registry_custody.json"

PARTS = [
    ("0000.sqlpart", 2048, "8ff020dc51687ff212c0e47c9896e9fc8870c87b"),
    ("0001.sqlpart", 2048, "bef2ef68e4ac488ffd1a12d37efaf4b365bf0391"),
    ("0002.sqlpart", 2048, "b54493a0fc619f5d59c25933e66c52fe508b13ab"),
    ("0003.sqlpart", 2048, "8b3e828c1b4dfe913dbe178d44b9afb2d3343a44"),
    ("0004.sqlpart", 2048, "bf12c29f7a3108425a3fdf879afae4bcfbc39025"),
    ("0005.sqlpart", 983, "d5a97eab60f799e55f4aed9ce40103eb7cf79818"),
]
EXPECTED_BYTES = 11223
EXPECTED_SHA256 = "01f4fcabb5a894cada0c4da43261582c7135c56754acd082ed20a1339444c5ff"
EXPECTED_GIT_BLOB = "f545b617c77d8bdedcd379cf739e6373c8ca2ccd"

PROHIBITED = (
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"\bsk_(?:live|test)_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bsbp_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bgh[opusr]_[A-Za-z0-9_-]{20,}\b"),
)


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def hold(reason: str) -> None:
    print(f"HOLD_FRAMEWORK_PACKAGE_CUSTODY: {reason}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    chunks: list[bytes] = []
    evidence: list[dict[str, object]] = []
    for name, expected_bytes, expected_git_sha in PARTS:
        path = PART_ROOT / name
        if not path.exists():
            hold(f"missing chunk {name}")
        raw = path.read_bytes()
        actual_git_sha = git_blob_sha(raw)
        if len(raw) != expected_bytes:
            hold(f"chunk {name} bytes expected={expected_bytes} actual={len(raw)}")
        if actual_git_sha != expected_git_sha:
            hold(f"chunk {name} Git SHA expected={expected_git_sha} actual={actual_git_sha}")
        chunks.append(raw)
        evidence.append({"path": str(path.relative_to(ROOT)), "bytes": len(raw), "git_blob_sha": actual_git_sha})

    body = b"".join(chunks)
    actual_sha256 = hashlib.sha256(body).hexdigest()
    actual_git_blob = git_blob_sha(body)
    if len(body) != EXPECTED_BYTES:
        hold(f"full bytes expected={EXPECTED_BYTES} actual={len(body)}")
    if actual_sha256 != EXPECTED_SHA256:
        hold(f"full SHA-256 expected={EXPECTED_SHA256} actual={actual_sha256}")
    if actual_git_blob != EXPECTED_GIT_BLOB:
        hold(f"full Git SHA expected={EXPECTED_GIT_BLOB} actual={actual_git_blob}")
    for pattern in PROHIBITED:
        if pattern.search(body):
            hold(f"credential-like literal matched {pattern.pattern!r}")

    TARGET.write_bytes(body)
    if MARKER.exists():
        MARKER.unlink()

    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    receipt.update({
        "source_state": "EXACT_PROVIDER_BODY_MATERIALIZED_REPLAY_PENDING",
        "canonical_path": str(TARGET.relative_to(ROOT)),
        "marker_retired": str(MARKER.relative_to(ROOT)),
        "provider_version": "20260820221308",
        "provider_name": "framework_package_registry_v1",
        "bytes": len(body),
        "sha256": actual_sha256,
        "git_blob_sha": actual_git_blob,
        "chunk_evidence": evidence,
        "materialized_at_utc": datetime.now(timezone.utc).isoformat(),
        "production_mutated": False,
        "dependent_penta_wave": "HOLD",
    })
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "version": "20260820221308", "bytes": len(body), "sha256": actual_sha256, "production_mutated": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
