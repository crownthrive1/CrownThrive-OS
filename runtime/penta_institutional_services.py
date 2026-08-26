"""PENTA Institutional Services governance runtime.

This module provides a deterministic, dependency-free decision-envelope and
fail-closed policy engine for PentaCapital, PentaImpact, PentaAnalytics,
PentaLegal, PentaRisk, PentaAudit, PentaPolicy, PentaEthics and PentaSecurity.

The runtime deliberately does not execute provider actions. It decides whether
an institutional-service output is advisory-ready, requires governance, is
ready for separately authorized execution, or must be held fail-closed.

Authority invariant: no PENTA subsystem manufactures authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4


KNOWN_SYSTEMS = {
    "penta.capital",
    "penta.impact",
    "penta.analytics",
    "penta.legal",
    "penta.risk",
    "penta.audit",
    "penta.policy",
    "penta.ethics",
    "penta.security",
}

PACKET_STATUSES = {"proposed", "approved", "rejected", "expired", "executed", "held"}

# Actions which a subsystem may analyze/package but may not autonomously execute.
CONSEQUENTIAL_ACTIONS = {
    "penta.capital": {
        "transfer_funds",
        "move_money",
        "disburse_funds",
        "place_trade",
        "borrow_funds",
        "pledge_asset",
        "open_account",
        "change_beneficiary",
        "commit_capital",
    },
    "penta.legal": {
        "sign_contract",
        "waive_right",
        "settle_claim",
        "make_legal_admission",
        "bind_organization",
        "accept_legal_terms",
    },
    "penta.policy": {
        "enact_policy",
        "repeal_policy",
        "supersede_policy",
        "grant_policy_exception",
        "change_policy_authority",
    },
    "penta.risk": {
        "accept_risk",
        "raise_risk_tolerance",
        "override_control",
        "waive_control",
    },
    "penta.ethics": {
        "issue_binding_veto",
        "remove_officer",
        "impose_sanction",
    },
    "penta.security": {
        "revoke_access",
        "rotate_credentials",
        "disable_service",
        "quarantine_resource",
        "delete_key",
        "expand_privilege",
        "change_security_policy",
    },
}

# These actions belong to another institutional owner and must not be promoted
# even when the packet otherwise contains approvals.
WRONG_SYSTEM_ACTIONS = {
    ("penta.audit", "certify_release"): "PentaAssure owns release-readiness certification.",
    ("penta.audit", "erase_finding"): "Audit findings must be dispositioned and preserved, not erased.",
    ("penta.audit", "approve_own_remediation"): "Independent re-test or accountable-owner approval is required.",
    ("penta.legal", "provide_legal_advice"): "PentaLegal is legal operations, not legal counsel.",
    ("penta.capital", "self_authorize_transfer"): "Capital authority must resolve to accountable governance and provider rails.",
    ("penta.policy", "self_enact_policy"): "Policy authority must resolve to an adopted CHLOM/DAIL-recognized source.",
    ("penta.security", "self_expand_privilege"): "Security controls cannot self-create privilege.",
}

ADVISORY_SYSTEMS = {"penta.impact", "penta.analytics"}

REQUIRED_FIELDS = {
    "packet_id",
    "issuing_system",
    "action_class",
    "summary",
    "evidence_refs",
    "risk_score",
    "impact_score",
    "required_capability",
    "human_gate",
    "approvals",
    "expires_at",
    "override_policy",
    "rollback_strategy",
    "audit_correlation_id",
    "status",
    "created_at",
}


class DecisionPacketError(ValueError):
    """Raised when a decision packet is structurally invalid."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise DecisionPacketError("datetime values must be non-empty ISO-8601 strings or null")
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise DecisionPacketError(f"invalid ISO-8601 datetime: {value}") from exc
    if parsed.tzinfo is None:
        raise DecisionPacketError("datetime values must include a timezone")
    return parsed.astimezone(timezone.utc)


def build_decision_packet(
    *,
    issuing_system: str,
    action_class: str,
    summary: str,
    evidence_refs: Iterable[str],
    risk_score: int,
    impact_score: int,
    required_capability: Optional[str] = None,
    human_gate_required: bool = False,
    human_roles: Optional[Iterable[str]] = None,
    quorum: int = 0,
    approvals: Optional[List[Dict[str, Any]]] = None,
    expires_at: Optional[str] = None,
    override_policy: str = "no_unrecorded_override",
    rollback_strategy: str = "hold_and_route_to_accountable_owner",
    audit_correlation_id: Optional[str] = None,
    status: str = "proposed",
    authority_trace: Optional[Dict[str, Optional[str]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build and validate a portable PENTA decision packet.

    Building a packet is evidence packaging, not authorization.
    """

    created = now or _utcnow()
    packet = {
        "packet_id": f"pdp-{uuid4().hex}",
        "issuing_system": issuing_system,
        "action_class": action_class,
        "summary": summary,
        "evidence_refs": list(evidence_refs),
        "risk_score": risk_score,
        "impact_score": impact_score,
        "required_capability": required_capability,
        "human_gate": {
            "required": bool(human_gate_required),
            "roles": list(human_roles or []),
            "quorum": quorum,
        },
        "approvals": list(approvals or []),
        "expires_at": expires_at,
        "override_policy": override_policy,
        "rollback_strategy": rollback_strategy,
        "audit_correlation_id": audit_correlation_id or f"audit-{uuid4().hex}",
        "status": status,
        "created_at": _iso(created),
        "authority_trace": authority_trace
        or {
            "chlom_ref": None,
            "dail_ref": None,
            "accountable_owner": None,
            "provider_binding_ref": None,
        },
        "metadata": dict(metadata or {}),
    }
    validate_decision_packet(packet, now=created)
    return packet


def validate_decision_packet(packet: Dict[str, Any], *, now: Optional[datetime] = None) -> None:
    """Validate structural invariants. Raises DecisionPacketError on failure."""

    if not isinstance(packet, dict):
        raise DecisionPacketError("packet must be an object")

    missing = REQUIRED_FIELDS - set(packet)
    if missing:
        raise DecisionPacketError(f"missing required fields: {sorted(missing)}")

    system = packet["issuing_system"]
    if system not in KNOWN_SYSTEMS:
        raise DecisionPacketError(f"unknown issuing_system: {system}")

    if not isinstance(packet["packet_id"], str) or len(packet["packet_id"]) < 8:
        raise DecisionPacketError("packet_id must be a stable non-empty identifier")
    if not isinstance(packet["audit_correlation_id"], str) or len(packet["audit_correlation_id"]) < 8:
        raise DecisionPacketError("audit_correlation_id must be a stable non-empty identifier")
    if not isinstance(packet["action_class"], str) or not packet["action_class"].strip():
        raise DecisionPacketError("action_class is required")
    if not isinstance(packet["summary"], str) or not packet["summary"].strip():
        raise DecisionPacketError("summary is required")

    evidence = packet["evidence_refs"]
    if not isinstance(evidence, list) or not evidence or any(not isinstance(x, str) or not x.strip() for x in evidence):
        raise DecisionPacketError("evidence_refs must contain at least one non-empty reference")
    if len(evidence) != len(set(evidence)):
        raise DecisionPacketError("evidence_refs must be unique")

    for key in ("risk_score", "impact_score"):
        value = packet[key]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise DecisionPacketError(f"{key} must be an integer from 0 through 100")

    if packet["status"] not in PACKET_STATUSES:
        raise DecisionPacketError(f"invalid status: {packet['status']}")

    gate = packet["human_gate"]
    if not isinstance(gate, dict) or not {"required", "roles", "quorum"}.issubset(gate):
        raise DecisionPacketError("human_gate requires required, roles and quorum")
    if not isinstance(gate["required"], bool):
        raise DecisionPacketError("human_gate.required must be boolean")
    if not isinstance(gate["roles"], list) or any(not isinstance(role, str) or not role.strip() for role in gate["roles"]):
        raise DecisionPacketError("human_gate.roles must be a list of non-empty role names")
    if len(gate["roles"]) != len(set(gate["roles"])):
        raise DecisionPacketError("human_gate.roles must be unique")
    if isinstance(gate["quorum"], bool) or not isinstance(gate["quorum"], int) or gate["quorum"] < 0:
        raise DecisionPacketError("human_gate.quorum must be a non-negative integer")
    if gate["required"] and (not gate["roles"] or gate["quorum"] < 1):
        raise DecisionPacketError("required human gates must name at least one role and quorum >= 1")
    if not gate["required"] and gate["quorum"] != 0:
        raise DecisionPacketError("non-required human gates must have quorum 0")

    approvals = packet["approvals"]
    if not isinstance(approvals, list):
        raise DecisionPacketError("approvals must be a list")
    for approval in approvals:
        if not isinstance(approval, dict):
            raise DecisionPacketError("approval entries must be objects")
        for key in ("principal", "role", "decision", "timestamp"):
            if key not in approval:
                raise DecisionPacketError(f"approval missing {key}")
        if approval["decision"] not in {"approve", "deny", "abstain", "recuse"}:
            raise DecisionPacketError("approval.decision must be approve, deny, abstain or recuse")
        _parse_datetime(approval["timestamp"])

    _parse_datetime(packet["created_at"])
    expiry = _parse_datetime(packet["expires_at"])
    effective_now = (now or _utcnow()).astimezone(timezone.utc)
    if expiry is not None and packet["status"] not in {"expired", "rejected", "executed"} and expiry <= effective_now:
        raise DecisionPacketError("packet is expired but status has not converged to expired/rejected/executed")

    if not isinstance(packet["override_policy"], str) or not packet["override_policy"].strip():
        raise DecisionPacketError("override_policy is required")
    if not isinstance(packet["rollback_strategy"], str) or not packet["rollback_strategy"].strip():
        raise DecisionPacketError("rollback_strategy is required")


def _unique_approved_principals(packet: Dict[str, Any], allowed_roles: Iterable[str]) -> set[str]:
    roles = set(allowed_roles)
    return {
        approval["principal"]
        for approval in packet.get("approvals", [])
        if approval.get("decision") == "approve" and approval.get("role") in roles
    }


def required_controls(packet: Dict[str, Any]) -> Dict[str, Any]:
    """Return governance controls required for a packet's action and risk."""

    system = packet["issuing_system"]
    action = packet["action_class"]
    risk = packet["risk_score"]
    consequential = action in CONSEQUENTIAL_ACTIONS.get(system, set())

    # High risk is always escalated even when the action class is ordinarily advisory.
    human_required = consequential or risk >= 70
    capability_required = consequential or risk >= 85
    independent_review = system in {"penta.audit", "penta.security"} or risk >= 90

    if system in ADVISORY_SYSTEMS and risk < 70:
        human_required = False
        capability_required = False

    return {
        "consequential": consequential,
        "human_gate_required": human_required,
        "capability_required": capability_required,
        "independent_review_required": independent_review,
    }


def evaluate_decision_packet(packet: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Evaluate a packet without executing it.

    Returns one of:
      * advisory_ready
      * governance_required
      * authorized_ready
      * hold_fail_closed
    """

    validate_decision_packet(packet, now=now)
    system = packet["issuing_system"]
    action = packet["action_class"]
    controls = required_controls(packet)
    reasons: List[str] = []

    wrong_system = WRONG_SYSTEM_ACTIONS.get((system, action))
    if wrong_system:
        return {
            "disposition": "hold_fail_closed",
            "reasons": [wrong_system],
            "controls": controls,
        }

    if packet["status"] in {"rejected", "expired", "held"}:
        return {
            "disposition": "hold_fail_closed",
            "reasons": [f"packet status is {packet['status']}"],
            "controls": controls,
        }

    gate = packet["human_gate"]
    if controls["human_gate_required"]:
        if not gate["required"]:
            reasons.append("PentaHybrid human gate is required for this action/risk class")
        elif len(_unique_approved_principals(packet, gate["roles"])) < gate["quorum"]:
            reasons.append("human approval quorum has not been satisfied")

    if controls["capability_required"]:
        if not packet.get("required_capability"):
            reasons.append("a concrete required_capability is required")
        trace = packet.get("authority_trace") or {}
        if not (trace.get("chlom_ref") or trace.get("dail_ref")):
            reasons.append("CHLOM/DAIL authority trace is missing")
        if not trace.get("accountable_owner"):
            reasons.append("accountable institutional owner is missing")

    # Capital and disruptive security actions additionally require an exact provider binding.
    if controls["consequential"] and system in {"penta.capital", "penta.security"}:
        trace = packet.get("authority_trace") or {}
        if not trace.get("provider_binding_ref"):
            reasons.append("certified provider binding reference is missing")

    if controls["independent_review_required"]:
        metadata = packet.get("metadata") or {}
        if not metadata.get("independent_review_ref"):
            reasons.append("independent review evidence is required")

    if reasons:
        return {
            "disposition": "governance_required",
            "reasons": reasons,
            "controls": controls,
        }

    if controls["consequential"] or controls["capability_required"]:
        return {
            "disposition": "authorized_ready",
            "reasons": ["governance prerequisites are represented; execution must still occur through the separately certified route/provider"],
            "controls": controls,
        }

    return {
        "disposition": "advisory_ready",
        "reasons": ["packet is structurally valid and remains non-authoritative advisory evidence"],
        "controls": controls,
    }


def system_boundary(system: str) -> Tuple[str, str]:
    """Return concise purpose/boundary text for operator surfaces."""

    boundaries = {
        "penta.capital": ("capital decision intelligence", "cannot autonomously move or bind money"),
        "penta.impact": ("impact measurement and program evaluation", "cannot award funding or certify claims by itself"),
        "penta.analytics": ("cross-ecosystem analytics and metric semantics", "cannot silently redefine source truth or authority"),
        "penta.legal": ("legal-operations workflow", "cannot act as counsel or bind CrownThrive"),
        "penta.risk": ("enterprise risk governance", "cannot accept consequential residual risk for an owner"),
        "penta.audit": ("independent execution/control audit", "cannot self-certify releases or erase findings"),
        "penta.policy": ("policy lifecycle and controls mapping", "cannot self-enact or self-reinterpret binding policy"),
        "penta.ethics": ("ethics/integrity review", "cannot manufacture a veto or governance role"),
        "penta.security": ("security governance and protective-action routing", "cannot self-expand privilege or bypass security controls"),
    }
    if system not in boundaries:
        raise DecisionPacketError(f"unknown system: {system}")
    return boundaries[system]
