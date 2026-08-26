#!/usr/bin/env python3
"""PentaBrain, PentaSpine, PentaNerves, health, load, cost and identity runtime."""
from __future__ import annotations

import hashlib
import ipaddress
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


class OrganicError(ValueError):
    """Fail-closed organic control-plane violation."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def validate_vault_identity(identity: Mapping[str, Any]) -> None:
    """Accept public identity references only; private material and IP identity are forbidden."""
    allowed = {"vault_id", "public_key_fingerprint", "key_algorithm", "signature_ref"}
    unknown = set(identity) - allowed
    if unknown:
        raise OrganicError(f"unsupported or sensitive identity fields: {sorted(unknown)}")
    vault_id = identity.get("vault_id")
    fingerprint = identity.get("public_key_fingerprint")
    if not isinstance(vault_id, str) or not vault_id.startswith("vault:") or _is_ip(vault_id.removeprefix("vault:")):
        raise OrganicError("identity must use a non-IP Vault ID")
    if not isinstance(fingerprint, str) or not fingerprint.startswith("sha256:") or len(fingerprint) != 71:
        raise OrganicError("public key fingerprint must be sha256:<64 lowercase hex>")
    try:
        int(fingerprint[7:], 16)
    except ValueError as exc:
        raise OrganicError("public key fingerprint is not hexadecimal") from exc
    for field in identity:
        if any(word in field.lower() for word in ("private", "secret", "password", "mnemonic", "ip_address")):
            raise OrganicError("private material and IP identity are prohibited")


@dataclass(frozen=True)
class OrganState:
    organ_id: str
    health: float
    load: float
    cost: float
    capacity: float
    redundancy: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "OrganState":
        organ_id = value.get("organ_id")
        if not isinstance(organ_id, str) or not organ_id:
            raise OrganicError("organ_id is required")
        numeric = {}
        for field in ("health", "load", "cost", "capacity"):
            item = value.get(field)
            if not isinstance(item, (int, float)) or isinstance(item, bool) or item < 0:
                raise OrganicError(f"{field} must be a non-negative number")
            numeric[field] = float(item)
        if numeric["health"] > 1 or numeric["load"] > 1 or numeric["capacity"] > 1:
            raise OrganicError("health, load and capacity must be between 0 and 1")
        redundancy = value.get("redundancy")
        if not isinstance(redundancy, int) or isinstance(redundancy, bool) or redundancy < 0:
            raise OrganicError("redundancy must be a non-negative integer")
        return cls(organ_id=organ_id, redundancy=redundancy, **numeric)


class OrganicControlPlane:
    """Stateful, deterministic body model with an append-only hash-chained spine."""

    def __init__(self, contract: Mapping[str, Any]):
        if contract.get("schema") != "ct.penta.organic-control-plane.v1":
            raise OrganicError("unsupported organic control-plane contract")
        self.contract = dict(contract)
        self.events: list[dict[str, Any]] = []
        self.learning: dict[str, dict[str, float | int]] = {}

    def route_governance(self, signal_type: str) -> str:
        routes = self.contract.get("governance_routes", {})
        route = routes.get(signal_type)
        if not isinstance(route, str):
            raise OrganicError("unknown governance signal fails closed")
        return route

    def _append(self, event: dict[str, Any]) -> dict[str, Any]:
        body = dict(event)
        body["sequence"] = len(self.events) + 1
        body["previous_sha256"] = self.events[-1]["event_sha256"] if self.events else "GENESIS"
        body["event_sha256"] = digest(body)
        self.events.append(body)
        return body

    def assess(self, organ: OrganState) -> dict[str, Any]:
        """PentaBrain assessment using health, pressure, redundancy and cost."""
        utilization = organ.load / organ.capacity if organ.capacity else float("inf")
        cost_limit = float(self.contract["cost_policy"]["per_organ_limit"])
        minimum_redundancy = int(self.contract["resilience_policy"]["minimum_redundancy"])
        reasons: list[str] = []
        if organ.health < 0.25:
            disposition = "quarantine_and_recover"
            reasons.append("critical_health")
        elif organ.redundancy < minimum_redundancy:
            disposition = "restore_redundancy"
            reasons.append("redundancy_below_floor")
        elif utilization > 1:
            disposition = "shed_and_rebalance_load"
            reasons.append("capacity_exceeded")
        elif organ.cost > cost_limit:
            disposition = "recede_noncritical_capacity"
            reasons.append("cost_limit_exceeded")
        elif utilization >= 0.8:
            disposition = "grow_capacity"
            reasons.append("high_utilization")
        elif utilization < 0.25 and organ.capacity > float(self.contract["resilience_policy"]["reserve_capacity_floor"]):
            disposition = "recede_with_reserve"
            reasons.append("sustained_low_utilization")
        else:
            disposition = "continue"
            reasons.append("within_operating_band")
        learned = self.learning.setdefault(organ.organ_id, {"observations": 0, "health_sum": 0.0})
        learned["observations"] = int(learned["observations"]) + 1
        learned["health_sum"] = float(learned["health_sum"]) + organ.health
        return {
            "organ_id": organ.organ_id,
            "health_class": "broken" if organ.health < 0.25 else "weak" if organ.health < 0.6 else "strong",
            "utilization": utilization,
            "disposition": disposition,
            "reasons": reasons,
            "learning": {
                "observations": learned["observations"],
                "mean_health": float(learned["health_sum"]) / int(learned["observations"]),
                "mode": "bounded_observational_no_self_authorization",
            },
        }

    def ingest(self, signal: Mapping[str, Any], *, observed_at: str | None = None) -> dict[str, Any]:
        """PentaNerves intake → PentaSpine event → PentaBrain assessment."""
        if signal.get("schema") != "ct.penta.nerve-signal.v1":
            raise OrganicError("unsupported nerve signal")
        identity = signal.get("identity")
        if not isinstance(identity, Mapping):
            raise OrganicError("signal identity is required")
        validate_vault_identity(identity)
        signal_type = signal.get("signal_type")
        if not isinstance(signal_type, str):
            raise OrganicError("signal_type is required")
        organ = OrganState.from_mapping(signal.get("organ", {}))
        governance_destination = self.route_governance(signal_type)
        assessment = self.assess(organ)
        event = {
            "schema": "ct.penta.spine-event.v1",
            "signal_id": signal.get("signal_id"),
            "signal_sha256": digest(signal),
            "source_vault_id": identity["vault_id"],
            "source_public_key_fingerprint": identity["public_key_fingerprint"],
            "governance_destination": governance_destination,
            "assessment": assessment,
            "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
        }
        return self._append(event)

    def verify_spine(self) -> bool:
        previous = "GENESIS"
        for sequence, event in enumerate(self.events, start=1):
            body = dict(event)
            claimed = body.pop("event_sha256", None)
            if body.get("sequence") != sequence or body.get("previous_sha256") != previous or digest(body) != claimed:
                return False
            previous = str(claimed)
        return True

    def command_center_snapshot(self) -> dict[str, Any]:
        """Public-safe projection: no private key, raw signature, IP or payload body."""
        states = [e["assessment"] for e in self.events]
        counts = {name: sum(1 for s in states if s["health_class"] == name) for name in ("strong", "weak", "broken")}
        snapshot: dict[str, Any] = {
            "schema": "ct.command-center.organic-health.v1",
            "event_count": len(self.events),
            "spine_integrity": self.verify_spine(),
            "health_counts": counts,
            "latest_event_sha256": self.events[-1]["event_sha256"] if self.events else None,
            "organs": [
                {
                    "organ_id": state["organ_id"],
                    "health_class": state["health_class"],
                    "utilization": state["utilization"],
                    "disposition": state["disposition"],
                }
                for state in states[-100:]
            ],
            "identity_projection": "vault_id_and_public_key_fingerprint_only",
        }
        snapshot["snapshot_sha256"] = digest(snapshot)
        return snapshot
