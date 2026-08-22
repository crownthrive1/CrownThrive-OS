#!/usr/bin/env python3
"""Validate the perpetual, fail-closed commercial release package factory."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
from collections import Counter
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
    bad["package_sha256"] = builder.sha256_hex({k: v for k, v in bad.items() if k != "package_sha256"})
    tests["cash_checkout_rejected"] = any("cash checkout" in e for e in builder.validate_package(bad, policy))

    bad = copy.deepcopy(package)
    bad["publication"]["automatic_publication_eligible"] = True
    bad["package_sha256"] = builder.sha256_hex({k: v for k, v in bad.items() if k != "package_sha256"})
    tests["premature_publication_rejected"] = any("automatic publication" in e for e in builder.validate_package(bad, policy))

    bad = copy.deepcopy(package)
    bad["gates"][0]["independent_reviewer_id"] = bad["governance"]["producer_agent_id"]
    bad["package_sha256"] = builder.sha256_hex({k: v for k, v in bad.items() if k != "package_sha256"})
    tests["self_review_rejected"] = any("self review" in e for e in builder.validate_package(bad, policy))

    bad = copy.deepcopy(package)
    bad["domain"]["state"] = "ACCEPTED"
    bad["package_sha256"] = builder.sha256_hex({k: v for k, v in bad.items() if k != "package_sha256"})
    tests["dns_tls_shortcut_rejected"] = any("domain acceptance" in e for e in builder.validate_package(bad, policy))

    bad = copy.deepcopy(package)
    bad["credential_contract"]["secret"] = "not-a-real-secret"
    bad["package_sha256"] = builder.sha256_hex({k: v for k, v in bad.items() if k != "package_sha256"})
    tests["secret_key_shape_rejected"] = any("forbidden secret-shaped key" in e for e in builder.validate_package(bad, policy))

    if not all(tests.values()):
        raise AssertionError(f"negative control failure: {tests}")
    return tests


def expected_inventory_state() -> tuple[int, dict[str, int]]:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    products = inventory.get("products") or []
    if not products:
        raise AssertionError("commercial inventory must contain at least one governed candidate")
    platform_counts = dict(sorted(Counter(str(item["platform_key"]) for item in products).items()))
    return len(products), platform_counts


def main() -> int:
    builder = load_builder()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    expected_count, expected_platform_counts = expected_inventory_state()

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
        if summary_a["product_count"] != expected_count:
            raise AssertionError(f"inventory/build product-count mismatch: inventory={expected_count} build={summary_a['product_count']}")
        if summary_a["platform_counts"] != expected_platform_counts:
            raise AssertionError(f"inventory/build platform-count mismatch: expected={expected_platform_counts} actual={summary_a['platform_counts']}")

        # Every currently discovered candidate starts fail-closed. Adding future products
        # expands the candidate set; it never inherits PASS from an older product/version.
        if summary_a["accepted_count"] != 0 or summary_a["hold_count"] != expected_count:
            raise AssertionError("current candidate inventory must remain fail-closed pending independent acceptance")
        if summary_a["cash_checkout_enabled_count"] != 0:
            raise AssertionError("cash checkout drift")
        if summary_a["automatic_publication_eligible_count"] != 0:
            raise AssertionError("publication eligibility drift")

        package_paths = sorted(p for p in out_a.glob("ct-*.json") if p.name != "summary.json")
        if len(package_paths) != expected_count:
            raise AssertionError("one exact release package is required per current inventory product")
        first = json.loads(package_paths[0].read_text(encoding="utf-8"))
        negative = assert_negative_controls(builder, first, policy)

        result = {
            "result": "PASS_COMMERCIAL_RELEASE_PACKAGE_AGENT_CONTROLLED_TEST",
            "factory_mode": "PERPETUAL_CANDIDATE_PROCESSING_FAIL_CLOSED",
            "current_product_count": expected_count,
            "current_platform_counts": expected_platform_counts,
            "terminal_product_count": None,
            "new_or_changed_versions_reenter_gates": True,
            "prior_version_pass_inheritance": False,
            "ecac_required_before_economic_activation": True,
            "deterministic_rebuild": True,
            "hold_count": expected_count,
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
