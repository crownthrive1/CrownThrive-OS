#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "supabase/migration_lineage/chlom_institutional_foundation_custody_v8.json"
TRANSPORT_KEY = "ct-replay-custody-institutional-foundation-v8"

PROHIBITED = (
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"\bsk_(?:live|test)_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bsbp_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bgh[opusr]_[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"(?i)(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*'[^']{8,}'"),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(code: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    raise SystemExit(f"HOLD_CHLOM_INSTITUTIONAL_FOUNDATION_{code}{suffix}")


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    transport = contract["transport"]
    carrier_path = ROOT / transport["path"]
    carrier = carrier_path.read_bytes()
    if len(carrier) != transport["bytes"]:
        fail("CARRIER_BYTES", f"{len(carrier)} != {transport['bytes']}")
    if sha256(carrier) != transport["sha256"]:
        fail("CARRIER_SHA256")

    try:
        proc = subprocess.run(
            [
                "gpg",
                "--batch",
                "--yes",
                "--quiet",
                "--pinentry-mode",
                "loopback",
                "--passphrase",
                TRANSPORT_KEY,
                "--decrypt",
                str(carrier_path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        fail("DECRYPT", exc.stderr.decode("utf-8", errors="replace")[-500:])

    payload_bytes = proc.stdout
    payload_meta = contract["payload"]
    if len(payload_bytes) != payload_meta["bytes"]:
        fail("PAYLOAD_BYTES", f"{len(payload_bytes)} != {payload_meta['bytes']}")
    if sha256(payload_bytes) != payload_meta["sha256"]:
        fail("PAYLOAD_SHA256")

    payload = json.loads(payload_bytes.decode("utf-8"))
    if payload.get("schema") != "crownthrive.supabase.provider-custody-bundle/v1":
        fail("PAYLOAD_SCHEMA")
    if payload.get("project_ref") != contract["project_ref"]:
        fail("PROJECT_REF")

    payload_rows = {
        str(row.get("version")): row
        for row in payload.get("migrations", [])
        if isinstance(row, dict)
    }
    expected_rows = {row["version"]: row for row in contract["migrations"][:2]}
    if set(payload_rows) != set(expected_rows):
        fail("VERSION_SET", repr(sorted(payload_rows)))

    materialized: list[dict[str, object]] = []
    for version, expected in expected_rows.items():
        row = payload_rows[version]
        if row.get("name") != expected["provider_name"]:
            fail("PROVIDER_NAME", version)
        statement = row.get("statement")
        if not isinstance(statement, str):
            fail("STATEMENT_TYPE", version)
        data = statement.encode("utf-8")
        if len(data) != expected["bytes"] or row.get("bytes") != expected["bytes"]:
            fail("STATEMENT_BYTES", version)
        if sha256(data) != expected["sha256"] or row.get("sha256") != expected["sha256"]:
            fail("STATEMENT_SHA256", version)
        for pattern in PROHIBITED:
            if pattern.search(data):
                fail("SECRET_PATTERN", f"{version}:{pattern.pattern!r}")
        for required in expected["required_objects"]:
            if required.encode("utf-8") not in data:
                fail("REQUIRED_OBJECT", f"{version}:{required}")

        active = ROOT / expected["active_path"]
        marker = ROOT / expected["retired_marker_path"]
        active.parent.mkdir(parents=True, exist_ok=True)
        active.write_bytes(data)
        if marker.exists():
            marker.unlink()
        materialized.append(
            {
                "version": version,
                "provider_name": expected["provider_name"],
                "path": expected["active_path"],
                "bytes": len(data),
                "sha256": sha256(data),
                "marker_removed": not marker.exists(),
            }
        )

    receipt = {
        "schema": "crownthrive.supabase.chlom-institutional-foundation-materialization/v8",
        "project_ref": contract["project_ref"],
        "carrier": {
            "path": transport["path"],
            "bytes": len(carrier),
            "sha256": sha256(carrier),
        },
        "payload": {
            "bytes": len(payload_bytes),
            "sha256": sha256(payload_bytes),
        },
        "migrations": materialized,
        "decision": "PASS_EXACT_PROVIDER_INSTITUTIONAL_FOUNDATION_MATERIALIZED",
        "production_mutation": False,
        "authority_created": False,
    }
    receipt_path = ROOT / "supabase/migration_lineage/chlom_institutional_foundation_materialization_v8.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
