"""Penta Family institutional-controls runtime.

Dependency-free governance/runtime primitives for:
PentaCompliance, PentaPrivacy, PentaIdentity, PentaData, PentaRecords,
PentaProcure, PentaVendor, PentaContracts and PentaQuality.

This module is intentionally fail-closed. It may package, classify and route
work at implemented maturity, but provider or consequential execution is
eligible only when the caller supplies evidence-backed certified/production
maturity plus the required authority, human and provider bindings.

Constitutional invariant: no PENTA subsystem manufactures authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4


KNOWN_SYSTEMS = {
    "penta.compliance",
    "penta.privacy",
    "penta.identity",
    "penta.data",
    "penta.records",
    "penta.procure",
    "penta.vendor",
    "penta.contracts",
    "penta.quality",
}

MATURITIES = {"specified", "implemented", "certified", "production", "hold", "retired"}
EXECUTION_ELIGIBLE = {"certified", "production"}
REQUESTED_EFFECTS = {"analyze", "prepare", "route", "execute"}

CONSEQUENTIAL_ACTIONS = {
    "penta.compliance": {"submit_attestation", "file_compliance_response", "close_material_exception"},
    "penta.privacy": {"disclose_personal_data", "erase_personal_data", "restrict_processing", "change_processing_purpose", "respond_to_rights_request"},
    "penta.identity": {"grant_role", "revoke_role", "grant_entitlement", "revoke_entitlement", "disable_identity"},
    "penta.data": {"publish_data_product", "share_restricted_dataset", "change_data_classification", "change_schema_contract"},
    "penta.records": {"place_hold", "release_hold", "dispose_record", "destroy_record", "change_retention_schedule"},
    "penta.procure": {"submit_purchase_order", "place_order", "approve_requisition", "accept_quote"},
    "penta.vendor": {"approve_vendor", "suspend_vendor", "offboard_vendor", "renew_vendor"},
    "penta.contracts": {"send_for_signature", "sign_contract", "accept_terms", "amend_contract", "terminate_contract"},
    "penta.quality": {"close_nonconformance", "approve_capa", "change_acceptance_criteria", "release_quality_hold"},
}

FORBIDDEN_ACTIONS = {
    ("penta.compliance", "invent_obligation"): "Compliance obligations require an authoritative source.",
    ("penta.compliance", "waive_regulatory_obligation"): "PentaCompliance cannot waive a binding obligation.",
    ("penta.compliance", "self_attest_compliance"): "Binding attestations require accountable signatory authority and evidence.",
    ("penta.privacy", "fabricate_consent"): "Consent cannot be manufactured.",
    ("penta.privacy", "waive_data_subject_right"): "PentaPrivacy cannot waive a person's statutory or contractual rights.",
    ("penta.identity", "self_grant_privilege"): "PentaIdentity cannot self-create privilege.",
    ("penta.identity", "mint_unchartered_role"): "Role authority must resolve to an adopted authority source.",
    ("penta.data", "silently_redefine_source_truth"): "Source semantics cannot be silently rewritten.",
    ("penta.data", "bypass_privacy_classification"): "Data governance cannot bypass privacy/security classification.",
    ("penta.records", "destroy_record_under_hold"): "Records under hold cannot be destroyed.",
    ("penta.records", "rewrite_historical_record"): "Historical evidence must remain preserved.",
    ("penta.procure", "self_authorize_spend"): "Procurement capability does not create spend authority.",
    ("penta.vendor", "self_certify_provider_adapter"): "PentaCertify owns provider adapter certification.",
    ("penta.vendor", "create_provider_credential"): "PentaCredentials owns protected credential lifecycle.",
    ("penta.contracts", "provide_legal_advice"): "PentaContracts is contract lifecycle management, not legal counsel.",
    ("penta.contracts", "self_sign_contract"): "Contract signature requires authorized signatory authority.",
    ("penta.quality", "erase_nonconformance"): "Quality findings must be dispositioned and preserved.",
    ("penta.quality", "self_certify_release"): "PentaAssure/PentaCertify own independent release/capability certification.",
}

INDEPENDENCE_ACTIONS = {
    ("penta.identity", "grant_role"),
    ("penta.identity", "grant_entitlement"),
    ("penta.quality", "close_nonconformance"),
    ("penta.quality", "approve_capa"),
    ("penta.compliance", "submit_attestation"),
    ("penta.vendor", "approve_vendor"),
}

PROVIDER_EFFECT_SYSTEMS = {
    "penta.identity", "penta.procure", "penta.vendor", "penta.contracts",
    "penta.privacy", "penta.records", "penta.data",
}


class InstitutionalControlError(ValueError):
    """Raised when an institutional-control request violates structure."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def receipt_sha256(value: Dict[str, Any]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def build_control_request(
    *,
    system: str,
    action: str,
    requested_effect: str,
    evidence_refs: Iterable[str],
    member_maturity: str = "implemented",
    risk_class: str = "D1",
    authority_trace: Optional[Dict[str, Optional[str]]] = None,
    human_gate: Optional[Dict[str, Any]] = None,
    provider_effect: bool = False,
    provider_binding_ref: Optional[str] = None,
    readback_strategy: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    packet = {
        "request_id": f"pic-{uuid4().hex}",
        "system": system,
        "action": action,
        "requested_effect": requested_effect,
        "evidence_refs": list(evidence_refs),
        "member_maturity": member_maturity,
        "risk_class": risk_class,
        "authority_trace": authority_trace or {"chlom_ref": None, "dail_ref": None, "accountable_owner": None},
        "human_gate": human_gate or {"required": False, "satisfied": False, "approver_refs": [], "separation_of_duties": False},
        "provider_effect": bool(provider_effect),
        "provider_binding_ref": provider_binding_ref,
        "readback_strategy": readback_strategy,
        "metadata": dict(metadata or {}),
        "created_at": _iso(now or _utcnow()),
    }
    validate_control_request(packet)
    packet["request_sha256"] = receipt_sha256(packet)
    return packet


def validate_control_request(packet: Dict[str, Any]) -> None:
    if not isinstance(packet, dict):
        raise InstitutionalControlError("request must be an object")
    required = {
        "request_id", "system", "action", "requested_effect", "evidence_refs",
        "member_maturity", "risk_class", "authority_trace", "human_gate",
        "provider_effect", "provider_binding_ref", "readback_strategy", "metadata", "created_at",
    }
    missing = required - set(packet)
    if missing:
        raise InstitutionalControlError(f"missing fields: {sorted(missing)}")
    if packet["system"] not in KNOWN_SYSTEMS:
        raise InstitutionalControlError(f"unknown system: {packet['system']}")
    if not isinstance(packet["action"], str) or not packet["action"].strip():
        raise InstitutionalControlError("action is required")
    if packet["requested_effect"] not in REQUESTED_EFFECTS:
        raise InstitutionalControlError("requested_effect must be analyze, prepare, route or execute")
    if packet["member_maturity"] not in MATURITIES:
        raise InstitutionalControlError(f"invalid member_maturity: {packet['member_maturity']}")
    if packet["risk_class"] not in {"D0", "D1", "D2", "D3"}:
        raise InstitutionalControlError("risk_class must be D0-D3")
    refs = packet["evidence_refs"]
    if not isinstance(refs, list) or not refs:
        raise InstitutionalControlError("evidence_refs must contain at least one reference")
    if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise InstitutionalControlError("evidence_refs must contain non-empty strings")
    if len(refs) != len(set(refs)):
        raise InstitutionalControlError("evidence_refs must be unique")
    trace = packet["authority_trace"]
    if not isinstance(trace, dict) or not {"chlom_ref", "dail_ref", "accountable_owner"}.issubset(trace):
        raise InstitutionalControlError("authority_trace requires chlom_ref, dail_ref and accountable_owner")
    gate = packet["human_gate"]
    if not isinstance(gate, dict):
        raise InstitutionalControlError("human_gate must be an object")
    gate_fields = {"required", "satisfied", "approver_refs", "separation_of_duties"}
    if not gate_fields.issubset(gate):
        raise InstitutionalControlError(f"human_gate missing fields: {sorted(gate_fields - set(gate))}")
    if not isinstance(gate["required"], bool) or not isinstance(gate["satisfied"], bool):
        raise InstitutionalControlError("human gate required/satisfied must be booleans")
    if not isinstance(gate["separation_of_duties"], bool):
        raise InstitutionalControlError("human_gate.separation_of_duties must be boolean")
    if not isinstance(gate["approver_refs"], list):
        raise InstitutionalControlError("human_gate.approver_refs must be a list")
    if gate["satisfied"] and not gate["approver_refs"]:
        raise InstitutionalControlError("a satisfied human gate requires an approver reference")
    if not isinstance(packet["provider_effect"], bool):
        raise InstitutionalControlError("provider_effect must be boolean")
    if packet["provider_binding_ref"] is not None and (not isinstance(packet["provider_binding_ref"], str) or not packet["provider_binding_ref"].strip()):
        raise InstitutionalControlError("provider_binding_ref must be non-empty or null")
    if packet["readback_strategy"] is not None and (not isinstance(packet["readback_strategy"], str) or not packet["readback_strategy"].strip()):
        raise InstitutionalControlError("readback_strategy must be non-empty or null")


def _authority_present(packet: Dict[str, Any]) -> bool:
    trace = packet["authority_trace"]
    return bool((trace.get("chlom_ref") or trace.get("dail_ref")) and trace.get("accountable_owner"))


def required_controls(packet: Dict[str, Any]) -> Dict[str, Any]:
    system = packet["system"]
    action = packet["action"]
    consequential = action in CONSEQUENTIAL_ACTIONS.get(system, set())
    provider_binding_required = bool(packet["provider_effect"] or (consequential and system in PROVIDER_EFFECT_SYSTEMS))
    human_gate_required = bool(consequential or packet["risk_class"] in {"D2", "D3"})
    return {
        "consequential": consequential,
        "authority_required": consequential or packet["requested_effect"] == "execute",
        "human_gate_required": human_gate_required,
        "provider_binding_required": provider_binding_required,
        "separation_of_duties_required": (system, action) in INDEPENDENCE_ACTIONS,
        "readback_required": packet["requested_effect"] == "execute" or provider_binding_required,
        "execution_maturity_required": packet["requested_effect"] == "execute",
    }


def _result(disposition: str, reasons: List[str], controls: Dict[str, Any]) -> Dict[str, Any]:
    result = {"disposition": disposition, "reasons": reasons, "controls": controls}
    result["receipt_sha256"] = receipt_sha256(result)
    return result


def evaluate_control_request(packet: Dict[str, Any]) -> Dict[str, Any]:
    validate_control_request(packet)
    controls = required_controls(packet)
    system = packet["system"]
    action = packet["action"]
    forbidden = FORBIDDEN_ACTIONS.get((system, action))
    if forbidden:
        return _result("hold_fail_closed", [forbidden], controls)
    if packet["member_maturity"] in {"hold", "retired"}:
        return _result("hold_fail_closed", [f"member maturity is {packet['member_maturity']}"], controls)
    metadata = packet.get("metadata") or {}
    if system == "penta.records" and action in {"dispose_record", "destroy_record"} and metadata.get("active_hold"):
        return _result("hold_fail_closed", ["record disposition is prohibited while an active hold exists"], controls)
    if system == "penta.privacy" and action == "change_processing_purpose" and not metadata.get("purpose_review_ref"):
        return _result("hold_fail_closed", ["processing-purpose change requires a purpose/privacy review reference"], controls)
    if system == "penta.quality" and action == "change_acceptance_criteria" and metadata.get("after_failure"):
        return _result("hold_fail_closed", ["acceptance criteria cannot be lowered after failure to manufacture a pass"], controls)
    reasons: List[str] = []
    if controls["execution_maturity_required"] and packet["member_maturity"] not in EXECUTION_ELIGIBLE:
        reasons.append(f"execution requires certified/production maturity; current maturity is {packet['member_maturity']}")
    if controls["authority_required"] and not _authority_present(packet):
        reasons.append("CHLOM/DAIL authority trace and accountable owner are required")
    gate = packet["human_gate"]
    if controls["human_gate_required"]:
        if not gate["required"]:
            reasons.append("PentaHybrid human gate must be marked required")
        elif not gate["satisfied"]:
            reasons.append("PentaHybrid human gate has not been satisfied")
    if controls["separation_of_duties_required"] and not gate["separation_of_duties"]:
        reasons.append("separation-of-duties evidence is required")
    if controls["provider_binding_required"] and not packet.get("provider_binding_ref"):
        reasons.append("certified provider binding reference is required")
    if controls["readback_required"] and not packet.get("readback_strategy"):
        reasons.append("readback strategy is required for provider/consequential execution")
    if system == "penta.records" and action in {"dispose_record", "destroy_record"}:
        if not metadata.get("retention_authority_ref"):
            reasons.append("record disposition requires retention/disposition authority")
        if metadata.get("hold_clearance") is not True:
            reasons.append("record disposition requires explicit hold-clearance evidence")
    if system == "penta.contracts" and action in {"send_for_signature", "sign_contract", "accept_terms"}:
        if not metadata.get("legal_review_ref"):
            reasons.append("contract binding workflow requires PentaLegal/counsel review evidence")
        if not metadata.get("signatory_authority_ref"):
            reasons.append("contract binding workflow requires authorized signatory evidence")
    if system == "penta.procure" and action in {"submit_purchase_order", "place_order", "accept_quote"}:
        if not metadata.get("spend_authority_ref"):
            reasons.append("procurement commitment requires spend authority evidence")
        if not metadata.get("contract_terms_ref"):
            reasons.append("procurement commitment requires governed contract/terms evidence")
    if system == "penta.compliance" and action == "submit_attestation":
        if not metadata.get("obligation_source_ref"):
            reasons.append("attestation requires authoritative obligation source")
        if not metadata.get("evidence_sufficiency_ref"):
            reasons.append("attestation requires evidence-sufficiency review")
    if system == "penta.quality" and action in {"close_nonconformance", "approve_capa"} and not metadata.get("retest_evidence_ref"):
        reasons.append("quality closure requires re-test/effectiveness evidence")
    if reasons:
        return _result("governance_required", reasons, controls)
    disposition = "advisory_ready" if packet["requested_effect"] == "analyze" else "workflow_ready" if packet["requested_effect"] in {"prepare", "route"} else "execution_ready"
    return _result(disposition, [], controls)


def self_test() -> Dict[str, Any]:
    base = build_control_request(system="penta.data", action="classify_dataset", requested_effect="analyze", evidence_refs=["evidence:data-catalog:1"], member_maturity="implemented")
    assert evaluate_control_request(base)["disposition"] == "advisory_ready"
    identity = build_control_request(
        system="penta.identity", action="grant_role", requested_effect="execute",
        evidence_refs=["evidence:role-request:1"], member_maturity="implemented",
        authority_trace={"chlom_ref": "chlom:role:1", "dail_ref": None, "accountable_owner": "role:owner"},
        human_gate={"required": True, "satisfied": True, "approver_refs": ["human:approver:1"], "separation_of_duties": True},
        provider_effect=True, provider_binding_ref="provider-binding:iam:1", readback_strategy="read effective role binding",
    )
    assert evaluate_control_request(identity)["disposition"] == "governance_required"
    forbidden = build_control_request(system="penta.privacy", action="fabricate_consent", requested_effect="prepare", evidence_refs=["evidence:request:1"])
    assert evaluate_control_request(forbidden)["disposition"] == "hold_fail_closed"
    return {"ok": True, "systems": sorted(KNOWN_SYSTEMS), "system_count": len(KNOWN_SYSTEMS), "execution_eligible_maturities": sorted(EXECUTION_ELIGIBLE)}


if __name__ == "__main__":
    print(json.dumps(self_test(), sort_keys=True))
