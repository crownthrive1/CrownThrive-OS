#!/usr/bin/env python3
"""Validate the commercial release package agent contract and negative controls."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_commercial_release_packages.py"
INVENTORY = ROOT / "developers" / "reference" / "commercial-release" / "commercial-gap-products.v1.json"
POLICY = ROOT / "developers" / "reference" / "commercial-release" / "release-policy.v1.json"

def load_builder():
    spec = importlib.util.spec_from_file_location("commercial_release_builder", BUILD)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def assert_negative_controls(builder, package, policy):
    tests = {}

    bad = copy.deepcopy(package)
    bad["commerce"]["cash_checkout_enabled"] = True
    bad["package_sha256"] = builder.sha256_hex({k:v for k,v in bad.items() if k != "package_sha256"})
    tests["cash_checkout_rejected"] = any("cash checkout" in e for e in builder.validate_package(bad, policy))

    bad = copy.deepcopy(package)
    bad["publication"]["automatic_publication_eligible"] = True
    bad["package_sha256"] = builder.sha256_hex({k:v for k,v in bad.items() if k != "package_sha256"})
    tests["premature_publication_rejected"] = any("automatic publication" in e for e in builder.validate_package(bad, policy))

    bad = copy.deepcopy(package)
    bad["gates"][0]["independent_reviewer_id"] = bad["governance"]["producer_agent_id"]
    bad["package_sha256"] = builder.sha256_hex({k:v for k,v in bad.items() if k != "package_sha256"})
    tests["self_review_rejected"] = any("self review" in e for e in builder.validate_package(bad, policy))

    bad = copy.deepcopy(package)
    bad["domain"]["state"] = "ACCEPTED"
    bad["package_sha256"] = builder.sha256_hex({k:v for k,v in bad.items() if k != "package_sha256"})
    tests["dns_tls_shortcut_rejected"] = any("domain acceptance" in e for e in builder.validate_package(bad, policy))

    bad = copy.deepcopy(package)
    bad["credential_contract"]["secret"] = "not-a-real-secret"
    bad["package_sha256"] = builder.sha256_hex({k:v for k,v in bad.items() if k != "package_sha256"})
    tests["secret_key_shape_rejected"] = any("forbidden secret-shaped key" in e for e in builder.validate_package(bad, policy))

    if not all(tests.values()):
        raise AssertionError(f"negative control failure: {tests}")
    return tests

def main() -> int:
    builder = load_builder()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        out_a = Path(a)
        out_b = Path(b)
        summary_a = builder.build_all(INVENTORY, POLICY, out_a)
        summary_b = builder.build_all(INVENTORY, POLICY, out_b)

        files_a = {p.name: p.read_bytes() for p in out_a.glob("*.json")}
        files_b = {p.name: p.read_bytes() for p in out_b.glob("*.json")}
        if files_a != files_b:
            raise AssertionError("deterministic rebuild mismatch")
        if summary_a != summary_b:
            raise AssertionError("summary mismatch")
        if summary_a["product_count"] != 30:
            raise AssertionError(f"expected 30 products, got {summary_a['product_count']}")
        if summary_a["platform_counts"] != {"launch": 10, "procure": 10, "ready": 10}:
            raise AssertionError(f"unexpected platform counts: {summary_a['platform_counts']}")
        if summary_a["accepted_count"] != 0 or summary_a["hold_count"] != 30:
            raise AssertionError("initial run must remain fail-closed")
        if summary_a["cash_checkout_enabled_count"] != 0:
            raise AssertionError("cash checkout drift")
        if summary_a["automatic_publication_eligible_count"] != 0:
            raise AssertionError("publication eligibility drift")

        first = json.loads((out_a / "ct-launch-90d-001.json").read_text(encoding="utf-8"))
        negative = assert_negative_controls(builder, first, policy)

        result = {
            "result": "PASS_COMMERCIAL_RELEASE_PACKAGE_AGENT_CONTROLLED_TEST",
            "product_count": 30,
            "platform_counts": summary_a["platform_counts"],
            "deterministic_rebuild": True,
            "hold_count": 30,
            "accepted_count": 0,
            "cash_checkout_enabled_count": 0,
            "automatic_publication_eligible_count": 0,
            "negative_controls": negative,
            "summary_sha256": summary_a["summary_sha256"],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
