#!/usr/bin/env python3
"""Materialize exact provider migration 20260820173930 from verified Git chunks.

Every segment is verified by byte length, SHA-256, and Git object ID before the
complete provider body is assembled. The complete body is then independently
verified, the matching no-op marker is retired, and a fail-closed receipt is
updated. This process never connects to or mutates Supabase.
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
PART_ROOT = ROOT / "supabase" / "migration_lineage" / "provider_custody" / "20260820173930"
TARGET = MIGRATIONS / "20260820173930_add_website_surface_contact_asset_control.sql"
MARKER = MIGRATIONS / "20260820173930_remote_applied_lineage.sql"
RECEIPT = ROOT / "supabase" / "migration_lineage" / "replay_diagnostics" / "20260904_website_surface_contact_asset_control_custody_v12.json"

PARTS = [
    ("0000.sqlpart", 2048, "811dc7e6bf4cc240988774084f30f0860785aecd5b61284fe3ab90837c8eddec", "d2f424b65d431a280d9a702d2144fe42d1c01336"),
    ("0001.sqlpart", 2048, "57d3f3bb6ea34f5bba60ca63c4cef8ca600f2c00fc418b09f1bf0b53c0107128", "270cf4538f289f9cfa46db28b5be0a47d6e8e4a1"),
    ("0002.sqlpart", 2048, "e30c9bc8e87f17fa0d7bde33795d4d8c52410b106caacb9af4b1489f2bbf2d2e", "029cc0037e3c73c963b21ac1255a1b0ad630049b"),
    ("0003.sqlpart", 2048, "0d6b306ecd20f0b4fe926423a006213562e0c198fea9272dd02d081038febf6d", "0c7435f8df2b14ec96c6d45c4e2b39b73e296771"),
    ("0004.sqlpart", 2048, "54a247daebf91a326752346db06f6b84fec6a9d7d20429279dcb7f0e2b233461", "2f08edef89791e8c9c46151071cf2446f74274d5"),
    ("0005.sqlpart", 2048, "7a93de7ee4640d250a0c41f0e0d058c04027cb53f6b2ba92bc3fea6b8a8bf44d", "5aa8e368a8fc124ec9351eb16b53d4dbd2511e5a"),
    ("0006.sqlpart", 2048, "949d1930f746bcb8139f2bbed3354417bca202a4e8c404bd2b506627a31f049e", "95fb16b86b79812b24c4a87dae2a871af0c10d34"),
    ("0007.sqlpart", 2048, "954fbeafaf4d5ad4b57d75cd50a4158f61441e3687b83b0cd47fa0dc2f61b51a", "2d8c538dac02d6af5b8adc4046943013088f9b6c"),
    ("0008.sqlpart", 2048, "5aabdbe6edd3938ddb782135f4b99247b5c1f3dbd962bb1d6810570a9bea7b9b", "5d7f69c8e2ec8ae76f223bf78cb3132dfd9e73c5"),
    ("0009.sqlpart", 2048, "15b449e33c6bdaf7a2423007d6a11845d8d1ce77af37486334c70c03c1d306dc", "d38d864cd76343e01fb3a9ef53a3a10dfbd74348"),
    ("0010.sqlpart", 2048, "ee7ebd011e7fee7765cd414dc2c0bd9e67b6e41a72988fe1ab5c282565493360", "4b3f6257033de916a8ead2557142c3254494d3e5"),
    ("0011.sqlpart", 2048, "32fe8bbf4de7f2721c16133d261e334b76c30c2768afc5a485a41893bc78f365", "e60950a0fdd1bdf225a4796e579543059c5b4e09"),
    ("0012.sqlpart", 1738, "3817da264f1d4b4f280eb2590031001731eb4012ec799885d86f85e19a834433", "f51664460e8919a3455223ac0e0a6e21fd509776"),
]

EXPECTED_BYTES = 26314
EXPECTED_SHA256 = "686f55cb167de9b0e2a78f913c542bc033843a9dc5272f107a23a95727771086"
EXPECTED_GIT_BLOB = "9caa8428f4f295aee689f3eb69974635be97b6dc"

PROHIBITED = (
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"\bsk_(?:live|test)_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bsbp_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bgh[opusr]_[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"(?i)(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*'[^']{8,}'"),
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def hold(reason: str) -> None:
    print(f"HOLD_WEBSITE_SURFACE_CUSTODY: {reason}", file=sys.stderr)
    raise SystemExit(1)


def verify(label: str, raw: bytes, expected_bytes: int, expected_sha256: str, expected_git_blob: str) -> None:
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
            hold(f"{label} contains a prohibited credential-like literal")


def main() -> None:
    chunks: list[bytes] = []
    chunk_evidence: list[dict[str, object]] = []
    for filename, size, expected_sha, expected_git in PARTS:
        path = PART_ROOT / filename
        if not path.is_file():
            hold(f"missing segment {path.relative_to(ROOT)}")
        raw = path.read_bytes()
        verify(filename, raw, size, expected_sha, expected_git)
        chunks.append(raw)
        chunk_evidence.append({
            "path": str(path.relative_to(ROOT)),
            "bytes": len(raw),
            "sha256": sha256(raw),
            "git_blob_sha": git_blob_sha(raw),
        })

    body = b"".join(chunks)
    verify("20260820173930", body, EXPECTED_BYTES, EXPECTED_SHA256, EXPECTED_GIT_BLOB)

    TARGET.write_bytes(body)
    if MARKER.exists():
        MARKER.unlink()

    matches = sorted(path.name for path in MIGRATIONS.glob("20260820173930_*.sql"))
    if matches != [TARGET.name]:
        hold(f"provider version is not unique after materialization: {matches}")

    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    receipt.update({
        "source_state": "EXACT_PROVIDER_BODY_MATERIALIZED_REPLAY_PENDING",
        "canonical_path": str(TARGET.relative_to(ROOT)),
        "retired_marker_path": str(MARKER.relative_to(ROOT)),
        "provider_version": "20260820173930",
        "provider_name": "add_website_surface_contact_asset_control",
        "bytes": len(body),
        "sha256": sha256(body),
        "git_blob_sha": git_blob_sha(body),
        "chunk_evidence": chunk_evidence,
        "materialized_at_utc": datetime.now(timezone.utc).isoformat(),
        "production_history_mutated": False,
        "production_schema_mutated": False,
        "production_data_copied": False,
        "production_mutated": False,
        "dependent_penta_wave": "HOLD_PENDING_TERMINAL_MIGRATIONS_PASSED",
    })
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "PASS",
        "provider_version": "20260820173930",
        "bytes": len(body),
        "sha256": sha256(body),
        "git_blob_sha": git_blob_sha(body),
        "production_mutated": False,
        "dependent_penta_wave": receipt["dependent_penta_wave"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        hold(f"materialization exception: {exc}")
