#!/usr/bin/env python3
"""Generate deterministic CrownThrive Services Stack package candidates.

The generated 672 records are derived package candidates. They do not change the
Proprietary Asset Factory's authoritative source-IP count and do not activate a
provider write, checkout, entitlement, operative license, D3 decision, or vote.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "developers/manifests/crownthrive-css-asset-matrix.v1.json"
DEFAULT_OUTPUT = ROOT / "build/css-assets"
OWNER = {
    "plugin": "ct.css.agent-productizer",
    "kernel": "ct.css.agent-orchestrator",
    "contract": "ct.css.agent-contract-steward",
    "adapter": "ct.css.agent-provider-adapter",
    "schema": "ct.css.agent-contract-steward",
    "event": "ct.css.agent-contract-steward",
    "workflow": "ct.css.agent-adoption-steward",
    "skill": "ct.css.agent-productizer",
    "script": "ct.css.agent-provider-adapter",
    "test_suite": "ct.css.agent-independent-verifier",
    "runbook": "ct.css.agent-compliance-controller",
    "policy": "ct.css.agent-compliance-controller",
}
TRADE_SECRET = {"kernel", "adapter", "script", "policy"}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build(service_id: str, asset_type: str, profile: str) -> dict[str, Any]:
    service_slug = service_id.removeprefix("ct.css.")
    asset_id = f"ct.css.asset.{service_slug}.{slug(asset_type)}.{slug(profile)}.v1"
    public_basis = f"CSS-ASSET|1.0.0|{service_id}|{asset_type}|{profile}|public-contract"
    package_basis = f"CSS-ASSET|1.0.0|{service_id}|{asset_type}|{profile}|package|protected-implementation"
    verifier = "ct.css.agent-independent-verifier" if OWNER[asset_type] != "ct.css.agent-independent-verifier" else "ct.css.agent-compliance-controller"
    return {
        "asset_id": asset_id,
        "service_id": service_id,
        "asset_type": asset_type,
        "deployment_profile": profile,
        "semantic_version": "1.0.0",
        "classification": "trade_secret" if asset_type in TRADE_SECRET else "restricted",
        "lifecycle_state": "specified",
        "authority_ceiling": "D2",
        "owner_agent_id": OWNER[asset_type],
        "verifier_agent_id": verifier,
        "public_contract_digest": digest(public_basis),
        "package_sha256": digest(package_basis),
        "vault_binding_state": "planned" if asset_type in TRADE_SECRET else "not_applicable",
        "rights_state": "candidate",
        "security_state": "candidate",
        "test_state": "planned",
        "commercial_state": "research",
        "checkout_enabled": False,
        "entitlement_active": False,
        "provider_write_enabled": False,
        "D3_auto": False,
        "sovereign_vote_effect": False,
        "source_asset_count_delta": 0,
        "history_policy": "append_or_supersede_never_silent_delete",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    records = [build(service, asset_type, profile) for service, asset_type, profile in itertools.product(matrix["service_ids"], matrix["asset_types"], matrix["deployment_profiles"])]
    if len(records) != 672 or len({record["asset_id"] for record in records}) != 672:
        raise SystemExit("CSS asset matrix did not produce 672 unique candidates")
    args.output.mkdir(parents=True, exist_ok=True)
    raw = ("\n".join(json.dumps(record, sort_keys=True, separators=(",", ":")) for record in records) + "\n").encode("utf-8")
    root = hashlib.sha256(raw).hexdigest()
    (args.output / "css-assets.v1.jsonl").write_bytes(raw)
    (args.output / "css-assets.receipt.v1.json").write_text(json.dumps({
        "schema_version": "1.0.0",
        "matrix_id": matrix["matrix_id"],
        "candidate_asset_records": 672,
        "catalog_sha256": root,
        "authoritative_asset_count_delta": 0,
        "provider_write_enabled": False,
        "checkout_enabled": False,
        "entitlement_active": False,
        "D3_auto": False,
        "sovereign_vote_effect": False,
        "history_policy": "append_or_supersede_never_silent_delete"
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"state":"generated","candidate_asset_records":672,"catalog_sha256":root,"authoritative_asset_count_delta":0}, indent=2))


if __name__ == "__main__":
    main()
