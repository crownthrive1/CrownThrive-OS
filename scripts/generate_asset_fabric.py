#!/usr/bin/env python3
"""Generate the CrownThrive Plugin–Pallet–Kernel Asset Fabric candidate catalog.

The generated records are deterministic derived package candidates. They do not
change the authoritative Proprietary Asset Factory source-IP count and do not
activate production code, provider writes, commerce, entitlements, D3 authority,
or sovereign votes.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import itertools
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "developers/manifests/asset-fabric-source-matrix.v1.json"
DEFAULT_OUTPUT = ROOT / "build/asset-fabric"
DEFAULT_RECEIPT = ROOT / "data/asset-fabric/catalog-receipt.v1.json"

OWNER_BY_TYPE = {
    "plugin": "ct.asset.agent-plugin-productizer",
    "pallet_bundle": "ct.asset.agent-governor",
    "kernel": "ct.asset.agent-kernel-builder",
    "executable": "ct.asset.agent-kernel-builder",
    "script": "ct.asset.agent-kernel-builder",
    "skill": "ct.asset.agent-plugin-productizer",
    "prompt": "ct.asset.agent-plugin-productizer",
    "mcp_tool_pack": "ct.asset.agent-contract-steward",
    "api_adapter": "ct.asset.agent-contract-steward",
    "event_handler": "ct.asset.agent-contract-steward",
    "schema_contract": "ct.asset.agent-contract-steward",
    "test_suite": "ct.asset.agent-release-sentinel",
}
VERIFIER = "ct.asset.agent-scrutinizer"
TRADE_SECRET_TYPES = {"kernel", "executable", "script", "prompt"}
PUBLIC_CONTRACT_TYPES = {"schema_contract", "test_suite", "mcp_tool_pack"}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def dependency_ids(pallet_id: str, capability: str, asset_type: str, profile: str) -> list[str]:
    base = f"ct.assetfabric.{pallet_id.lower()}.{slug(capability)}"
    profile_slug = slug(profile)
    ref = lambda kind: f"{base}.{slug(kind)}.{profile_slug}.v1"
    mapping = {
        "plugin": ["pallet_bundle", "mcp_tool_pack", "test_suite"],
        "pallet_bundle": ["kernel", "schema_contract", "test_suite"],
        "executable": ["kernel", "script", "test_suite"],
        "api_adapter": ["schema_contract", "event_handler", "test_suite"],
        "mcp_tool_pack": ["schema_contract", "test_suite"],
        "event_handler": ["schema_contract", "test_suite"],
        "skill": ["prompt", "test_suite"],
    }
    return [ref(kind) for kind in mapping.get(asset_type, [])]


def build_record(pallet_id: str, pallet_name: str, capability: str, asset_type: str, profile: str, matrix_version: str) -> dict[str, Any]:
    semantic_version = "1.0.0"
    asset_id = f"ct.assetfabric.{pallet_id.lower()}.{slug(capability)}.{slug(asset_type)}.{slug(profile)}.v1"
    contract_basis = "|".join(["ct.assetfabric.contract", matrix_version, pallet_id, pallet_name, capability, asset_type, profile, semantic_version])
    package_basis = f"{contract_basis}|package|public-contract-private-implementation"
    return {
        "asset_id": asset_id,
        "canonical_name": f"{pallet_name} {capability.replace('_', ' ').title()} {asset_type.replace('_', ' ').title()} ({profile.replace('_', ' ').title()})",
        "pallet_id": pallet_id,
        "pallet_name": pallet_name,
        "capability_key": capability,
        "asset_type": asset_type,
        "deployment_profile": profile,
        "semantic_version": semantic_version,
        "lifecycle_state": "specified",
        "authority_ceiling": "D2",
        "classification": "trade_secret" if asset_type in TRADE_SECRET_TYPES else "restricted",
        "public_contract_available": asset_type in PUBLIC_CONTRACT_TYPES,
        "public_contract_digest": sha256_text(contract_basis),
        "package_sha256": sha256_text(package_basis),
        "owner_agent_id": OWNER_BY_TYPE[asset_type],
        "verifier_agent_id": VERIFIER,
        "dependencies": dependency_ids(pallet_id, capability, asset_type, profile),
        "rights_state": "candidate",
        "security_state": "candidate",
        "test_state": "planned",
        "custody_state": "planned",
        "commercial_state": "research",
        "checkout_enabled": False,
        "entitlement_active": False,
        "provider_write_enabled": False,
        "D3_auto": False,
        "sovereign_vote_effect": False,
        "source_asset_count_delta": 0,
        "source_factory_ref": "ct.fleet.chlom-proprietary-asset-factory.100k-plus",
        "history_policy": "append_or_supersede_never_silent_delete",
    }


def generate(matrix_path: Path, output_dir: Path) -> dict[str, Any]:
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    asset_types: list[str] = matrix["asset_types"]
    profiles: list[str] = matrix["deployment_profiles"]
    output_dir.mkdir(parents=True, exist_ok=True)
    shards_dir = output_dir / "shards"
    shards_dir.mkdir(parents=True, exist_ok=True)
    shards: list[dict[str, Any]] = []
    total = 0
    for pallet in matrix["pallets"]:
        records = [
            build_record(pallet["pallet_id"], pallet["pallet_name"], capability, asset_type, profile, matrix["version"])
            for capability, asset_type, profile in itertools.product(pallet["capability_families"], asset_types, profiles)
        ]
        raw = ("\n".join(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) for record in records) + "\n").encode("utf-8")
        compressed = gzip.compress(raw, compresslevel=9, mtime=0)
        encoded = base64.b64encode(compressed)
        name = f"{pallet['pallet_id'].lower()}.jsonl.gz.b64"
        (shards_dir / name).write_bytes(encoded)
        total += len(records)
        shards.append({
            "pallet_id": pallet["pallet_id"], "pallet_name": pallet["pallet_name"], "record_count": len(records),
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "gzip_sha256": hashlib.sha256(compressed).hexdigest(),
            "base64_sha256": hashlib.sha256(encoded).hexdigest(), "path": f"shards/{name}",
            "raw_bytes": len(raw), "gzip_bytes": len(compressed),
        })
    catalog_root = hashlib.sha256("".join(item["raw_sha256"] for item in shards).encode("ascii")).hexdigest()
    index = {
        "schema_version": "1.1.0", "suite_id": "ct.assetfabric.suite.v1",
        "canonical_name": "CrownThrive Plugin–Pallet–Kernel Asset Fabric", "matrix_version": matrix["version"],
        "source_model": {"pallets":len(matrix["pallets"]),"capability_families_total":sum(len(p["capability_families"]) for p in matrix["pallets"]),"asset_types":len(asset_types),"deployment_profiles":len(profiles),"candidate_asset_records":total},
        "asset_types": asset_types, "deployment_profiles": profiles, "catalog_root_sha256": catalog_root, "shards": shards,
        "authoritative_asset_count_delta": 0, "authoritative_factory": "ct.fleet.chlom-proprietary-asset-factory.100k-plus",
        "authoritative_generation_assets": 100800,
        "counting_note": "Derived package candidates bind the existing CrownThrive proprietary estate and do not silently add independent source-IP claims.",
        "lifecycle_state": "controlled_test_candidate_catalog", "checkout_enabled": False, "entitlement_active": False,
        "provider_write_enabled": False, "D3_auto": False, "sovereign_vote_effect": False,
        "history_policy": "append_or_supersede_never_silent_delete",
    }
    (output_dir / "catalog-index.v1.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return index


def receipt_from_index(index: dict[str, Any]) -> dict[str, Any]:
    receipt = json.loads(json.dumps(index))
    receipt["receipt_id"] = "ct.assetfabric.catalog-receipt.v1.1"
    receipt["repository_embedded_records"] = False
    receipt["deterministic_materialization"] = "scripts/generate_asset_fabric.py"
    for shard in receipt["shards"]:
        shard["path"] = f"generated://asset-fabric/{shard['path']}"
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write-receipt", action="store_true")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    index = generate(args.matrix.resolve(), args.output.resolve())
    if args.write_receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt_from_index(index), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"state":"generated","candidate_asset_records":index["source_model"]["candidate_asset_records"],"catalog_root_sha256":index["catalog_root_sha256"],"authoritative_asset_count_delta":0,"checkout_enabled":False,"D3_auto":False}, indent=2))


if __name__ == "__main__":
    main()
