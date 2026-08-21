#!/usr/bin/env python3
"""Deterministic candidate compiler for the governed Framework Factory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


class CompileError(ValueError):
    pass


CONSEQUENTIAL_FLAGS = (
    "activation_allowed",
    "public_claim_allowed",
    "commercialization_allowed",
    "checkout_enabled",
    "can_vote",
    "delete_allowed",
)

CANDIDATE_ID_RE = re.compile(r"^ct\.[a-z0-9.-]+\.v[0-9]+$")
ALLOWED_CANDIDATE_FIELDS = {
    "schema_version",
    "candidate_id",
    "candidate_type",
    "state",
    "source_ids",
    "public_sources",
    "invariants",
    "known_drift",
    "required_tests",
    "authority_ceiling",
    "framework_count_delta",
    *CONSEQUENTIAL_FLAGS,
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require_unique_strings(source: dict[str, Any], key: str) -> list[str]:
    value = source.get(key)
    if not isinstance(value, list) or not value:
        raise CompileError(f"{key} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise CompileError(f"{key} entries must be non-empty strings")
    if len(value) != len(set(value)):
        raise CompileError(f"{key} entries must be unique")
    return value


def compile_candidate(source: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise CompileError("candidate must be a JSON object")
    required = {
        "schema_version",
        "candidate_id",
        "candidate_type",
        "state",
        "source_ids",
        "invariants",
        "authority_ceiling",
        "framework_count_delta",
        *CONSEQUENTIAL_FLAGS,
    }
    missing = sorted(required - source.keys())
    if missing:
        raise CompileError("missing required fields: " + ", ".join(missing))
    unexpected = sorted(source.keys() - ALLOWED_CANDIDATE_FIELDS)
    if unexpected:
        raise CompileError("unsupported candidate fields: " + ", ".join(unexpected))
    if source["schema_version"] != "1.0.0":
        raise CompileError("schema_version must be 1.0.0")
    if not isinstance(source["candidate_id"], str) or not CANDIDATE_ID_RE.fullmatch(source["candidate_id"]):
        raise CompileError("candidate_id must be a versioned CrownThrive identifier")
    if source["state"] != "CANDIDATE_HOLD":
        raise CompileError("compiler accepts only CANDIDATE_HOLD inputs")
    if not isinstance(source["candidate_type"], str) or source["candidate_type"] not in {
        "framework",
        "capability_pack",
        "policy_pack",
        "pallet",
    }:
        raise CompileError("unsupported candidate type")
    source_ids = require_unique_strings(source, "source_ids")
    invariants = require_unique_strings(source, "invariants")
    for optional_string_set in ("public_sources", "required_tests"):
        if optional_string_set in source:
            require_unique_strings(source, optional_string_set)
    if "known_drift" in source and not isinstance(source["known_drift"], list):
        raise CompileError("known_drift must be an array")
    invalid_flag_types = [
        key for key in CONSEQUENTIAL_FLAGS if key in source and type(source[key]) is not bool
    ]
    if invalid_flag_types:
        raise CompileError(
            "consequential flags must be JSON booleans: " + ", ".join(invalid_flag_types)
        )
    forbidden_true = [key for key in CONSEQUENTIAL_FLAGS if source.get(key, False)]
    if forbidden_true:
        raise CompileError("controlled compiler refuses enabled consequential flags: " + ", ".join(forbidden_true))
    authority_ceiling = source.get("authority_ceiling")
    if authority_ceiling not in {"D0", "D1", "D2"}:
        raise CompileError("authority_ceiling must be D0, D1 or D2")
    framework_count_delta = source.get("framework_count_delta", 0)
    if type(framework_count_delta) is not int or framework_count_delta not in {0, 1}:
        raise CompileError("framework_count_delta must be 0 or 1")
    if source["candidate_type"] != "framework" and framework_count_delta != 0:
        raise CompileError("non-framework package cannot increase framework count")

    tests = [
        {"test_id": "source_ids_present", "passed": bool(source_ids)},
        {"test_id": "source_ids_unique", "passed": len(source_ids) == len(set(source_ids))},
        {"test_id": "invariants_present", "passed": bool(invariants)},
        {"test_id": "authority_bounded_D0_D2", "passed": authority_ceiling in {"D0", "D1", "D2"}},
        {"test_id": "no_self_activation", "passed": source.get("activation_allowed", False) is False},
        {"test_id": "no_machine_vote", "passed": source.get("can_vote", False) is False},
        {"test_id": "commercial_hold", "passed": source.get("commercialization_allowed", False) is False},
        {"test_id": "no_checkout", "passed": source.get("checkout_enabled", False) is False},
    ]
    source_digest = sha256(source)
    compiled = {
        "compiler_contract_version": "1.0.1",
        "compiled_candidate_id": source["candidate_id"],
        "compiled_from_sha256": source_digest,
        "candidate_type": source["candidate_type"],
        "release_state": "COMPILED_TEST_HOLD",
        "factory_integration": {
            "integration_state": "PENDING_PARENT_CERTIFICATION",
            "framework_count_delta": framework_count_delta,
            "existing_eight_framework_factory_unchanged": framework_count_delta == 0,
            "parent_certifier": "ct.relay.agent-d",
        },
        "source_ids": sorted(source_ids),
        "invariants": sorted(invariants),
        "test_results": tests,
        "test_status": (
            "SELF_TEST_PASS_PENDING_INDEPENDENT_VERIFICATION"
            if all(row["passed"] for row in tests)
            else "FAIL"
        ),
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
        "authority_ceiling": "D1",
        "activation_allowed": False,
        "public_claim_allowed": False,
        "commercialization_allowed": False,
        "checkout_enabled": False,
        "can_vote": False,
        "delete_allowed": False,
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
    non_boolean_rejected = False
    try:
        compile_candidate(dict(valid, activation_allowed="false"))
    except CompileError:
        non_boolean_rejected = True
    if not non_boolean_rejected:
        raise CompileError("non-boolean consequential flag was not rejected")
    return {
        "status": "SELF_TEST_PASS_PENDING_INDEPENDENT_VERIFICATION",
        "deterministic": True,
        "self_activation_rejected": True,
        "non_boolean_flag_rejected": True,
        "output_sha256": sha256(first),
    }


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
