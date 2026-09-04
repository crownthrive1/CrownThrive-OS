#!/usr/bin/env python3
"""Materialize exact CHLOM gate and specialist-agent migration custody.

This script assembles only provider-ledger bytes that were split into Git objects,
verifies every chunk and complete object, retires the corresponding no-op lineage
markers, and records a fail-closed receipt. It never connects to or mutates Supabase.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
CUSTODY = ROOT / "supabase" / "migration_lineage" / "provider_custody"
RECEIPT = (
    ROOT
    / "supabase"
    / "migration_lineage"
    / "replay_diagnostics"
    / "20260904_chlom_gate_agent_custody_v9.json"
)

DIRECT = {
    "version": "20260821025311",
    "name": "chlom_construction_gates_control_plane_v1",
    "path": MIGRATIONS / "20260821025311_chlom_construction_gates_control_plane_v1.sql",
    "bytes": 3889,
    "sha256": "184168880bc1dbe525ced4afa0ce197fd27a66628f66560d0b3009c6b5186fc2",
    "git_blob_sha": "996423c8330ea2df8f1d776238f98c1eeafddcec",
}

ASSEMBLIES: dict[str, dict[str, Any]] = {
    "20260821025425": {
        "name": "chlom_construction_gate_catalog_v1",
        "path": MIGRATIONS / "20260821025425_chlom_construction_gate_catalog_v1.sql",
        "part_root": CUSTODY / "20260821025425",
        "bytes": 25248,
        "sha256": "a2ad0cef8f291a0141c30b31211a152d5e89891f03732802972f9b7f39d08b1b",
        "git_blob_sha": "b3a168fda13080328f95f3cb7f00202ec5cac8f0",
        "parts": [
            ("0000.sqlpart", 4096, "aada3a3044c660ca0986a4fc6dd3fe9aee80b7e5e98b7ce3cecfd75cef5742cf", "9f179b3123b6083622b59037b32a05d41d20a6f8"),
            ("0001.sqlpart", 4096, "145a4eed77b4f657e0fcd623d7f7325f0924c7a2f32ce3b1b6f26503f755dd82", "d26bb52a9dff64ed33661793940d6207711b85dc"),
            ("0002.sqlpart", 4096, "c99e1feae34c8c6ea2a56febc14cf9d2ebf07a4f404a37e0ec35cd6571117459", "81d1de77823f8256a479452c35655745992e2282"),
            ("0003.sqlpart", 4096, "7571dfbc04f05cc05f6896a4ba6bb250053e518315331ae918921efacb0a0675", "df832fbec7b80468f0e5d3a88fd4f435a63456cc"),
            ("0004.sqlpart", 4096, "463e41fe6defd5d1a829e749850d365e2e17d36ac00d9445b8bb4072a363dd5f", "9fdb09bb5c936ff1de053e62c1eae48bdac72f92"),
            ("0005.sqlpart", 4096, "14ab45cd80df4c65e88f265fb9b8a71bec94679d2fe3617473d5fd83c1ef779a", "71db259d1e80e452bf7a4b15b282515cf878aad9"),
            ("0006.sqlpart", 672, "4d243f4056c221e4773a947768f32f627e30cc1f0b19e71ec26b515d048650e8", "2cf50d348c4e52b77a5e41b2b86ecd24198c8ee4"),
        ],
    },
    "20260821030400": {
        "name": "chlom_missing_specialist_agents_and_gate_assignments_v1",
        "path": MIGRATIONS / "20260821030400_chlom_missing_specialist_agents_and_gate_assignments_v1.sql",
        "part_root": CUSTODY / "20260821030400",
        "bytes": 9441,
        "sha256": "c5e88ce6ffbbaafe3a48773ce678998db286afa57c216ea5d1071bdbaa57423a",
        "git_blob_sha": "84f287ac7071331a033fc3128319f2986d81a30c",
        "parts": [
            ("0000.sqlpart", 4096, "392782d8205157ae0d982460df96f38b68769ddc43d20a55efd87409899e7db1", "c42c9cff7b69ea114d6ec0771e08d906e435e565"),
            ("0001.sqlpart", 4096, "b4cfc10f88e9b04ad142e393562de8e61b8eccde95e64ee90a7609a202d9f8c0", "fe923fca5f2f608b4450d544482c86360b3ef092"),
            ("0002.sqlpart", 1249, "10ea47130a5013f280a79eea8b9ea413b69e1c304fea929378862315b42be31c", "d1a4f3d1ee0f3e0973ca9acc121e66603b1bdac9"),
        ],
    },
}

MARKERS = (
    MIGRATIONS / "20260821025311_remote_applied_lineage.sql",
    MIGRATIONS / "20260821025425_remote_applied_lineage.sql",
    MIGRATIONS / "20260821030400_remote_applied_lineage.sql",
)

PROHIBITED = (
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"\bsk_(?:live|test)_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bsbp_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bgh[opusr]_[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        rb"(?i)(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*'[^']{8,}'"
    ),
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob_sha(raw: bytes) -> str:
    header = b"blob " + str(len(raw)).encode("ascii") + b"\0"
    return hashlib.sha1(header + raw).hexdigest()


def hold(reason: str) -> None:
    print(f"HOLD_CHLOM_GATE_AGENT_CUSTODY: {reason}", file=sys.stderr)
    raise SystemExit(1)


def verify_bytes(
    *, label: str, raw: bytes, expected_bytes: int, expected_sha256: str, expected_git_sha: str
) -> None:
    if len(raw) != expected_bytes:
        hold(f"{label} bytes expected={expected_bytes} actual={len(raw)}")
    actual_sha256 = sha256(raw)
    if actual_sha256 != expected_sha256:
        hold(
            f"{label} SHA-256 expected={expected_sha256} actual={actual_sha256}"
        )
    actual_git_sha = git_blob_sha(raw)
    if actual_git_sha != expected_git_sha:
        hold(
            f"{label} Git blob expected={expected_git_sha} actual={actual_git_sha}"
        )
    for pattern in PROHIBITED:
        if pattern.search(raw):
            hold(f"{label} contains prohibited credential-like literal")


def assemble(version: str, contract: dict[str, Any]) -> dict[str, Any]:
    chunks: list[bytes] = []
    chunk_evidence: list[dict[str, Any]] = []
    for filename, size, expected_sha256, expected_git_sha in contract["parts"]:
        path: Path = contract["part_root"] / filename
        if not path.is_file():
            hold(f"{version} missing chunk {path.relative_to(ROOT)}")
        raw = path.read_bytes()
        verify_bytes(
            label=f"{version}/{filename}",
            raw=raw,
            expected_bytes=size,
            expected_sha256=expected_sha256,
            expected_git_sha=expected_git_sha,
        )
        chunks.append(raw)
        chunk_evidence.append(
            {
                "path": str(path.relative_to(ROOT)),
                "bytes": len(raw),
                "sha256": sha256(raw),
                "git_blob_sha": git_blob_sha(raw),
            }
        )

    body = b"".join(chunks)
    verify_bytes(
        label=version,
        raw=body,
        expected_bytes=contract["bytes"],
        expected_sha256=contract["sha256"],
        expected_git_sha=contract["git_blob_sha"],
    )
    output: Path = contract["path"]
    output.write_bytes(body)
    return {
        "version": version,
        "provider_name": contract["name"],
        "path": str(output.relative_to(ROOT)),
        "bytes": len(body),
        "sha256": sha256(body),
        "git_blob_sha": git_blob_sha(body),
        "chunks": chunk_evidence,
    }


def verify_unique_version(version: str, expected_path: Path) -> None:
    matches = sorted(path.name for path in MIGRATIONS.glob(f"{version}_*.sql"))
    if matches != [expected_path.name]:
        hold(
            f"version {version} must resolve only to {expected_path.name}; actual={matches}"
        )


def main() -> None:
    direct_path: Path = DIRECT["path"]
    if not direct_path.is_file():
        hold(f"missing direct provider body {direct_path.relative_to(ROOT)}")
    direct_raw = direct_path.read_bytes()
    verify_bytes(
        label=DIRECT["version"],
        raw=direct_raw,
        expected_bytes=DIRECT["bytes"],
        expected_sha256=DIRECT["sha256"],
        expected_git_sha=DIRECT["git_blob_sha"],
    )

    evidence: list[dict[str, Any]] = [
        {
            "version": DIRECT["version"],
            "provider_name": DIRECT["name"],
            "path": str(direct_path.relative_to(ROOT)),
            "bytes": len(direct_raw),
            "sha256": sha256(direct_raw),
            "git_blob_sha": git_blob_sha(direct_raw),
            "chunks": [],
        }
    ]
    for version, contract in ASSEMBLIES.items():
        evidence.append(assemble(version, contract))

    for marker in MARKERS:
        if marker.exists():
            marker.unlink()

    verify_unique_version(DIRECT["version"], direct_path)
    for version, contract in ASSEMBLIES.items():
        verify_unique_version(version, contract["path"])

    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    receipt.update(
        {
            "source_state": "EXACT_PROVIDER_BODIES_MATERIALIZED_REPLAY_PENDING",
            "custody_points": evidence,
            "retired_markers": [str(path.relative_to(ROOT)) for path in MARKERS],
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
                "scope": "CHLOM_GATE_AND_SPECIALIST_AGENT_PROVIDER_CUSTODY",
                "versions": [row["version"] for row in evidence],
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
