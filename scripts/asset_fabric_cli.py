#!/usr/bin/env python3
"""Cross-platform CLI for the CrownThrive Plugin–Pallet–Kernel Asset Fabric."""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "data/asset-fabric/catalog-receipt.v1.json"
BUILD = ROOT / "build/asset-fabric"
INDEX = BUILD / "catalog-index.v1.json"
GENERATOR = ROOT / "scripts/generate_asset_fabric.py"
VALIDATOR = ROOT / "scripts/validate_asset_fabric.py"
SCRUTINIZER = ROOT / "scripts/scrutinize_asset_fabric.py"


def receipt() -> dict[str, Any]:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def ensure_catalog() -> Path:
    expected = receipt()["catalog_root_sha256"]
    if INDEX.exists():
        current = json.loads(INDEX.read_text(encoding="utf-8"))
        if current.get("catalog_root_sha256") == expected:
            return INDEX
    result = subprocess.run([sys.executable, str(GENERATOR), "--output", str(BUILD)], check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
    return INDEX


def records() -> Iterable[dict[str, Any]]:
    index = json.loads(ensure_catalog().read_text(encoding="utf-8"))
    for shard in index["shards"]:
        path = INDEX.parent / "shards" / f"{shard['pallet_id'].lower()}.jsonl.gz.b64"
        raw = gzip.decompress(base64.b64decode(path.read_bytes()))
        for line in raw.decode("utf-8").splitlines():
            if line.strip():
                yield json.loads(line)


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def cmd_status(_: argparse.Namespace) -> None:
    data = receipt()
    emit({"suite_id":data["suite_id"],"state":data["lifecycle_state"],"candidate_asset_records":data["source_model"]["candidate_asset_records"],"catalog_root_sha256":data["catalog_root_sha256"],"pallets":data["source_model"]["pallets"],"capability_families":data["source_model"]["capability_families_total"],"asset_types":data["source_model"]["asset_types"],"deployment_profiles":data["source_model"]["deployment_profiles"],"authoritative_asset_count_delta":0,"checkout_enabled":False,"entitlement_active":False,"provider_write_enabled":False,"D3_auto":False})


def cmd_search(args: argparse.Namespace) -> None:
    query = args.query.lower().strip()
    found = []
    for record in records():
        if args.pallet and record["pallet_id"] != args.pallet: continue
        if args.asset_type and record["asset_type"] != args.asset_type: continue
        if args.profile and record["deployment_profile"] != args.profile: continue
        haystack = " ".join([record["asset_id"],record["canonical_name"],record["pallet_name"],record["capability_key"],record["asset_type"],record["deployment_profile"]]).lower()
        if query in haystack:
            found.append(record)
            if len(found) >= args.limit: break
    emit(found)


def cmd_get(args: argparse.Namespace) -> None:
    for record in records():
        if record["asset_id"] == args.asset_id:
            emit(record); return
    raise SystemExit(f"asset not found: {args.asset_id}")


def cmd_dependencies(args: argparse.Namespace) -> None:
    all_records = list(records())
    by_id = {item["asset_id"]: item for item in all_records}
    item = by_id.get(args.asset_id)
    if not item: raise SystemExit(f"asset not found: {args.asset_id}")
    reverse = [candidate["asset_id"] for candidate in all_records if args.asset_id in candidate["dependencies"]]
    emit({"asset_id":args.asset_id,"dependencies":item["dependencies"],"reverse_dependencies":reverse})


def run(script: Path, *extra: str) -> None:
    result = subprocess.run([sys.executable, str(script), *extra], check=False)
    raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(prog="thrive-assets")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status"); status.set_defaults(func=cmd_status)
    search = sub.add_parser("search"); search.add_argument("query"); search.add_argument("--pallet"); search.add_argument("--asset-type"); search.add_argument("--profile"); search.add_argument("--limit", type=int, default=25); search.set_defaults(func=cmd_search)
    get = sub.add_parser("get"); get.add_argument("asset_id"); get.set_defaults(func=cmd_get)
    deps = sub.add_parser("dependencies"); deps.add_argument("asset_id"); deps.set_defaults(func=cmd_dependencies)
    generate = sub.add_parser("generate"); generate.set_defaults(func=lambda _: run(GENERATOR, "--output", str(BUILD)))
    validate = sub.add_parser("validate"); validate.set_defaults(func=lambda _: run(VALIDATOR))
    scrutinize = sub.add_parser("scrutinize"); scrutinize.set_defaults(func=lambda _: run(SCRUTINIZER))
    args = parser.parse_args(); args.func(args)


if __name__ == "__main__":
    main()
