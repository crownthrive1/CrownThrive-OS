#!/usr/bin/env python3
"""Validate PentaBooks v4 governance receipts.

This checks source-control metadata only. Remote custody byte readback and
provider/public canaries remain separate release predicates.
"""

import argparse
import json
import re
import sys
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED = {
    "schema", "rotation_id", "wave_id", "track_id", "baseline_id",
    "product_count", "internal_package_qa", "custody_state",
    "provider_state", "public_release_state", "final_os_control_sha256",
    "products", "trade_secret_policy"
}


def validate(data):
    missing = sorted(REQUIRED - set(data))
    if missing:
        raise ValueError(f"missing keys: {missing}")
    if data["schema"] != "ct.pentabooks.rotation-receipt.v4":
        raise ValueError("unsupported schema")
    if data["baseline_id"] != "PB-BASELINE-004":
        raise ValueError("wrong baseline")
    if data.get("candidate_values_are_revenue") is not False:
        raise ValueError("candidate value must be explicitly non-revenue")
    if not SHA256_RE.fullmatch(data["final_os_control_sha256"]):
        raise ValueError("invalid control SHA-256")
    products = data["products"]
    if not isinstance(products, list) or data["product_count"] != len(products):
        raise ValueError("product count mismatch")
    seen = set()
    for product in products:
        if not all(product.get(k) for k in ("sku", "title", "sha256")):
            raise ValueError("incomplete product record")
        if product["sku"] in seen:
            raise ValueError(f"duplicate SKU: {product['sku']}")
        seen.add(product["sku"])
        if not SHA256_RE.fullmatch(product["sha256"]):
            raise ValueError(f"invalid product SHA-256: {product['sku']}")
    if data["provider_state"] not in {"NOT_ACTIVATED", "ACTIVATED_WITH_EVIDENCE"}:
        raise ValueError("invalid provider state")
    if data["public_release_state"] not in {"NOT_PUBLIC", "PUBLIC_WITH_EVIDENCE"}:
        raise ValueError("invalid public release state")
    if data["trade_secret_policy"] != "METADATA_ONLY_PUBLIC_SURFACES_SECRET_VALUES_VAULT_ONLY":
        raise ValueError("invalid trade-secret boundary")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.receipt.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("receipt root must be an object")
        validate(data)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {data['product_count']} governed PentaBooks products")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
