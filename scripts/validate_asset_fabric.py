#!/usr/bin/env python3
"""Validate the CrownThrive Plugin–Pallet–Kernel Asset Fabric catalog."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "developers/manifests/asset-fabric-source-matrix.v1.json"
DEFAULT_RECEIPT = ROOT / "data/asset-fabric/catalog-receipt.v1.json"
DEFAULT_MANIFEST = ROOT / "developers/manifests/crownthrive-plugin-pallet-kernel-asset-fabric.v1.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_KEYS = {"api_key","secret","private_key","service_role_key","password","credential_value","private_subject_id","decrypted_secret"}


def fail(message: str) -> None:
    raise AssertionError(message)


def walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower()
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def generate_catalog(output_dir: Path) -> Path:
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from generate_asset_fabric import generate  # type: ignore
    generate(DEFAULT_MATRIX, output_dir)
    return output_dir / "catalog-index.v1.json"


def resolve_shard(index_path: Path, shard: dict[str, Any]) -> Path:
    path_value = str(shard["path"])
    if path_value.startswith("generated://asset-fabric/"):
        path_value = path_value.removeprefix("generated://asset-fabric/")
    candidate = index_path.parent / path_value
    if candidate.exists():
        return candidate
    fallback = index_path.parent / "shards" / f"{shard['pallet_id'].lower()}.jsonl.gz.b64"
    if fallback.exists():
        return fallback
    fail(f"missing shard {shard['pallet_id']}")
    raise AssertionError


def load_records(index_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    raw_digests: list[str] = []
    for shard in index["shards"]:
        path = resolve_shard(index_path, shard)
        encoded = path.read_bytes()
        if hashlib.sha256(encoded).hexdigest() != shard["base64_sha256"]:
            fail(f"base64 digest mismatch: {path}")
        compressed = base64.b64decode(encoded)
        if hashlib.sha256(compressed).hexdigest() != shard["gzip_sha256"]:
            fail(f"gzip digest mismatch: {path}")
        raw = gzip.decompress(compressed)
        raw_digest = hashlib.sha256(raw).hexdigest()
        if raw_digest != shard["raw_sha256"]:
            fail(f"raw digest mismatch: {path}")
        raw_digests.append(raw_digest)
        shard_records = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        if len(shard_records) != shard["record_count"]:
            fail(f"shard count mismatch: {path}")
        records.extend(shard_records)
    root_digest = hashlib.sha256("".join(raw_digests).encode("ascii")).hexdigest()
    if root_digest != index["catalog_root_sha256"]:
        fail("catalog root digest mismatch")
    return index, records


def validate(index_path: Path, receipt_path: Path, manifest_path: Path) -> dict[str, Any]:
    index, records = load_records(index_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_count = 5760
    if len(records) != expected_count or index["source_model"]["candidate_asset_records"] != expected_count:
        fail(f"expected {expected_count} records, found {len(records)}")
    if receipt["source_model"]["candidate_asset_records"] != expected_count or manifest["catalog"]["candidate_asset_records"] != expected_count:
        fail("receipt/manifest count mismatch")
    for source in (index, receipt):
        if source["authoritative_asset_count_delta"] != 0:
            fail("derived catalog may not change authoritative source-IP count")
        if source["checkout_enabled"] or source["entitlement_active"] or source["provider_write_enabled"]:
            fail("unexpected activation in catalog metadata")
        if source["D3_auto"] or source["sovereign_vote_effect"]:
            fail("unexpected governance authority in catalog metadata")
        if source["history_policy"] != "append_or_supersede_never_silent_delete":
            fail("history-policy drift")
    if index["catalog_root_sha256"] != receipt["catalog_root_sha256"] or index["catalog_root_sha256"] != manifest["catalog"]["catalog_root_sha256"]:
        fail("catalog root mismatch")
    receipt_shards = {item["pallet_id"]: item for item in receipt["shards"]}
    for shard in index["shards"]:
        expected = receipt_shards.get(shard["pallet_id"])
        if expected is None:
            fail(f"receipt missing shard {shard['pallet_id']}")
        for key in ("record_count", "raw_sha256", "gzip_sha256", "base64_sha256"):
            if shard[key] != expected[key]:
                fail(f"receipt shard mismatch {shard['pallet_id']}:{key}")

    ids = [record["asset_id"] for record in records]
    if len(ids) != len(set(ids)):
        fail("duplicate asset IDs")
    id_set = set(ids)
    pallet_asset_type = Counter()
    pallet_counts = Counter()
    capability_pairs = set()
    asset_types = set()
    profiles = set()
    dependency_edges = 0
    for record in records:
        pallet_counts[record["pallet_id"]] += 1
        pallet_asset_type[(record["pallet_id"], record["asset_type"])] += 1
        capability_pairs.add((record["pallet_id"], record["capability_key"]))
        asset_types.add(record["asset_type"])
        profiles.add(record["deployment_profile"])
        if record["owner_agent_id"] == record["verifier_agent_id"] or record["authority_ceiling"] != "D2":
            fail(f"agent/authority violation: {record['asset_id']}")
        for key in ("checkout_enabled","entitlement_active","provider_write_enabled","D3_auto","sovereign_vote_effect"):
            if record[key] is not False:
                fail(f"{key} must be false: {record['asset_id']}")
        if record["source_asset_count_delta"] != 0 or record["history_policy"] != "append_or_supersede_never_silent_delete":
            fail(f"count/history violation: {record['asset_id']}")
        if not SHA256.fullmatch(record["public_contract_digest"]) or not SHA256.fullmatch(record["package_sha256"]):
            fail(f"invalid digest: {record['asset_id']}")
        for dependency in record["dependencies"]:
            dependency_edges += 1
            if dependency not in id_set:
                fail(f"missing dependency {dependency} for {record['asset_id']}")
        bad_keys = FORBIDDEN_KEYS.intersection(walk_keys(record))
        if bad_keys:
            fail(f"forbidden keys {sorted(bad_keys)} in {record['asset_id']}")

    if len(pallet_counts) != 12 or any(value != 480 for value in pallet_counts.values()):
        fail("each of 12 pallets must contain 480 records")
    if len(capability_pairs) != 120 or len(asset_types) != 12 or len(profiles) != 4:
        fail("matrix dimensionality mismatch")
    if any(value != 40 for value in pallet_asset_type.values()) or dependency_edges != 8640:
        fail("pallet/type or dependency count mismatch")

    agents = manifest["agents"]
    if len(agents) != 7 or sum(agent["role"] == "independent_verifier" for agent in agents) != 1:
        fail("control-agent mesh mismatch")
    for agent in agents:
        if agent["authority_ceiling"] != "D2" or agent["vote_eligible"] or agent["self_approval"]:
            fail(f"agent-governance violation: {agent['agent_id']}")
    if len(manifest["tool_surface"]) != 20:
        fail("root plugin must expose 20 controlled-test tools")

    return {"state":"PASS","candidate_asset_records":len(records),"pallets":len(pallet_counts),"capability_families":len(capability_pairs),"asset_types":len(asset_types),"deployment_profiles":len(profiles),"dependency_edges":dependency_edges,"catalog_root_sha256":index["catalog_root_sha256"],"receipt_match":"PASS","authoritative_asset_count_delta":0,"owner_verifier_separation":"PASS","secret_private_field_scan":"PASS","activation_controls":"PASS","D3_auto":False,"sovereign_vote_effect":False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    if args.index:
        result = validate(args.index.resolve(), args.receipt.resolve(), args.manifest.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="ct-asset-fabric-") as temp:
            result = validate(generate_catalog(Path(temp)), args.receipt.resolve(), args.manifest.resolve())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
