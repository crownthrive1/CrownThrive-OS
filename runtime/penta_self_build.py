"""Governed self-build contract for every registered Penta Family member.

The runtime turns a capability gap into a bounded PentaFactory candidate and
evaluates build/test/self-certification/final-certification/release evidence.
Every originating Penta must self-certify its own exact candidate evidence before
institutional gates evaluate it. That self-certification never fabricates provider
truth and never replaces final independent certification, provider readback, DAIL,
or D3/human-reserved authority.
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
SELF_CERT_STAGES = {"build", "test", "certify", "release"}


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
        "license_provenance_ref", "security_review_ref", "builder_system",
        "self_certifier_system", "certifier_system",
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
    source_system = packet["source_system"]
    builder_system = packet.get("builder_system")
    self_certifier_system = packet.get("self_certifier_system")
    final_certifier_system = packet.get("certifier_system")

    if source_system not in registered_members:
        reasons.append("source_system is not a registered Penta Family member")
    if builder_system != "penta.factory":
        reasons.append("PentaFactory must own candidate construction")
    if self_certifier_system != source_system:
        reasons.append("originator self-certification must be issued by the source Penta itself")

    if packet["requested_stage"] in SELF_CERT_STAGES:
        self_ref = packet.get("self_certification_ref")
        self_sha = packet.get("self_certification_sha256")
        gate_ref = packet.get("gate_awareness_ref")
        if not isinstance(self_ref, str) or not self_ref.strip():
            reasons.append("originator self-certification evidence is required")
        if not isinstance(self_sha, str) or len(self_sha) != 64 or any(ch not in "0123456789abcdef" for ch in self_sha.lower()):
            reasons.append("originator self-certification SHA-256 is required")
        if not isinstance(gate_ref, str) or not gate_ref.strip():
            reasons.append("PR gate-awareness evidence is required")

    if packet["requested_stage"] in {"certify", "release"}:
        if final_certifier_system in {builder_system, source_system}:
            reasons.append("final institutional certification must remain independent from builder and source Penta")
        if not packet.get("independent_certification_ref"):
            reasons.append("independent final certification evidence is required")
        if not packet.get("exact_artifact_sha256") or len(str(packet.get("exact_artifact_sha256"))) != 64:
            reasons.append("exact artifact SHA-256 is required")

    expected_tests = set(packet["acceptance_tests"] + packet["negative_tests"] + packet["stress_tests"])
    reported = set(packet["test_results"])
    if packet["requested_stage"] in {"test", "certify", "release"}:
        missing = sorted(expected_tests - reported)
        failed = sorted(key for key in expected_tests if packet["test_results"].get(key) is False)
        if missing:
            reasons.append("test results missing: " + ", ".join(missing))
        if failed:
            reasons.append("tests failed: " + ", ".join(failed))

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
        "build": "SELF_CERTIFIED_BUILD_CANDIDATE_READY",
        "test": "SELF_CERTIFIED_TEST_EVIDENCE_READY",
        "certify": "FINAL_CERTIFICATION_READY",
        "release": "RELEASE_READY",
    }[packet["requested_stage"]]
    originator_self_certified = packet["requested_stage"] in SELF_CERT_STAGES and not any(
        reason.startswith("originator self-certification") or reason.startswith("PR gate-awareness")
        for reason in reasons
    ) and self_certifier_system == source_system
    result = {
        "schema": "ct.penta.self-build-decision.v2",
        "candidate_id": packet["candidate_id"],
        "source_system": source_system,
        "requested_stage": packet["requested_stage"],
        "disposition": "HOLD_FAIL_CLOSED" if reasons else stage_ready,
        "reasons": reasons,
        "originator_self_certified": originator_self_certified,
        "originator_may_submit_own_evidence": True,
        "originator_may_write_own_evidence_blobs": True,
        "final_independent_certification_required": packet["requested_stage"] in {"certify", "release"},
        "provider_truth_manufactured": False,
        "code_written": False,
        "production_promoted": False,
        "authority_manufactured": False,
    }
    result["receipt_sha256"] = _digest(result)
    return result


def coverage_report(root: Path) -> dict[str, Any]:
    registry, snapshot = load_family(root)
    family_contract = registry.get("self_build_contract")
    if not isinstance(family_contract, dict):
        raise PentaSelfBuildError("family self_build_contract is missing")
    required_true = (
        "applies_to_all_registered_members", "typed_gap_required", "penta_factory_builder_required",
        "independent_certification_required", "negative_and_stress_tests_required",
        "rollback_required", "authority_never_manufactured", "d3_human_reserved",
    )
    missing_flags = [key for key in required_true if family_contract.get(key) is not True]
    if missing_flags:
        raise PentaSelfBuildError("self-build invariants missing: " + ", ".join(missing_flags))

    contract_path = root / str(family_contract.get("contract_path") or "")
    if not contract_path.exists():
        raise PentaSelfBuildError("self-build production contract is missing")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    required_gates = contract.get("required_gates") or {}
    new_required = (
        "originator_self_certification_required",
        "originator_evidence_blob_required",
        "gate_awareness_required",
        "independent_final_certification_required",
        "dail_binding_required_before_institutional_pass",
    )
    missing_new = [key for key in new_required if required_gates.get(key) is not True]
    if missing_new:
        raise PentaSelfBuildError("self-build self-certification invariants missing: " + ", ".join(missing_new))

    members = sorted(snapshot["members"])
    result = {
        "schema": "ct.penta.self-build-coverage.v2",
        "disposition": "PASS",
        "member_count": len(members),
        "covered_member_count": len(members),
        "members": members,
        "candidate_schema_path": family_contract.get("candidate_schema_path"),
        "runtime_path": family_contract.get("runtime_path"),
        "originator_self_certification_required": True,
        "independent_final_certification_required": True,
        "gate_awareness_required": True,
        "truth_rule": "every Penta self-certifies its own exact candidate evidence; final institutional PASS still requires required provider gates, readback and DAIL",
    }
    result["receipt_sha256"] = _digest(result)
    return result


if __name__ == "__main__":
    print(json.dumps(coverage_report(Path(__file__).resolve().parents[1]), sort_keys=True))
