"""PentaPolice policy-continuity reference runtime.

The production execution plane is ThriveBase/PostgreSQL. This module provides the
repository-native deterministic model used by tests, CI, documentation, and offline
validation. It never performs provider writes, votes, money movement, or checkout.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal

ControlState = Literal["current", "superseded", "retired", "historical"]
RiskClass = Literal["D0", "D1", "D2", "D3"]


@dataclass(frozen=True)
class ControlAuthority:
    control_id: str
    control_family: str
    semantic_version: str
    effective_at: datetime
    state: ControlState
    authority_model: str


@dataclass(frozen=True)
class ReleaseEvidence:
    risk_class: RiskClass
    genuine_pass: bool
    independent_certification_pass: int
    independent_certification_required: int
    health_pass: int
    health_required: int
    route_verified: bool
    rollback_readback_verified: bool
    maintenance_active: bool
    human_approval_state: str = "not_required"


@dataclass(frozen=True)
class AuthorityDecision:
    accepted: bool
    authority_model: str
    reason: str
    oidc_role: str = "execution_identity_attestation_only"
    vote_quorum_required: bool = False
    money_movement: bool = False
    checkout_activation: bool = False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def current_control(controls: Iterable[ControlAuthority], family: str) -> ControlAuthority:
    candidates = [c for c in controls if c.control_family == family and c.state == "current"]
    if not candidates:
        raise ValueError(f"no current control registered for {family}")
    # Newest exact registration is authoritative. Duplicate older current rows are drift
    # for PentaPolice to supersede, never an invitation to merge authorities.
    return max(candidates, key=lambda c: (c.effective_at, c.semantic_version, c.control_id))


def stale_current_controls(
    controls: Iterable[ControlAuthority], family: str
) -> tuple[ControlAuthority, ...]:
    rows = [c for c in controls if c.control_family == family and c.state == "current"]
    if len(rows) <= 1:
        return ()
    winner = current_control(rows, family)
    return tuple(c for c in rows if c.control_id != winner.control_id)


def evaluate_autonomous_release(evidence: ReleaseEvidence) -> AuthorityDecision:
    if evidence.maintenance_active:
        return AuthorityDecision(False, "autonomous_exact_evidence", "maintenance_active")
    if not evidence.genuine_pass:
        return AuthorityDecision(False, "autonomous_exact_evidence", "candidate_not_genuine_pass")
    if evidence.independent_certification_required <= 0 or (
        evidence.independent_certification_pass != evidence.independent_certification_required
    ):
        return AuthorityDecision(False, "autonomous_exact_evidence", "independent_certification_incomplete")
    if evidence.health_required <= 0 or evidence.health_pass != evidence.health_required:
        return AuthorityDecision(False, "autonomous_exact_evidence", "provider_health_incomplete")
    if not evidence.route_verified:
        return AuthorityDecision(False, "autonomous_exact_evidence", "route_not_verified")
    if not evidence.rollback_readback_verified:
        return AuthorityDecision(False, "autonomous_exact_evidence", "rollback_readback_not_verified")
    if evidence.risk_class == "D3" and evidence.human_approval_state != "approved":
        return AuthorityDecision(False, "autonomous_exact_evidence", "d3_human_approval_required")
    return AuthorityDecision(True, "autonomous_exact_evidence", "exact_evidence_pass")


def supersession_story(old: ControlAuthority, new: ControlAuthority) -> str:
    if old.control_family != new.control_family:
        raise ValueError("controls must belong to the same family")
    if old.control_id == new.control_id:
        raise ValueError("a control cannot supersede itself")
    return (
        f"{old.control_id} is preserved as historical fact for the {old.control_family} "
        f"control family. It was superseded by {new.control_id}, which is the current "
        "registered authority model. Supersession preserves prior evidence and does not "
        "grant the historical control present authority."
    )
