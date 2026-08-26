"""Regression tests for the Penta Family institutional-controls runtime."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.penta_institutional_controls import (  # noqa: E402
    EXECUTION_ELIGIBLE,
    KNOWN_SYSTEMS,
    InstitutionalControlError,
    build_control_request,
    evaluate_control_request,
    receipt_sha256,
    validate_control_request,
)

EXPECTED = {"penta.compliance", "penta.privacy", "penta.identity", "penta.data", "penta.records", "penta.procure", "penta.vendor", "penta.contracts", "penta.license", "penta.quality"}


def expect_error(fn, contains: str) -> None:
    try:
        fn()
    except InstitutionalControlError as exc:
        assert contains in str(exc), (contains, str(exc))
    else:
        raise AssertionError(f"expected InstitutionalControlError containing {contains!r}")


def approved_gate(*, separation: bool = False) -> dict:
    return {"required": True, "satisfied": True, "approver_refs": ["human:approver:1"], "separation_of_duties": separation}


def authority() -> dict:
    return {"chlom_ref": "chlom:authority:1", "dail_ref": None, "accountable_owner": "role:owner"}


def test_all_ten_systems_registered_in_runtime() -> None:
    assert KNOWN_SYSTEMS == EXPECTED
    assert EXECUTION_ELIGIBLE == {"certified", "production"}


def test_advisory_analysis_is_ready_at_implemented_maturity() -> None:
    packet = build_control_request(system="penta.data", action="classify_dataset", requested_effect="analyze", evidence_refs=["evidence:catalog:1"], member_maturity="implemented")
    result = evaluate_control_request(packet)
    assert result["disposition"] == "advisory_ready"
    assert len(result["receipt_sha256"]) == 64


def test_implemented_member_cannot_execute_even_with_other_gates() -> None:
    packet = build_control_request(
        system="penta.identity", action="grant_role", requested_effect="execute", evidence_refs=["evidence:access-request:1"],
        member_maturity="implemented", authority_trace=authority(), human_gate=approved_gate(separation=True), provider_effect=True,
        provider_binding_ref="provider-binding:iam:1", readback_strategy="read effective role membership",
    )
    result = evaluate_control_request(packet)
    assert result["disposition"] == "governance_required"
    assert any("certified/production maturity" in reason for reason in result["reasons"])


def test_certified_identity_execution_requires_separation_of_duties() -> None:
    packet = build_control_request(
        system="penta.identity", action="grant_role", requested_effect="execute", evidence_refs=["evidence:access-request:2"],
        member_maturity="certified", authority_trace=authority(), human_gate=approved_gate(separation=False), provider_effect=True,
        provider_binding_ref="provider-binding:iam:1", readback_strategy="read effective role membership",
    )
    result = evaluate_control_request(packet)
    assert result["disposition"] == "governance_required"
    assert "separation-of-duties evidence is required" in result["reasons"]


def test_certified_identity_execution_can_become_execution_ready() -> None:
    packet = build_control_request(
        system="penta.identity", action="grant_role", requested_effect="execute", evidence_refs=["evidence:access-request:3", "evidence:sod:1"],
        member_maturity="certified", authority_trace=authority(), human_gate=approved_gate(separation=True), provider_effect=True,
        provider_binding_ref="provider-binding:iam:1", readback_strategy="read effective role membership and audit event",
    )
    assert evaluate_control_request(packet)["disposition"] == "execution_ready"


def test_forbidden_privacy_consent_manufacture_holds() -> None:
    packet = build_control_request(system="penta.privacy", action="fabricate_consent", requested_effect="prepare", evidence_refs=["evidence:privacy-request:1"])
    result = evaluate_control_request(packet)
    assert result["disposition"] == "hold_fail_closed"
    assert "Consent cannot be manufactured." in result["reasons"]


def test_record_under_hold_cannot_be_disposed() -> None:
    packet = build_control_request(
        system="penta.records", action="dispose_record", requested_effect="execute", evidence_refs=["evidence:records:1"], member_maturity="production",
        authority_trace=authority(), human_gate=approved_gate(), provider_effect=True, provider_binding_ref="provider-binding:records:1",
        readback_strategy="verify disposition receipt", metadata={"active_hold": True, "retention_authority_ref": "records-schedule:1", "hold_clearance": False},
    )
    result = evaluate_control_request(packet)
    assert result["disposition"] == "hold_fail_closed"
    assert any("active hold" in reason for reason in result["reasons"])


def test_contract_signature_requires_legal_and_signatory_evidence() -> None:
    packet = build_control_request(
        system="penta.contracts", action="sign_contract", requested_effect="execute", evidence_refs=["evidence:contract:1"], member_maturity="certified",
        authority_trace=authority(), human_gate=approved_gate(), provider_effect=True, provider_binding_ref="provider-binding:esign:1",
        readback_strategy="verify signed envelope and exact executed hash",
    )
    result = evaluate_control_request(packet)
    assert result["disposition"] == "governance_required"
    assert any("PentaLegal/counsel" in reason for reason in result["reasons"])
    assert any("signatory" in reason for reason in result["reasons"])


def test_contract_signature_can_become_execution_ready_with_full_evidence() -> None:
    packet = build_control_request(
        system="penta.contracts", action="sign_contract", requested_effect="execute", evidence_refs=["evidence:contract:2", "evidence:legal:2", "evidence:signatory:2"],
        member_maturity="production", authority_trace=authority(), human_gate=approved_gate(), provider_effect=True,
        provider_binding_ref="provider-binding:esign:2", readback_strategy="verify signed envelope and exact executed hash",
        metadata={"legal_review_ref": "penta-legal:review:2", "signatory_authority_ref": "chlom:signatory:2"},
    )
    assert evaluate_control_request(packet)["disposition"] == "execution_ready"


def test_procurement_commitment_requires_spend_and_terms() -> None:
    packet = build_control_request(
        system="penta.procure", action="place_order", requested_effect="execute", evidence_refs=["evidence:requisition:1"], member_maturity="certified",
        authority_trace=authority(), human_gate=approved_gate(), provider_effect=True, provider_binding_ref="provider-binding:procurement:1",
        readback_strategy="verify order and receipt identifiers",
    )
    result = evaluate_control_request(packet)
    assert result["disposition"] == "governance_required"
    assert any("spend authority" in reason for reason in result["reasons"])
    assert any("contract/terms" in reason for reason in result["reasons"])


def test_quality_cannot_lower_criteria_after_failure() -> None:
    packet = build_control_request(system="penta.quality", action="change_acceptance_criteria", requested_effect="prepare", evidence_refs=["evidence:test-failure:1"], metadata={"after_failure": True})
    result = evaluate_control_request(packet)
    assert result["disposition"] == "hold_fail_closed"
    assert any("manufacture a pass" in reason for reason in result["reasons"])


def test_quality_closure_requires_independent_retest() -> None:
    packet = build_control_request(
        system="penta.quality", action="close_nonconformance", requested_effect="execute", evidence_refs=["evidence:ncr:1"], member_maturity="certified",
        authority_trace=authority(), human_gate=approved_gate(separation=True), readback_strategy="confirm NCR closure and quality ledger state",
    )
    result = evaluate_control_request(packet)
    assert result["disposition"] == "governance_required"
    assert any("re-test/effectiveness" in reason for reason in result["reasons"])


def test_compliance_attestation_requires_source_and_evidence_review() -> None:
    packet = build_control_request(
        system="penta.compliance", action="submit_attestation", requested_effect="execute", evidence_refs=["evidence:controls:1"], member_maturity="certified",
        authority_trace=authority(), human_gate=approved_gate(separation=True), readback_strategy="verify attestation receipt and stored evidence hash",
    )
    result = evaluate_control_request(packet)
    assert result["disposition"] == "governance_required"
    assert any("obligation source" in reason for reason in result["reasons"])
    assert any("evidence-sufficiency" in reason for reason in result["reasons"])


def test_license_issuance_requires_exact_rights_terms_and_acceptance() -> None:
    packet = build_control_request(
        system="penta.license", action="issue_license", requested_effect="execute",
        evidence_refs=["evidence:license-request:1"], member_maturity="production",
        authority_trace=authority(), human_gate=approved_gate(separation=True), provider_effect=True,
        provider_binding_ref="provider-binding:license:1", readback_strategy="read exact provider grant and document hash",
    )
    result = evaluate_control_request(packet)
    assert result["disposition"] == "governance_required"
    assert any("rights-control profile" in reason for reason in result["reasons"])
    assert any("asset/version/hash" in reason for reason in result["reasons"])
    assert any("adopted terms" in reason for reason in result["reasons"])
    assert any("acceptance" in reason for reason in result["reasons"])


def test_license_issuance_can_be_ready_only_with_all_gates() -> None:
    packet = build_control_request(
        system="penta.license", action="issue_license", requested_effect="execute",
        evidence_refs=["evidence:license-request:2", "evidence:rights:2", "evidence:terms:2"], member_maturity="production",
        authority_trace=authority(), human_gate=approved_gate(separation=True), provider_effect=True,
        provider_binding_ref="provider-binding:license:2", readback_strategy="read exact provider grant and document hash",
        metadata={
            "rights_profile_ref": "chlom:rights:2", "asset_version_ref": "asset:2@sha256:abc",
            "terms_ref": "terms:license:2", "acceptance_ref": "acceptance:2",
        },
    )
    assert evaluate_control_request(packet)["disposition"] == "execution_ready"


def test_license_cannot_manufacture_rights() -> None:
    packet = build_control_request(
        system="penta.license", action="fabricate_rights", requested_effect="prepare",
        evidence_refs=["evidence:request:forbidden"], member_maturity="production",
    )
    assert evaluate_control_request(packet)["disposition"] == "hold_fail_closed"


def test_request_validation_rejects_unknown_system() -> None:
    packet = build_control_request(system="penta.data", action="classify_dataset", requested_effect="analyze", evidence_refs=["evidence:1"])
    broken = copy.deepcopy(packet)
    broken["system"] = "penta.unknown"
    broken.pop("request_sha256", None)
    expect_error(lambda: validate_control_request(broken), "unknown system")


def test_receipt_hash_is_deterministic() -> None:
    payload = {"b": 2, "a": [1, 3]}
    assert receipt_sha256(payload) == receipt_sha256(copy.deepcopy(payload))
    assert len(receipt_sha256(payload)) == 64


def run() -> None:
    tests = [obj for name, obj in sorted(globals().items()) if name.startswith("test_") and callable(obj)]
    for test in tests:
        test()
    print(f"PASS: {len(tests)} Penta institutional-control tests")


if __name__ == "__main__":
    run()
