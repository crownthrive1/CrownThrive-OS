#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "supabase/migration_lineage/chlom_institutional_foundation_custody_v8.json"
RECEIPT_PATH = ROOT / "supabase/migration_lineage/chlom_institutional_foundation_materialization_v8.json"

PROHIBITED = (
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"\bsk_(?:live|test)_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bsbp_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bgh[opusr]_[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"(?i)(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*'[^']{8,}'"),
)


def digest(path: Path) -> tuple[int, str, bytes]:
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest(), data


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}
    errors: list[str] = []

    carrier = ROOT / contract["transport"]["path"]
    if not carrier.is_file():
        errors.append("missing:carrier")
    else:
        size, sha, _ = digest(carrier)
        checks["carrier_exact"] = size == contract["transport"]["bytes"] and sha == contract["transport"]["sha256"]

    for row in contract["migrations"]:
        version = row["version"]
        active = ROOT / row["active_path"]
        marker = ROOT / row["retired_marker_path"]
        checks[f"{version}_marker_absent"] = not marker.exists()
        if not active.is_file():
            errors.append(f"missing:{row['active_path']}")
            continue
        size, sha, data = digest(active)
        checks[f"{version}_exact"] = size == row["bytes"] and sha == row["sha256"]
        checks[f"{version}_required_objects"] = all(item.encode("utf-8") in data for item in row["required_objects"])
        checks[f"{version}_no_secret_literals"] = not any(pattern.search(data) for pattern in PROHIBITED)

    if RECEIPT_PATH.is_file():
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        checks["materialization_receipt"] = (
            receipt.get("decision") == "PASS_EXACT_PROVIDER_INSTITUTIONAL_FOUNDATION_MATERIALIZED"
            and receipt.get("production_mutation") is False
            and receipt.get("authority_created") is False
        )
    else:
        errors.append("missing:materialization_receipt")

    checks["provider_versions_unique"] = len({row["version"] for row in contract["migrations"]}) == len(contract["migrations"])
    checks["clean_preview_required"] = contract["invariants"].get("clean_preview_required_before_merge") is True
    errors.extend(sorted(name for name, passed in checks.items() if not passed))
    result = {
        "decision": "PASS_CHLOM_INSTITUTIONAL_FOUNDATION_CUSTODY_V8" if not errors else "HOLD_CHLOM_INSTITUTIONAL_FOUNDATION_CUSTODY_V8",
        "pass": not errors,
        "checks": checks,
        "errors": errors,
        "production_mutation": False,
        "authority_created": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
