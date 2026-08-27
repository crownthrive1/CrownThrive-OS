"""Fail-closed HOLD hand-raise and autonomous remediation planner.

The planner keeps a HOLD visible until independently produced evidence satisfies
every required predicate.  It may route bounded, zero-provider-effect repair
candidates; it never certifies, votes, activates a provider, or clears history.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping


class HoldHandError(ValueError):
    """Raised when a HOLD evidence packet is malformed."""


PREDICATE_ROUTES = {
    "exact_head_ci": ("PentaCrawler", "PentaTest", "PentaHelp"),
    "security_gate": ("PentaCrawler", "PentaAudit", "PentaHelp"),
    "independent_verifier": ("PentaCertify", "PentaVergence", "PentaHelp"),
    "rollback_readback": ("PentaTest", "PentaAudit", "PentaHelp"),
    "zero_cost_budget": ("PentaCosts", "SmartTreasury", "PentaHelp"),
    "provider_containment": ("PentaCrawler", "PentaRoute", "PentaHelp"),
}

REQUIRED_PREDICATES = tuple(PREDICATE_ROUTES)
FINAL_STATES = {"PASS", "HOLD", "FAIL", "UNKNOWN"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _required_text(packet: Mapping[str, Any], key: str) -> str:
    value = packet.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HoldHandError(f"{key} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class Observation:
    predicate: str
    status: str
    producer_id: str
    evidence_sha256: str
    exact_head_sha: str
    independent: bool

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Observation":
        predicate = _required_text(value, "predicate")
        if predicate not in PREDICATE_ROUTES:
            raise HoldHandError(f"unsupported predicate: {predicate}")
        status = _required_text(value, "status").upper()
        if status not in FINAL_STATES:
            raise HoldHandError(f"invalid predicate status: {status}")
        evidence_sha256 = _required_text(value, "evidence_sha256").lower()
        exact_head_sha = _required_text(value, "exact_head_sha").lower()
        if len(evidence_sha256) != 64 or any(c not in "0123456789abcdef" for c in evidence_sha256):
            raise HoldHandError("evidence_sha256 must be lowercase SHA-256")
        if len(exact_head_sha) != 40 or any(c not in "0123456789abcdef" for c in exact_head_sha):
            raise HoldHandError("exact_head_sha must be lowercase Git SHA-1")
        if not isinstance(value.get("independent"), bool):
            raise HoldHandError("independent must be boolean")
        return cls(
            predicate=predicate,
            status=status,
            producer_id=_required_text(value, "producer_id"),
            evidence_sha256=evidence_sha256,
            exact_head_sha=exact_head_sha,
            independent=value["independent"],
        )


def evaluate_hold(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return a durable hand state and bounded remediation routing plan."""

    campaign_id = _required_text(packet, "campaign_id")
    hold_evidence_sha256 = _required_text(packet, "hold_evidence_sha256").lower()
    exact_head_sha = _required_text(packet, "exact_head_sha").lower()
    if len(hold_evidence_sha256) != 64:
        raise HoldHandError("hold_evidence_sha256 must be SHA-256")
    if len(exact_head_sha) != 40:
        raise HoldHandError("exact_head_sha must be Git SHA-1")
    producer_ids = packet.get("producer_ids")
    if not isinstance(producer_ids, list) or any(not isinstance(x, str) or not x for x in producer_ids):
        raise HoldHandError("producer_ids must be a string list")

    raw_observations = packet.get("observations")
    if not isinstance(raw_observations, list):
        raise HoldHandError("observations must be a list")
    observations = [Observation.from_mapping(item) for item in raw_observations]

    latest: dict[str, Observation] = {}
    for observation in observations:
        if observation.exact_head_sha == exact_head_sha:
            latest[observation.predicate] = observation

    predicates: dict[str, str] = {}
    reasons: list[str] = []
    actions: list[dict[str, Any]] = []
    for predicate in REQUIRED_PREDICATES:
        observation = latest.get(predicate)
        status = observation.status if observation else "UNKNOWN"
        if observation and status == "PASS":
            if not observation.independent or observation.producer_id in producer_ids:
                status = "HOLD"
                reasons.append(f"{predicate}: PASS evidence is not independent")
        predicates[predicate] = status
        if status != "PASS":
            routes = PREDICATE_ROUTES[predicate]
            actions.append(
                {
                    "action_key": f"{campaign_id}:{exact_head_sha}:{predicate}",
                    "predicate": predicate,
                    "state": "QUEUED_INTERNAL_REMEDIATION",
                    "routes": list(routes),
                    "provider_effect": False,
                    "paid_cost_minor": 0,
                    "certification_effect": False,
                }
            )
            if not any(reason.startswith(f"{predicate}:") for reason in reasons):
                reasons.append(f"{predicate}: {status}")

    resolution_eligible = all(value == "PASS" for value in predicates.values())
    result = {
        "schema": "ct.penta.hold-hand-decision.v1",
        "campaign_id": campaign_id,
        "hand_id": _digest({"campaign_id": campaign_id, "hold": hold_evidence_sha256}),
        "hand_state": "RESOLUTION_READY" if resolution_eligible else "RAISED",
        "hand_remains_visible": not resolution_eligible,
        "exact_head_sha": exact_head_sha,
        "predicates": predicates,
        "reasons": reasons,
        "remediation_actions": actions,
        "resolution_eligible": resolution_eligible,
        "certified": False,
        "self_certified": False,
        "provider_effect": False,
        "paid_cost_minor": 0,
        "historical_hold_deleted": False,
        "next_gate": "independent_resolution_receipt" if resolution_eligible else "bounded_remediation",
    }
    result["decision_sha256"] = _digest(result)
    return result

