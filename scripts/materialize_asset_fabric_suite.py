#!/usr/bin/env python3
"""Materialize and validate the Asset Fabric from canonical repository sources.

The earlier bundle experiment was intentionally replaced. The source matrix,
generator, receipt, validator, and scrutinizer are the canonical materialization
path; no hidden source bundle or chunk directory is required.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/asset-fabric"
GENERATOR = ROOT / "scripts/generate_asset_fabric.py"
VALIDATOR = ROOT / "scripts/validate_asset_fabric.py"
SCRUTINIZER = ROOT / "scripts/scrutinize_asset_fabric.py"
RECEIPT = ROOT / "data/asset-fabric/materialization-receipt.v1.json"


def run(*args: str) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    run(str(GENERATOR), "--output", str(OUTPUT))
    run(str(VALIDATOR), "--index", str(OUTPUT / "catalog-index.v1.json"))
    run(str(SCRUTINIZER), "--index", str(OUTPUT / "catalog-index.v1.json"))
    catalog = json.loads((OUTPUT / "catalog-index.v1.json").read_text(encoding="utf-8"))
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps({
        "state": "materialized_and_validated",
        "suite_id": catalog["suite_id"],
        "catalog_root_sha256": catalog["catalog_root_sha256"],
        "candidate_asset_records": catalog["source_model"]["candidate_asset_records"],
        "authoritative_asset_count_delta": 0,
        "checkout_enabled": False,
        "entitlement_active": False,
        "provider_write_enabled": False,
        "D3_auto": False,
        "history_policy": "append_or_supersede_never_silent_delete"
    }, indent=2) + "\n", encoding="utf-8")
    print(RECEIPT)


if __name__ == "__main__":
    main()
