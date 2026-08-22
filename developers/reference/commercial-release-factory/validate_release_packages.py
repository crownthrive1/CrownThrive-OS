#!/usr/bin/env python3
"""Fail-closed validator for CrownThrive commercial release-package projections."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate(payload: dict[str, Any], expected_products: int | None = None) -> dict[str, int]:
    packages = payload.get("packages")
    if not isinstance(packages, list):
        raise ValueError("packages must be an array")
    if expected_products is not None and len(packages) != expected_products:
        raise ValueError(f"expected {expected_products} packages; found {len(packages)}")
    if payload.get("direct_provider_write") is not False:
        raise ValueError("direct provider write must remain false")
    if payload.get("checkout_enabled") is not False:
        raise ValueError("checkout must remain closed")
    if payload.get("sovereign_votes_created") is not False:
        raise ValueError("package generation cannot create sovereign votes")

    seen: set[str] = set()
    pass_gates = hold_gates = 0
    for package in packages:
        sku = package.get("sku")
        if not isinstance(sku, str) or sku in seen:
            raise ValueError(f"duplicate or invalid SKU {sku!r}")
        seen.add(sku)
        if package.get("credit_only") is not True or package.get("checkout_mode") != "credits_only":
            raise ValueError(f"{sku}: credit-only invariant failed")
        if package.get("checkout_state") != "closed" or package.get("stripe_objects_created") is not False:
            raise ValueError(f"{sku}: checkout/provider-object invariant failed")
        if package.get("governed_acceptance_state") != "waiting_for_all_certifications_then_sovereign_vote":
            raise ValueError(f"{sku}: governed acceptance state invalid")
        if package.get("destination_state") != "hold_feed_consumer_unverified":
            raise ValueError(f"{sku}: destination must remain held")
        if not SHA256_RE.fullmatch(str(package.get("package_sha256") or "")):
            raise ValueError(f"{sku}: package SHA-256 invalid")
        gates = package.get("gates")
        if not isinstance(gates, list):
            raise ValueError(f"{sku}: gates must be an array")
        gate_keys = [gate.get("dimension_key") for gate in gates]
        required = package.get("required_dimensions")
        if gate_keys != required:
            raise ValueError(f"{sku}: gate sequence and required dimensions diverge")
        for item in gates:
            if item.get("state") == "pass":
                pass_gates += 1
            elif item.get("state") == "hold":
                hold_gates += 1
            else:
                raise ValueError(f"{sku}: initial gate state must be pass or hold")
    return {"packages": len(packages), "pass_gates": pass_gates, "hold_gates": hold_gates}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--expected-products", type=int)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    summary = validate(payload, expected_products=args.expected_products)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
