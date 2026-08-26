"""Negative-control and lifecycle tests for PentaCompliance/PentaLicense."""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.penta_compliance_license import (  # noqa: E402
    PentaComplianceLicenseError,
    append_license_event,
    digest,
    evaluate_compliance,
    evaluate_license_request,
    issue_license_grant,
    public_verification,
    verify_receipt,
)


FIXED_NOW = datetime(2026, 8, 26, 20, 0, tzinfo=timezone.utc)


def obligation() -> dict:
    return {
        "obligation_id": "ct.internal.license-exactness-v1",
        "title": "License exactness control",
        "source_ref": "support/master-licensing-and-rights-architecture.mdx",
        "source_sha256": digest("support/master-licensing-and-rights-architecture.mdx"),
        "jurisdictions": ["internal"],
        "scopes": ["licensing"],
        "owner_ref": "role:rights-steward",
        "status": "active",
        "effective_from": "2026-08-26",
        "effective_to": None,
        "evidence_requirements": ["rights-profile", "terms"],
        "controls": [
            {"control_id": "rights-profile", "requirement": "Exact rights profile exists."},
            {"control_id": "terms", "requirement": "Adopted terms exist."},
        ],
    }


def compliance_pass() -> dict:
    return evaluate_compliance(
        [obligation()], jurisdictions=["internal"], scopes=["licensing"],
        evidence_index={"rights-profile": ["evidence:rights:1"], "terms": ["evidence:terms:1"]},
        as_of=date(2026, 8, 26),
    )


def asset() -> dict:
    return {
        "asset_id": "asset:course-001", "version": "1.0.0", "content_sha256": "b" * 64,
        "title": "Course One", "owner_ref": "CrownThrive LLC", "status": "active",
        "rights_control_refs": ["chlom:rights:course-001:v1"],
        "allowed_rights": ["display", "stream"], "prohibited_rights": ["sublicense"],
        "territories": ["US", "CA"], "media": ["web", "mobile"],
    }


def request() -> dict:
    return {
        "request_id": "request:001", "asset_id": "asset:course-001", "asset_version": "1.0.0",
        "asset_sha256": "b" * 64, "licensee_ref": "party:customer-001",
        "requested_rights": ["display"], "territories": ["US"], "media": ["web"],
        "use_case": "individual course access", "lane": "self_serve", "risk_class": "D1",
        "valid_from": "2026-08-26", "valid_until": "2027-08-26",
        "template_ref": "template:course-license:v1", "acceptance_ref": "acceptance:checkout:001",
        "commercial_terms_ref": "terms:course-standard:v1",
        "authority_trace": {"chlom_ref": "chlom:rights:course-001:v1", "accountable_owner": "role:rights-steward"},
        "human_gate": {"required": False, "satisfied": False, "approver_refs": []},
        "compliance_receipt": compliance_pass(), "provider_effect": False,
        "provider_binding_ref": None, "readback_strategy": None, "idempotency_key": "license:course-001:customer-001",
    }


def approved_gate() -> dict:
    return {"required": True, "satisfied": True, "approver_refs": ["human:founder:1"]}


def test_compliance_missing_evidence_holds() -> None:
    result = evaluate_compliance(
        [obligation()], jurisdictions=["internal"], scopes=["licensing"],
        evidence_index={"rights-profile": ["evidence:rights:1"]}, as_of=date(2026, 8, 26),
    )
    assert result["disposition"] == "HOLD_EVIDENCE_GAP"
    assert result["missing_evidence"] == [{"obligation_id": "ct.internal.license-exactness-v1", "control_id": "terms"}]
    assert verify_receipt(result)


def test_invalid_obligation_source_holds_entire_evaluation() -> None:
    broken = obligation()
    broken["source_sha256"] = "not-a-hash"
    result = evaluate_compliance(
        [broken], jurisdictions=["internal"], scopes=["licensing"], evidence_index={}, as_of=date(2026, 8, 26),
    )
    assert result["disposition"] == "HOLD_SOURCE_INVALID"


def test_exact_self_serve_request_is_internal_issue_ready() -> None:
    result = evaluate_license_request(asset(), request())
    assert result["disposition"] == "ISSUE_READY_INTERNAL"
    assert result["binding_action_performed"] is False
    assert verify_receipt(result)


def test_request_cannot_exceed_or_sublicense_rights() -> None:
    packet = request()
    packet["requested_rights"] = ["display", "sublicense", "broadcast"]
    result = evaluate_license_request(asset(), packet)
    assert result["disposition"] == "HOLD_FAIL_CLOSED"
    assert any("exceed" in reason for reason in result["reasons"])
    assert any("prohibited" in reason for reason in result["reasons"])


def test_asset_version_hash_mismatch_holds() -> None:
    packet = request()
    packet["asset_sha256"] = "c" * 64
    result = evaluate_license_request(asset(), packet)
    assert result["disposition"] == "HOLD_FAIL_CLOSED"
    assert any("exact registered asset" in reason for reason in result["reasons"])


def test_forged_compliance_receipt_holds() -> None:
    packet = request()
    packet["compliance_receipt"]["disposition"] = "PASS_EVIDENCE_SATISFIED"
    packet["compliance_receipt"]["missing_evidence"] = [{"control_id": "hidden"}]
    result = evaluate_license_request(asset(), packet)
    assert result["disposition"] == "HOLD_FAIL_CLOSED"
    assert any("PentaCompliance" in reason for reason in result["reasons"])


def test_d3_request_routes_to_human_review() -> None:
    packet = request()
    packet["risk_class"] = "D3"
    packet["lane"] = "reviewed"
    packet["human_gate"] = {"required": True, "satisfied": False, "approver_refs": []}
    result = evaluate_license_request(asset(), packet)
    assert result["disposition"] == "HUMAN_REVIEW_REQUIRED"


def test_d3_request_with_human_evidence_can_be_issue_ready() -> None:
    packet = request()
    packet["risk_class"] = "D3"
    packet["lane"] = "reviewed"
    packet["human_gate"] = approved_gate()
    result = evaluate_license_request(asset(), packet)
    assert result["disposition"] == "ISSUE_READY_INTERNAL"


def test_provider_issuance_requires_binding_and_readback() -> None:
    packet = request()
    packet["provider_effect"] = True
    result = evaluate_license_request(asset(), packet)
    assert result["disposition"] == "HOLD_FAIL_CLOSED"
    packet["provider_binding_ref"] = "binding:license-provider:v1"
    packet["readback_strategy"] = "read exact provider grant id and immutable document hash"
    assert evaluate_license_request(asset(), packet)["disposition"] == "ISSUE_READY_PROVIDER"


def test_issuance_is_deterministic_and_decision_bound() -> None:
    packet = request()
    decision = evaluate_license_request(asset(), packet)
    first = issue_license_grant(asset(), packet, decision, now=FIXED_NOW)
    second = issue_license_grant(copy.deepcopy(asset()), copy.deepcopy(packet), copy.deepcopy(decision), now=FIXED_NOW)
    assert first == second
    assert verify_receipt(first)
    changed = copy.deepcopy(packet)
    changed["licensee_ref"] = "party:another"
    try:
        issue_license_grant(asset(), changed, decision, now=FIXED_NOW)
    except PentaComplianceLicenseError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("expected decision-binding failure")


def test_signed_grant_is_append_only_for_revocation() -> None:
    packet = request()
    decision = evaluate_license_request(asset(), packet)
    grant = issue_license_grant(asset(), packet, decision, now=FIXED_NOW)
    original = copy.deepcopy(grant)
    event = append_license_event(
        grant, action="revoke", expected_grant_sha256=grant["receipt_sha256"],
        authority_trace={"chlom_ref": "chlom:rights:course-001:v1", "accountable_owner": "role:rights-steward"},
        human_gate=approved_gate(), evidence_refs=["evidence:revocation:001"], now=FIXED_NOW,
    )
    assert grant == original
    assert event["mutates_original_grant"] is False
    public = public_verification(grant, [event])
    assert public["status"] == "revoked"
    assert "licensee_ref" not in public


def test_event_rejects_stale_grant_hash() -> None:
    packet = request()
    decision = evaluate_license_request(asset(), packet)
    grant = issue_license_grant(asset(), packet, decision, now=FIXED_NOW)
    try:
        append_license_event(
            grant, action="suspend", expected_grant_sha256="0" * 64,
            authority_trace={"chlom_ref": "chlom:rights:course-001:v1", "accountable_owner": "role:rights-steward"},
            human_gate=approved_gate(), evidence_refs=["evidence:suspend:1"], now=FIXED_NOW,
        )
    except PentaComplianceLicenseError as exc:
        assert "exact immutable grant" in str(exc)
    else:
        raise AssertionError("expected stale-hash failure")
