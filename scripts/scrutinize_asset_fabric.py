#!/usr/bin/env python3
"""Independently scrutinize the CrownThrive Asset Fabric candidate catalog."""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts/generate_asset_fabric.py"
VALIDATOR = ROOT / "scripts/validate_asset_fabric.py"
DEFAULT_REPORT = ROOT / "data/asset-fabric/scrutiny-report.v1.json"


def generate(output: Path) -> Path:
    result = subprocess.run([sys.executable, str(GENERATOR), "--output", str(output)], check=False, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return output / "catalog-index.v1.json"


def records(index_path: Path) -> list[dict[str, Any]]:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    result: list[dict[str, Any]] = []
    for shard in index["shards"]:
        path = index_path.parent / "shards" / f"{shard['pallet_id'].lower()}.jsonl.gz.b64"
        raw = gzip.decompress(base64.b64decode(path.read_bytes()))
        result.extend(json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip())
    return result


def scrutinize(index_path: Path) -> dict[str, Any]:
    validation = subprocess.run([sys.executable, str(VALIDATOR), "--index", str(index_path)], check=False, capture_output=True, text=True)
    if validation.returncode:
        raise RuntimeError(validation.stderr or validation.stdout)
    validator = json.loads(validation.stdout)
    entries = records(index_path)
    holds = {
        "rights": sum(item["rights_state"] != "cleared" for item in entries),
        "security": sum(item["security_state"] != "verified" for item in entries),
        "tests": sum(item["test_state"] != "pass" for item in entries),
        "custody": sum(item["custody_state"] != "verified" for item in entries),
        "commercialization": sum(item["commercial_state"] != "live" for item in entries),
    }
    return {
        "schema_version": "1.1.0",
        "report_id": "ct.assetfabric.scrutiny.v1.1",
        "state": "PASS_WITH_CONTROLLED_TEST_HOLDS",
        "validator": validator,
        "counts": {
            "lifecycle": dict(Counter(item["lifecycle_state"] for item in entries)),
            "classification": dict(Counter(item["classification"] for item in entries)),
            "owners": dict(Counter(item["owner_agent_id"] for item in entries)),
            "dependency_cardinality": {str(key): value for key, value in sorted(Counter(len(item["dependencies"]) for item in entries).items())},
            "pallets": dict(sorted(Counter(item["pallet_id"] for item in entries).items())),
            "asset_types": dict(sorted(Counter(item["asset_type"] for item in entries).items())),
            "deployment_profiles": dict(sorted(Counter(item["deployment_profile"] for item in entries).items())),
        },
        "holds": holds,
        "hold_interpretation": "All 5,760 records are structurally valid derived package candidates. They remain non-production until applicable rights, security, tests, custody, runtime, accessibility, fulfillment and independent-verification gates pass.",
        "promotion_allowed": False,
        "provider_write_allowed": False,
        "checkout_enabled": False,
        "entitlement_active": False,
        "D3_auto": False,
        "sovereign_vote_effect": False,
        "owner_agent_id": "ct.asset.agent-governor",
        "verifier_agent_id": "ct.asset.agent-scrutinizer",
        "history_policy": "append_or_supersede_never_silent_delete",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.index:
        report = scrutinize(args.index.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="ct-asset-scrutiny-") as temp:
            report = scrutinize(generate(Path(temp)))
    if args.write:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
