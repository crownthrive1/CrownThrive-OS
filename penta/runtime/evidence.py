#!/usr/bin/env python3
"""Shared deterministic evidence helpers for PENTA production runtimes."""
from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: pathlib.Path, value: object) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def receipt(*, system: str, operation: str, status: str, authority_ref: str, inputs: object, outputs: object) -> dict:
    body = {
        "schema_version": "1.0.0",
        "system": system,
        "operation": operation,
        "status": status,
        "authority_ref": authority_ref,
        "observed_at": utc_now(),
        "inputs_sha256": sha256(inputs),
        "outputs_sha256": sha256(outputs),
        "authority_note": "A receipt proves execution evidence only. It does not manufacture legal, provider, economic, publication, or governance authority."
    }
    body["receipt_sha256"] = sha256(body)
    return body
