#!/usr/bin/env python3
"""Deterministic candidate compiler for the governed Framework Factory."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


class CompileError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def compile_candidate(source: dict[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "candidate_id", "candidate_type", "state", "source_ids", "invariants"}
    missing = sorted(required - source.keys())
    if missing:
        raise CompileError("missing required fields: " + ", ".join(missing))
    if source["state"] != "CANDIDATE_HOLD":
        raise CompileError("compiler accepts only CANDIDATE_HOLD inputs")
    if source["candidate_type"] not in {"framework", "capability_pack", "policy_pack", "pallet"}:
        raise CompileError("unsupported candidate type")
    if not source["source_ids"] or len(source["source_ids"]) != len(set(source["source_ids"])):
        raise CompileError("source_ids must be non-empty and unique")
    if not source["invariants"] or len(source["invariants"]) != len(set(source["invariants"])):
        raise CompileError("invariants must be non-empty and unique")
    forbidden_true = [
        key
        for key in ("activation_allowed", "public_claim_allowed", "commercialization_allowed", "checkout_enabled", "can_vote")
        if source.get(key) is True
    ]
    if forbidden_true:
        raise CompileError("controlled compiler refuses enabled consequential flags: " + ", ".join(forbidden_true))
    if source.get("authority_ceiling") == "D3":
        raise CompileError("D3 is human-reserved")
    if source.get("framework_count_delta", 0) not in {0, 1}:
        raise CompileError("framework_count_delta must be 0 or 1")
    if source["candidate_type"] != "framework" and source.get("framework_count_delta", 0) != 0:
        raise CompileError("non-framework package cannot increase framework count")

    tests = [
        {"test_id": "source_ids_present", "passed": bool(source["source_ids"])},
        {"test_id": "source_ids_unique", "passed": len(source["source_ids"]) == len(set(source["source_ids"]))},
        {"test_id": "invariants_present", "passed": bool(source["invariants"])},
        {"test_id": "no_D3", "passed": source.get("authority_ceiling") != "D3"},
        {"test_id": "no_self_activation", "passed": source.get("activation_allowed") is not True},
        {"test_id": "no_machine_vote", "passed": source.get("can_vote") is not True},
        {"test_id": "commercial_hold", "passed": source.get("commercialization_allowed") is not True},
        {"test_id": "no_checkout", "passed": source.get("checkout_enabled") is not True},
    ]
    source_digest = sha256(source)
    compiled = {
        "compiler_contract_version": "1.0.0",
        "compiled_candidate_id": source["candidate_id"],
        "compiled_from_sha256": source_digest,
        "candidate_type": source["candidate_type"],
        "release_state": "COMPILED_TEST_HOLD",
        "factory_integration": {
            "integration_state": "PENDING_PARENT_CERTIFICATION",
            "framework_count_delta": source.get("framework_count_delta", 0),
            "existing_eight_framework_factory_unchanged": source.get("framework_count_delta", 0) == 0,
            "parent_certifier": "ct.relay.agent-d",
        },
        "source_ids": sorted(source["source_ids"]),
        "invariants": sorted(source["invariants"]),
        "test_results": tests,
        "test_status": "PASS" if all(row["passed"] for row in tests) else "FAIL",
        "controls": {
            "can_vote": False,
            "d3_human_reserved": True,
            "no_self_approval": True,
            "activation_allowed": False,
            "public_claim_allowed": False,
            "commercialization_allowed": False,
            "delete_allowed": False,
        },
        "not_proven": ["runtime behavior", "governance approval", "publication", "commercial readiness"],
    }
    compiled["compiled_manifest_sha256"] = sha256(compiled)
    return compiled


def self_test() -> dict[str, Any]:
    valid = {
        "schema_version": "1.0.0",
        "candidate_id": "ct.framework-candidate.self-test.v1",
        "candidate_type": "capability_pack",
        "state": "CANDIDATE_HOLD",
        "source_ids": ["SELF-TEST-SOURCE"],
        "invariants": ["no_self_activation"],
        "framework_count_delta": 0,
        "activation_allowed": False,
        "commercialization_allowed": False,
    }
    first = compile_candidate(valid)
    second = compile_candidate(valid)
    if canonical_bytes(first) != canonical_bytes(second):
        raise CompileError("compiler is not deterministic")
    rejected = False
    invalid = dict(valid, activation_allowed=True)
    try:
        compile_candidate(invalid)
    except CompileError:
        rejected = True
    if not rejected:
        raise CompileError("self-activation test was not rejected")
    return {"status": "PASS", "deterministic": True, "self_activation_rejected": True, "output_sha256": sha256(first)}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--compile", type=Path)
    group.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.self_test:
            value = self_test()
        else:
            source = json.loads(args.compile.read_text(encoding="utf-8"))
            value = compile_candidate(source)
        payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
        if args.output:
            if args.output.exists():
                raise CompileError(f"refusing to overwrite prior compiled evidence: {args.output}")
            args.output.write_text(payload, encoding="utf-8")
        print(payload, end="")
    except (OSError, json.JSONDecodeError, CompileError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
