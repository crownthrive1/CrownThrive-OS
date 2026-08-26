"""Governed self-build contract for every registered Penta Family member.

The runtime turns a capability gap into a bounded PentaFactory candidate and
evaluates build/test/certification/release evidence. It never writes code or
promotes a candidate by itself; provider writes and D3 authority remain gated.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from runtime.penta_family import load_family
except ModuleNotFoundError:  # Direct `python runtime/penta_self_build.py` execution.
    from penta_family import load_family


class PentaSelfBuildError(ValueError):
    pass


STAGES = {"specify", "build", "test", "certify", "release"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _required_string(packet: Mapping[str, Any], key: str) -> str:
    value = packet.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PentaSelfBuildError(f"{key} must be a non-empty string")
    return value.strip()


def _string_list(packet: Mapping[str, Any], key: str) -> list[str]:
    value = packet.get(key)
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
        raise PentaSelfBuildError(f"{key} must be a non-empty string list")
    if len(value) != len(set(value)):
        raise PentaSelfBuildError(f"{key} must be unique")
    return sorted(value)


def validate_candidate(packet: Mapping[str, Any]) -> None:
    for key in (
        "candidate_id", "source_system", "gap_id", "gap_statement", "requested_stage",
        "risk_class", "exact_source_ref", "idempotency_key", "rollback_plan",
        "license_provenance_ref", "security_review_ref",
    ):
        _required_string(packet, key)
    if packet["requested_stage"] not in STAGES:
        raise PentaSelfBuildError("requested_stage is invalid")
    if packet["risk_class"] not in {"D0", "D1", "D2", "D3"}:
        raise PentaSelfBuildError("risk_class must be D0-D3")
    for key in ("requirements", "acceptance_tests", "negative_tests", "stress_tests", "evidence_refs"):
        _string_list(packet, key)
    results = packet.get("test_results")
    if not isinstance(results, dict) or any(not isinstance(key, str) or not isinstance(value, bool) for key, value in results.items()):
        raise PentaSelfBuildError("test_results must map test ids to booleans")
    authority = packet.get("authority_trace")
    if not isinstance(authority, dict):
        raise PentaSelfBuildError("authority_trace must be an object")
    human = packet.get("human_gate")
    if not isinstance(human, dict):
        raise PentaSelfBuildError("human_gate must be an object")
    if not isinstance(packet.get("provider_effect"), bool):
        raise PentaSelfBuildError("provider_effect must be boolean")


def evaluate_candidate(packet: Mapping[str, Any], *, registered_members: Mapping[str, Any]) -> dict[str, Any]:
    validate_candidate(packet)
    reasons: list[str] = []
    if packet["source_system"] not in registered_members:
        reasons.append("source_system is not a registered Penta Family member")
    if packet.get("builder_system") != "penta.factory":
        reasons.append("PentaFactory must own candidate construction")
    if packet.get("certifier_system") == packet.get("builder_system") and packet["requested_stage"] in {"certify", "release"}:
        reasons.append("independent certification cannot be performed by the builder")
    expected_tests = set(packet["acceptance_tests"] + packet["negative_tests"] + packet["stress_tests"])
    reported = set(packet["test_results"])
    if packet["requested_stage"] in {"test", "certify", "release"}:
        missing = sorted(expected_tests - reported)
        failed = sorted(key for key in expected_tests if packet["test_results"].get(key) is False)
        if missing:
            reasons.append("test results missing: " + ", ".join(missing))
        if failed:
            reasons.append("tests failed: " + ", ".join(failed))
    if packet["requested_stage"] in {"certify", "release"}:
        if not packet.get("independent_certification_ref"):
            reasons.append("independent certification evidence is required")
        if not packet.get("exact_artifact_sha256") or len(str(packet.get("exact_artifact_sha256"))) != 64:
            reasons.append("exact artifact SHA-256 is required")
    human = packet["human_gate"]
    if packet["risk_class"] == "D3":
        if not (human.get("required") is True and human.get("satisfied") is True and human.get("approver_refs")):
            reasons.append("D3 remains human-reserved")
    authority = packet["authority_trace"]
    if packet["requested_stage"] == "release" and not (authority.get("chlom_ref") and authority.get("accountable_owner")):
        reasons.append("release requires adopted authority and accountable owner")
    if packet["requested_stage"] == "release" and not packet.get("exact_head_sha"):
        reasons.append("release requires an exact immutable source head")
    if packet["provider_effect"]:
        if not packet.get("provider_binding_ref"):
            reasons.append("provider release requires a certified provider binding")
        if not packet.get("readback_strategy"):
            reasons.append("provider release requires readback strategy")

    stage_ready = {
        "specify": "SPECIFICATION_READY",
        "build": "BUILD_CANDIDATE_READY",
        "test": "TEST_EVIDENCE_READY",
        "certify": "CERTIFICATION_READY",
        "release": "RELEASE_READY",
    }[packet["requested_stage"]]
    result = {
        "schema": "ct.penta.self-build-decision.v1",
        "candidate_id": packet["candidate_id"],
        "source_system": packet["source_system"],
        "requested_stage": packet["requested_stage"],
        "disposition": "HOLD_FAIL_CLOSED" if reasons else stage_ready,
        "reasons": reasons,
        "code_written": False,
        "production_promoted": False,
        "authority_manufactured": False,
    }
    result["receipt_sha256"] = _digest(result)
    return result


def coverage_report(root: Path) -> dict[str, Any]:
    registry, snapshot = load_family(root)
    contract = registry.get("self_build_contract")
    if not isinstance(contract, dict):
        raise PentaSelfBuildError("family self_build_contract is missing")
    required_true = (
        "applies_to_all_registered_members", "typed_gap_required", "penta_factory_builder_required",
        "independent_certification_required", "negative_and_stress_tests_required",
        "rollback_required", "authority_never_manufactured", "d3_human_reserved",
    )
    missing_flags = [key for key in required_true if contract.get(key) is not True]
    if missing_flags:
        raise PentaSelfBuildError("self-build invariants missing: " + ", ".join(missing_flags))
    members = sorted(snapshot["members"])
    result = {
        "schema": "ct.penta.self-build-coverage.v1",
        "disposition": "PASS",
        "member_count": len(members),
        "covered_member_count": len(members),
        "members": members,
        "candidate_schema_path": contract.get("candidate_schema_path"),
        "runtime_path": contract.get("runtime_path"),
        "truth_rule": "coverage enables governed candidate routing; it does not authorize autonomous production promotion",
    }
    result["receipt_sha256"] = _digest(result)
    return result


if __name__ == "__main__":
    print(json.dumps(coverage_report(Path(__file__).resolve().parents[1]), sort_keys=True))
