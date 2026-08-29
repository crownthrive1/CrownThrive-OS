"""Governed self-build coverage, originator self-certification and fail-closed promotion tests."""

from __future__ import annotations

import copy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.penta_family import load_family  # noqa: E402
from runtime.penta_self_build import coverage_report, evaluate_candidate  # noqa: E402


def members() -> dict:
    return load_family(ROOT)[1]["members"]


def candidate(stage: str = "build") -> dict:
    tests = ["acceptance:contract", "negative:authority", "stress:determinism"]
    return {
        "candidate_id": "candidate:penta-license:001",
        "source_system": "penta.license",
        "gap_id": "gap:license-lifecycle-runtime",
        "gap_statement": "Add bounded license lifecycle software.",
        "requested_stage": stage,
        "risk_class": "D2",
        "exact_source_ref": "git:head:example",
        "idempotency_key": "self-build:penta-license:001",
        "requirements": ["immutable grants", "fail-closed rights checks"],
        "acceptance_tests": [tests[0]],
        "negative_tests": [tests[1]],
        "stress_tests": [tests[2]],
        "test_results": {test: True for test in tests},
        "rollback_plan": "Revert exact release commit and preserve evidence.",
        "license_provenance_ref": "chlom:source-license:v1",
        "security_review_ref": "penta-security:review:001",
        "evidence_refs": ["evidence:requirements:001"],
        "builder_system": "penta.factory",
        "self_certifier_system": "penta.license",
        "self_certification_ref": "penta-self-cert:penta-license:001",
        "self_certification_sha256": "c" * 64,
        "gate_awareness_ref": "penta-pr-gate:001",
        "certifier_system": "penta.certify",
        "independent_certification_ref": "penta-certify:receipt:001",
        "exact_artifact_sha256": "d" * 64,
        "exact_head_sha": "e" * 40,
        "authority_trace": {"chlom_ref": "chlom:build-authority:001", "accountable_owner": "role:release-owner"},
        "human_gate": {"required": False, "satisfied": False, "approver_refs": []},
        "provider_effect": False,
        "provider_binding_ref": None,
        "readback_strategy": None,
    }


def test_every_registered_member_has_self_build_and_self_cert_coverage() -> None:
    report = coverage_report(ROOT)
    assert report["disposition"] == "PASS"
    assert report["member_count"] == report["covered_member_count"]
    assert report["originator_self_certification_required"] is True
    assert report["independent_final_certification_required"] is True
    assert report["gate_awareness_required"] is True
    assert "penta.compliance" in report["members"]
    assert "penta.license" in report["members"]


def test_build_candidate_is_self_certified_without_claiming_final_promotion() -> None:
    result = evaluate_candidate(candidate("build"), registered_members=members())
    assert result["disposition"] == "SELF_CERTIFIED_BUILD_CANDIDATE_READY"
    assert result["originator_self_certified"] is True
    assert result["originator_may_submit_own_evidence"] is True
    assert result["originator_may_write_own_evidence_blobs"] is True
    assert result["code_written"] is False
    assert result["production_promoted"] is False
    assert result["authority_manufactured"] is False


def test_unknown_penta_cannot_request_factory_work() -> None:
    packet = candidate()
    packet["source_system"] = "penta.unknown"
    packet["self_certifier_system"] = "penta.unknown"
    result = evaluate_candidate(packet, registered_members=members())
    assert result["disposition"] == "HOLD_FAIL_CLOSED"
    assert any("registered" in reason for reason in result["reasons"])


def test_originator_must_self_certify_its_own_candidate() -> None:
    packet = candidate("build")
    packet["self_certifier_system"] = "penta.factory"
    result = evaluate_candidate(packet, registered_members=members())
    assert result["disposition"] == "HOLD_FAIL_CLOSED"
    assert any("source Penta itself" in reason for reason in result["reasons"])


def test_missing_self_certification_evidence_holds() -> None:
    packet = candidate("test")
    packet["self_certification_ref"] = None
    packet["self_certification_sha256"] = None
    packet["gate_awareness_ref"] = None
    result = evaluate_candidate(packet, registered_members=members())
    assert result["disposition"] == "HOLD_FAIL_CLOSED"
    assert any("self-certification" in reason for reason in result["reasons"])
    assert any("gate-awareness" in reason for reason in result["reasons"])


def test_originator_self_cert_does_not_replace_final_independent_certification() -> None:
    packet = candidate("certify")
    packet["certifier_system"] = "penta.license"
    result = evaluate_candidate(packet, registered_members=members())
    assert result["originator_self_certified"] is True
    assert result["disposition"] == "HOLD_FAIL_CLOSED"
    assert any("final institutional certification" in reason for reason in result["reasons"])


def test_release_fails_when_a_negative_test_fails() -> None:
    packet = candidate("release")
    packet["test_results"]["negative:authority"] = False
    result = evaluate_candidate(packet, registered_members=members())
    assert result["disposition"] == "HOLD_FAIL_CLOSED"
    assert any("tests failed" in reason for reason in result["reasons"])


def test_provider_release_requires_binding_and_readback() -> None:
    packet = candidate("release")
    packet["provider_effect"] = True
    result = evaluate_candidate(packet, registered_members=members())
    assert result["disposition"] == "HOLD_FAIL_CLOSED"
    packet["provider_binding_ref"] = "provider:github:binding:v1"
    packet["readback_strategy"] = "read exact deployed source head"
    assert evaluate_candidate(packet, registered_members=members())["disposition"] == "RELEASE_READY"


def test_d3_release_remains_human_reserved() -> None:
    packet = candidate("release")
    packet["risk_class"] = "D3"
    result = evaluate_candidate(packet, registered_members=members())
    assert result["disposition"] == "HOLD_FAIL_CLOSED"
    packet["human_gate"] = {"required": True, "satisfied": True, "approver_refs": ["human:founder:1"]}
    assert evaluate_candidate(packet, registered_members=members())["disposition"] == "RELEASE_READY"


def test_decision_is_deterministic_under_replay() -> None:
    packet = candidate("release")
    assert evaluate_candidate(packet, registered_members=members()) == evaluate_candidate(copy.deepcopy(packet), registered_members=members())
