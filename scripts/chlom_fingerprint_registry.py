#!/usr/bin/env python3
"""CrownThrive CHLOM Fingerprint ID deterministic helper.

Public-safe reference implementation. This module does not create identity,
ownership, legal authority, DIDs, credentials, keys, or blockchain state.
It only canonicalizes bounded records under ct-json-c14n-v1 and computes
SHA-256 Fingerprint IDs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PROFILE_ID = "ct-json-c14n-v1"
FINGERPRINT_PREFIX = "ctfp:v1:sha256:"


class CanonicalizationError(ValueError):
    pass


def _validate(value: Any, path: str = "$") -> None:
    if isinstance(value, float):
        raise CanonicalizationError(f"{path}: floating-point values are not permitted in {PROFILE_ID}")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(f"{path}: object keys must be strings")
            _validate(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate(child, f"{path}[{index}]")
    elif value is None or isinstance(value, (str, int, bool)):
        return
    else:
        raise CanonicalizationError(f"{path}: unsupported value type {type(value).__name__}")


def canonicalize(value: Any) -> str:
    """Return deterministic UTF-8 JSON text for the bounded v1 profile."""
    _validate(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_hex(canonical_text: str) -> str:
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def fingerprint_record(value: Any) -> tuple[str, str, str]:
    canonical = canonicalize(value)
    digest = sha256_hex(canonical)
    return canonical, digest, f"{FINGERPRINT_PREFIX}{digest}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file", type=Path, help="JSON file containing one bounded record")
    args = parser.parse_args()

    record = json.loads(args.json_file.read_text(encoding="utf-8"))
    canonical, digest, fingerprint_id = fingerprint_record(record)
    print(json.dumps({
        "profile_id": PROFILE_ID,
        "canonical_json": canonical,
        "sha256": digest,
        "fingerprint_id": fingerprint_id,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
