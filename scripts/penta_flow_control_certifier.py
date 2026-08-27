#!/usr/bin/env python3
"""Deterministic, fail-closed verifier for a campaign-bound Penta runtime release.

This tool does not manufacture certification. A campaign is CERTIFIED only when an
independent verifier receipt is present and matches the exact campaign and release,
and rollback/readback evidence is complete. Missing evidence yields a non-zero exit.

Input is a JSON evidence bundle. No network or secret access is required.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_BINDING = {
    "max_concurrency": 4,
    "max_claim_batch": 8,
    "max_cost_minor": 0,
    "max_internal_units": 1_000_000,
    "independent_evidence_required": True,
    "provider_write_authority": False,
    "money_movement_authority": False,
    "rights_disposition_authority": False,
    "credential_authority": False,
    "nonrenewing": True,
}


def _fail(check: str, reason: str) -> dict[str, str]:
    return {"check": check, "status": "FAIL", "reason": reason}


def _pass(check: str) -> dict[str, str]:
    return {"check": check, "status": "PASS"}


def verify(bundle: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    checks: list[dict[str, str]] = []
    campaign_id = bundle.get("campaign_id")
    release = bundle.get("release", {})
    binding = bundle.get("binding", {})
    runtime = bundle.get("runtime_readback", {})
    receipt = bundle.get("independent_verifier_receipt")
    rollback = bundle.get("rollback_readback", {})

    if not campaign_id:
        checks.append(_fail("campaign_id", "campaign_id is required"))
    else:
        checks.append(_pass("campaign_id"))

    if not release.get("repository") or not release.get("commit_sha"):
        checks.append(_fail("exact_release", "repository and exact commit_sha are required"))
    else:
        checks.append(_pass("exact_release"))

    for key, expected in REQUIRED_BINDING.items():
        actual = binding.get(key)
        if actual != expected:
            checks.append(_fail(f"binding.{key}", f"expected {expected!r}, got {actual!r}"))
        else:
            checks.append(_pass(f"binding.{key}"))

    if runtime.get("adapter_enabled") is not False:
        checks.append(_fail("provider_adapter", "provider adapter must be disabled"))
    else:
        checks.append(_pass("provider_adapter"))

    if runtime.get("provider_jobs_released") is not False:
        checks.append(_fail("provider_jobs", "provider jobs must not be released"))
    else:
        checks.append(_pass("provider_jobs"))

    if runtime.get("paid_cost_minor", 0) != 0:
        checks.append(_fail("paid_cost", "paid/provider cost must remain zero"))
    else:
        checks.append(_pass("paid_cost"))

    if not runtime.get("readback_verified"):
        checks.append(_fail("runtime_readback", "runtime readback evidence is missing or unverified"))
    else:
        checks.append(_pass("runtime_readback"))

    if not isinstance(receipt, dict):
        checks.append(_fail("independent_receipt", "independent verifier receipt is missing"))
    else:
        expected = {
            "campaign_id": campaign_id,
            "release_commit": release.get("commit_sha"),
            "decision": "PASS",
        }
        for key, value in expected.items():
            if receipt.get(key) != value:
                checks.append(_fail(f"receipt.{key}", f"expected {value!r}, got {receipt.get(key)!r}"))
            else:
                checks.append(_pass(f"receipt.{key}"))
        verifier_id = receipt.get("verifier_id")
        producer_ids = set(bundle.get("producer_ids", []))
        if not verifier_id:
            checks.append(_fail("receipt.verifier_id", "verifier identity is required"))
        elif verifier_id in producer_ids:
            checks.append(_fail("receipt.independence", "verifier must be distinct from producer identities"))
        else:
            checks.append(_pass("receipt.independence"))
        if not receipt.get("receipt_id") or not receipt.get("evidence_sha256"):
            checks.append(_fail("receipt.integrity", "receipt_id and evidence_sha256 are required"))
        else:
            checks.append(_pass("receipt.integrity"))

    rollback_required = [
        ("baseline_sha", "rollback baseline SHA is required"),
        ("rollback_tested", "rollback must be explicitly tested"),
        ("pre_rollback_readback_sha", "pre-rollback readback SHA is required"),
        ("post_rollback_readback_sha", "post-rollback readback SHA is required"),
        ("post_rollback_matches_baseline", "post-rollback readback must match baseline"),
    ]
    for key, reason in rollback_required:
        if not rollback.get(key):
            checks.append(_fail(f"rollback.{key}", reason))
        else:
            checks.append(_pass(f"rollback.{key}"))

    failed = [c for c in checks if c["status"] == "FAIL"]
    return ("CERTIFIED" if not failed else "NOT_CERTIFIED", checks)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="JSON evidence bundle")
    parser.add_argument("--report", type=Path, help="optional JSON report path")
    args = parser.parse_args()

    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"NOT_CERTIFIED: unable to read evidence bundle: {exc}", file=sys.stderr)
        return 2

    decision, checks = verify(bundle)
    report = {
        "decision": decision,
        "campaign_id": bundle.get("campaign_id"),
        "release_commit": bundle.get("release", {}).get("commit_sha"),
        "checks": checks,
    }
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if decision == "CERTIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
