#!/usr/bin/env python3
"""Compatibility validator for Commercial Release Factory v2 packages."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from commercial_release_factory import validate_package


def validate(payload: dict, expected_products: int | None = None) -> dict[str, int]:
    packages = payload.get("packages")
    if not isinstance(packages, list):
        raise ValueError("packages must be an array")
    if expected_products is not None and len(packages) != expected_products:
        raise ValueError(f"expected {expected_products} packages; found {len(packages)}")
    for package in packages:
        validate_package(package)
    passed = sum(g.get("state") == "pass" for p in packages for g in p.get("canonical_gates", []))
    held = sum(g.get("state") == "hold" for p in packages for g in p.get("canonical_gates", []))
    return {"packages": len(packages), "pass_gates": passed, "hold_gates": held}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--expected-products", type=int)
    args = parser.parse_args()
    summary = validate(json.loads(args.input.read_text()), args.expected_products)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
