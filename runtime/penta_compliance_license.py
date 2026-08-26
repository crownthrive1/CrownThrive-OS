"""Deterministic PentaCompliance and PentaLicense production decision runtime.

The runtime evaluates evidence and can create an immutable license grant only
when an exact, adopted rights profile and every required authority/control gate
are present. It does not discover law, manufacture ownership, sign contracts,
send provider messages, or replace qualified legal/human review.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Optional


class PentaComplianceLicenseError(ValueError):
    """Raised when a compliance or license packet is structurally unsafe."""


RISK_CLASSES = {"D0", "D1", "D2", "D3"}
LICENSE_LANES = {"self_serve", "reviewed"}
LICENSE_EVENT_ACTIONS = {"amend", "renew", "suspend", "revoke"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _without_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "receipt_sha256"}


def _receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["receipt_sha256"] = digest(result)
    return result


def verify_receipt(payload: Mapping[str, Any]) -> bool:
    expected = payload.get("receipt_sha256")
    return isinstance(expected, str) and len(expected) == 64 and digest(_without_receipt(payload)) == expected


def _required_string(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise PentaComplianceLicenseError(f"{key} must be a non-empty string")
    return item.strip()


def _string_set(value: Mapping[str, Any], key: str, *, allow_empty: bool = False) -> set[str]:
    items = value.get(key)
    if not isinstance(items, list) or (not items and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise PentaComplianceLicenseError(f"{key} must be {qualifier}")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise PentaComplianceLicenseError(f"{key} must contain non-empty strings")
    if len(items) != len(set(items)):
        raise PentaComplianceLicenseError(f"{key} must be unique")
    return set(items)


def _parse_date(value: Any, key: str) -> date:
    if not isinstance(value, str):
        raise PentaComplianceLicenseError(f"{key} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise PentaComplianceLicenseError(f"{key} must be an ISO date") from exc


def _utc_iso(now: Optional[datetime] = None) -> str:
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_obligation(obligation: Mapping[str, Any]) -> None:
    for key in ("obligation_id", "title", "source_ref", "owner_ref", "status"):
        _required_string(obligation, key)
    if obligation["status"] not in {"draft", "active", "superseded", "retired"}:
        raise PentaComplianceLicenseError("obligation status is invalid")
    _string_set(obligation, "jurisdictions")
    _string_set(obligation, "scopes")
    _string_set(obligation, "evidence_requirements")
    controls = obligation.get("controls")
    if not isinstance(controls, list) or not controls:
        raise PentaComplianceLicenseError("controls must be a non-empty list")
    seen: set[str] = set()
    for control in controls:
        if not isinstance(control, dict):
            raise PentaComplianceLicenseError("control must be an object")
        control_id = _required_string(control, "control_id")
        _required_string(control, "requirement")
        if control_id in seen:
            raise PentaComplianceLicenseError("control_id values must be unique")
        seen.add(control_id)
    _parse_date(obligation.get("effective_from"), "effective_from")
    if obligation.get("effective_to") is not None:
        if _parse_date(obligation["effective_to"], "effective_to") < _parse_date(obligation["effective_from"], "effective_from"):
            raise PentaComplianceLicenseError("effective_to cannot precede effective_from")
    source_hash = _required_string(obligation, "source_sha256")
    if len(source_hash) != 64 or any(char not in "0123456789abcdef" for char in source_hash):
        raise PentaComplianceLicenseError("source_sha256 must be a lowercase SHA-256")


def evaluate_compliance(
    obligations: Iterable[Mapping[str, Any]],
    *,
    jurisdictions: Iterable[str],
    scopes: Iterable[str],
    evidence_index: Mapping[str, Iterable[str]],
    as_of: date,
) -> dict[str, Any]:
    """Evaluate adopted obligations without asserting universal legal compliance."""
    jurisdiction_set = {str(item) for item in jurisdictions if str(item)}
    scope_set = {str(item) for item in scopes if str(item)}
    if not jurisdiction_set or not scope_set:
        raise PentaComplianceLicenseError("jurisdictions and scopes are required")
    if not isinstance(evidence_index, Mapping):
        raise PentaComplianceLicenseError("evidence_index must be an object")

    applicable: list[dict[str, Any]] = []
    source_errors: list[str] = []
    missing: list[dict[str, str]] = []
    for raw in obligations:
        try:
            validate_obligation(raw)
        except PentaComplianceLicenseError as exc:
            source_errors.append(str(exc))
            continue
        if raw["status"] != "active":
            continue
        starts = _parse_date(raw["effective_from"], "effective_from")
        ends = _parse_date(raw["effective_to"], "effective_to") if raw.get("effective_to") else None
        if as_of < starts or (ends and as_of > ends):
            continue
        if not (set(raw["jurisdictions"]) & jurisdiction_set):
            continue
        if not (set(raw["scopes"]) & scope_set):
            continue
        controls: list[dict[str, Any]] = []
        for control in raw["controls"]:
            refs = sorted({str(ref) for ref in evidence_index.get(control["control_id"], []) if str(ref)})
            satisfied = bool(refs)
            controls.append({"control_id": control["control_id"], "satisfied": satisfied, "evidence_refs": refs})
            if not satisfied:
                missing.append({"obligation_id": raw["obligation_id"], "control_id": control["control_id"]})
        applicable.append({"obligation_id": raw["obligation_id"], "source_ref": raw["source_ref"], "controls": controls})

    if source_errors:
        disposition = "HOLD_SOURCE_INVALID"
    elif missing:
        disposition = "HOLD_EVIDENCE_GAP"
    else:
        disposition = "PASS_EVIDENCE_SATISFIED"
    return _receipt({
        "schema": "ct.penta.compliance-evaluation.v1",
        "disposition": disposition,
        "truth_scope": "adopted obligation evidence only; not a universal legal opinion or binding attestation",
        "as_of": as_of.isoformat(),
        "jurisdictions": sorted(jurisdiction_set),
        "scopes": sorted(scope_set),
        "applicable": applicable,
        "missing_evidence": missing,
        "source_errors": sorted(source_errors),
    })


def validate_asset_profile(asset: Mapping[str, Any]) -> None:
    for key in ("asset_id", "version", "content_sha256", "title", "owner_ref", "status"):
        _required_string(asset, key)
    if asset["status"] not in {"active", "hold", "retired"}:
        raise PentaComplianceLicenseError("asset status is invalid")
    if len(asset["content_sha256"]) != 64 or any(char not in "0123456789abcdef" for char in asset["content_sha256"]):
        raise PentaComplianceLicenseError("content_sha256 must be a lowercase SHA-256")
    _string_set(asset, "rights_control_refs")
    _string_set(asset, "allowed_rights")
    _string_set(asset, "prohibited_rights", allow_empty=True)
    _string_set(asset, "territories")
    _string_set(asset, "media")


def _authority_ready(trace: Any) -> bool:
    return isinstance(trace, dict) and bool(trace.get("chlom_ref") and trace.get("accountable_owner"))


def _human_ready(gate: Any) -> bool:
    return isinstance(gate, dict) and gate.get("required") is True and gate.get("satisfied") is True and bool(gate.get("approver_refs"))


def evaluate_license_request(asset: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    """Return exact issuance eligibility; it performs no provider or contract action."""
    validate_asset_profile(asset)
    for key in (
        "request_id", "asset_id", "asset_version", "asset_sha256", "licensee_ref",
        "use_case", "lane", "risk_class", "valid_from", "valid_until",
        "template_ref", "acceptance_ref", "idempotency_key",
    ):
        _required_string(request, key)
    if request["risk_class"] not in RISK_CLASSES:
        raise PentaComplianceLicenseError("risk_class must be D0-D3")
    if request["lane"] not in LICENSE_LANES:
        raise PentaComplianceLicenseError("lane must be self_serve or reviewed")
    requested_rights = _string_set(request, "requested_rights")
    requested_territories = _string_set(request, "territories")
    requested_media = _string_set(request, "media")
    starts = _parse_date(request["valid_from"], "valid_from")
    ends = _parse_date(request["valid_until"], "valid_until")
    if ends < starts:
        raise PentaComplianceLicenseError("valid_until cannot precede valid_from")

    reasons: list[str] = []
    review_reasons: list[str] = []
    if asset["status"] != "active":
        reasons.append("asset is not active")
    if (request["asset_id"], request["asset_version"], request["asset_sha256"]) != (
        asset["asset_id"], asset["version"], asset["content_sha256"],
    ):
        reasons.append("request does not bind the exact registered asset version and hash")
    if not set(asset["rights_control_refs"]):
        reasons.append("chain-of-title or rights-control evidence is absent")
    outside_rights = sorted(requested_rights - set(asset["allowed_rights"]))
    prohibited = sorted(requested_rights & set(asset["prohibited_rights"]))
    outside_territories = sorted(requested_territories - set(asset["territories"]))
    outside_media = sorted(requested_media - set(asset["media"]))
    if outside_rights:
        reasons.append("requested rights exceed the adopted rights profile: " + ", ".join(outside_rights))
    if prohibited:
        reasons.append("requested rights are prohibited: " + ", ".join(prohibited))
    if outside_territories:
        reasons.append("requested territories exceed the adopted rights profile: " + ", ".join(outside_territories))
    if outside_media:
        reasons.append("requested media exceed the adopted rights profile: " + ", ".join(outside_media))
    if not _authority_ready(request.get("authority_trace")):
        reasons.append("CHLOM rights authority and accountable owner are required")
    compliance = request.get("compliance_receipt")
    if not isinstance(compliance, dict) or not verify_receipt(compliance) or compliance.get("disposition") != "PASS_EVIDENCE_SATISFIED":
        reasons.append("valid PentaCompliance evidence-satisfied receipt is required")

    if request["risk_class"] in {"D2", "D3"} or request["lane"] == "reviewed":
        review_reasons.append("risk/lane requires accountable human review")
    elif request.get("human_gate") and request["human_gate"].get("required") and not _human_ready(request["human_gate"]):
        reasons.append("declared human gate is not satisfied")

    provider_effect = request.get("provider_effect") is True
    if provider_effect and not request.get("provider_binding_ref"):
        reasons.append("certified provider binding is required for external issuance")
    if provider_effect and not request.get("readback_strategy"):
        reasons.append("provider readback strategy is required for external issuance")
    if not request.get("commercial_terms_ref"):
        review_reasons.append("commercial terms are not registered")
        if request["lane"] == "self_serve":
            reasons.append("self-serve issuance requires exact registered commercial terms")

    if reasons:
        disposition = "HOLD_FAIL_CLOSED"
    elif review_reasons and not _human_ready(request.get("human_gate")):
        disposition = "HUMAN_REVIEW_REQUIRED"
    else:
        disposition = "ISSUE_READY_PROVIDER" if provider_effect else "ISSUE_READY_INTERNAL"
    return _receipt({
        "schema": "ct.penta.license-decision.v1",
        "request_id": request["request_id"],
        "request_sha256": digest(request),
        "asset_profile_sha256": digest(asset),
        "asset_id": asset["asset_id"],
        "asset_version": asset["version"],
        "disposition": disposition,
        "reasons": reasons,
        "review_reasons": review_reasons,
        "provider_effect": provider_effect,
        "binding_action_performed": False,
    })


def issue_license_grant(
    asset: Mapping[str, Any],
    request: Mapping[str, Any],
    decision: Mapping[str, Any],
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    if not verify_receipt(decision):
        raise PentaComplianceLicenseError("license decision receipt is invalid")
    if decision.get("disposition") not in {"ISSUE_READY_INTERNAL", "ISSUE_READY_PROVIDER"}:
        raise PentaComplianceLicenseError("license decision is not issuance-ready")
    fresh = evaluate_license_request(asset, request)
    if fresh["receipt_sha256"] != decision["receipt_sha256"]:
        raise PentaComplianceLicenseError("license decision does not match the current request")
    issued_at = _utc_iso(now)
    identity = digest({
        "request_id": request["request_id"],
        "asset_id": asset["asset_id"],
        "asset_version": asset["version"],
        "licensee_ref": request["licensee_ref"],
        "idempotency_key": request["idempotency_key"],
    })
    return _receipt({
        "schema": "ct.penta.license-grant.v1",
        "license_id": f"CTL-{identity[:24].upper()}",
        "grant_version": 1,
        "status": "issued_internal" if decision["disposition"] == "ISSUE_READY_INTERNAL" else "provider_dispatch_required",
        "asset": {"asset_id": asset["asset_id"], "version": asset["version"], "content_sha256": asset["content_sha256"]},
        "licensee_ref": request["licensee_ref"],
        "rights": sorted(request["requested_rights"]),
        "territories": sorted(request["territories"]),
        "media": sorted(request["media"]),
        "valid_from": request["valid_from"],
        "valid_until": request["valid_until"],
        "template_ref": request["template_ref"],
        "acceptance_ref": request["acceptance_ref"],
        "commercial_terms_ref": request.get("commercial_terms_ref"),
        "authority_trace": request["authority_trace"],
        "decision_receipt_sha256": decision["receipt_sha256"],
        "issued_at": issued_at,
        "immutable": True,
    })


def append_license_event(
    grant: Mapping[str, Any],
    *,
    action: str,
    expected_grant_sha256: str,
    authority_trace: Mapping[str, Any],
    human_gate: Mapping[str, Any],
    evidence_refs: Iterable[str],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    if action not in LICENSE_EVENT_ACTIONS:
        raise PentaComplianceLicenseError("unsupported license lifecycle action")
    if not verify_receipt(grant) or grant.get("receipt_sha256") != expected_grant_sha256:
        raise PentaComplianceLicenseError("exact immutable grant receipt is required")
    if not _authority_ready(authority_trace) or not _human_ready(human_gate):
        raise PentaComplianceLicenseError("license lifecycle action requires rights authority and human approval")
    refs = sorted({str(ref) for ref in evidence_refs if str(ref)})
    if not refs:
        raise PentaComplianceLicenseError("license lifecycle action requires evidence")
    event_identity = digest({"grant": expected_grant_sha256, "action": action, "evidence_refs": refs})
    return _receipt({
        "schema": "ct.penta.license-event.v1",
        "event_id": f"CTLE-{event_identity[:24].upper()}",
        "license_id": grant["license_id"],
        "action": action,
        "previous_grant_sha256": expected_grant_sha256,
        "authority_trace": dict(authority_trace),
        "approver_refs": sorted(human_gate["approver_refs"]),
        "evidence_refs": refs,
        "occurred_at": _utc_iso(now),
        "mutates_original_grant": False,
    })


def public_verification(grant: Mapping[str, Any], events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    if not verify_receipt(grant):
        raise PentaComplianceLicenseError("license grant receipt is invalid")
    status = grant["status"]
    verified_events = []
    for event in events:
        if not verify_receipt(event) or event.get("license_id") != grant["license_id"]:
            raise PentaComplianceLicenseError("license event chain is invalid")
        verified_events.append(event)
    if verified_events:
        latest = sorted(verified_events, key=lambda item: (item["occurred_at"], item["event_id"]))[-1]
        status = {"revoke": "revoked", "suspend": "suspended", "renew": "renewal_recorded", "amend": "amendment_recorded"}[latest["action"]]
    return {
        "license_id": grant["license_id"],
        "asset_id": grant["asset"]["asset_id"],
        "asset_version": grant["asset"]["version"],
        "status": status,
        "valid_from": grant["valid_from"],
        "valid_until": grant["valid_until"],
        "grant_sha256": grant["receipt_sha256"],
        "event_count": len(verified_events),
    }


def self_test() -> dict[str, Any]:
    source_ref = "docs/phase3/PENTA_COMPLIANCE_LICENSE_EXECUTION_ROADMAP.md"
    obligation = {
        "obligation_id": "ct.internal.license-chain-v1", "title": "Exact rights evidence",
        "source_ref": source_ref, "source_sha256": sha256(source_ref.encode()).hexdigest(),
        "jurisdictions": ["internal"], "scopes": ["licensing"], "owner_ref": "role:rights-steward",
        "status": "active", "effective_from": "2026-08-26", "effective_to": None,
        "evidence_requirements": ["rights-profile"],
        "controls": [{"control_id": "rights-profile", "requirement": "Exact rights profile is registered."}],
    }
    compliance = evaluate_compliance([obligation], jurisdictions=["internal"], scopes=["licensing"], evidence_index={"rights-profile": ["evidence:rights:1"]}, as_of=date(2026, 8, 26))
    assert compliance["disposition"] == "PASS_EVIDENCE_SATISFIED"
    asset = {
        "asset_id": "asset:example", "version": "1.0.0", "content_sha256": "a" * 64,
        "title": "Example", "owner_ref": "CrownThrive LLC", "status": "active",
        "rights_control_refs": ["chlom:rights:example"], "allowed_rights": ["display"],
        "prohibited_rights": ["sublicense"], "territories": ["US"], "media": ["web"],
    }
    request = {
        "request_id": "request:example", "asset_id": "asset:example", "asset_version": "1.0.0",
        "asset_sha256": "a" * 64, "licensee_ref": "party:example", "requested_rights": ["display"],
        "territories": ["US"], "media": ["web"], "use_case": "approved demonstration", "lane": "self_serve",
        "risk_class": "D1", "valid_from": "2026-08-26", "valid_until": "2027-08-26",
        "template_ref": "template:license:v1", "acceptance_ref": "acceptance:example",
        "commercial_terms_ref": "terms:standard:v1", "authority_trace": {"chlom_ref": "chlom:rights:example", "accountable_owner": "role:rights-steward"},
        "human_gate": {"required": False, "satisfied": False, "approver_refs": []},
        "compliance_receipt": compliance, "provider_effect": False, "provider_binding_ref": None,
        "readback_strategy": None, "idempotency_key": "license:example:1",
    }
    decision = evaluate_license_request(asset, request)
    assert decision["disposition"] == "ISSUE_READY_INTERNAL"
    grant = issue_license_grant(asset, request, decision, now=datetime(2026, 8, 26, tzinfo=timezone.utc))
    assert verify_receipt(grant)
    return {"ok": True, "compliance": compliance["disposition"], "license": decision["disposition"], "grant_sha256": grant["receipt_sha256"]}


if __name__ == "__main__":
    print(json.dumps(self_test(), sort_keys=True))
