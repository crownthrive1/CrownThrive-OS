#!/usr/bin/env python3
"""PentaBrain, PentaSpine, PentaNerves, health, load, cost and identity runtime."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


class OrganicError(ValueError):
    """Fail-closed organic control-plane violation."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


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
    if (
        not isinstance(fingerprint, str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint)
    ):
        raise OrganicError("public key fingerprint must be sha256:<64 lowercase hex>")
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
            if (
                not isinstance(item, (int, float))
                or isinstance(item, bool)
                or not math.isfinite(item)
                or item < 0
            ):
                raise OrganicError(f"{field} must be a finite non-negative number")
            numeric[field] = float(item)
        if numeric["health"] > 1 or numeric["load"] > 1 or numeric["capacity"] > 1:
            raise OrganicError("health, load and capacity must be between 0 and 1")
        redundancy = value.get("redundancy")
        if not isinstance(redundancy, int) or isinstance(redundancy, bool) or redundancy < 0:
            raise OrganicError("redundancy must be a non-negative integer")
        return cls(organ_id=organ_id, redundancy=redundancy, **numeric)


class OrganicControlPlane:
    """Stateful, deterministic body model with an append-only hash-chained spine."""

    def __init__(self, contract: Mapping[str, Any], *, journal_path: Path | None = None):
        if contract.get("schema") != "ct.penta.organic-control-plane.v1":
            raise OrganicError("unsupported organic control-plane contract")
        if contract.get("version") != "1.1.0":
            raise OrganicError("unsupported organic control-plane version")
        routes = contract.get("information_routes")
        if not isinstance(routes, Mapping) or set(routes) != {"afferent", "efferent", "lateral"}:
            raise OrganicError("organic control plane requires exact tri-directional routes")
        time_policy = contract.get("time_policy")
        if not isinstance(time_policy, Mapping) or any(
            not isinstance(time_policy.get(field), (int, float))
            or isinstance(time_policy.get(field), bool)
            or not math.isfinite(float(time_policy[field]))
            or float(time_policy[field]) < 0
            for field in ("max_signal_age_seconds", "max_future_skew_seconds")
        ):
            raise OrganicError("organic time policy must contain finite non-negative bounds")
        self.contract = dict(contract)
        self.journal_path = journal_path
        self.events: list[dict[str, Any]] = []
        self.learning: dict[str, dict[str, float | int]] = {}
        self.signal_ids: set[str] = set()
        if journal_path and journal_path.exists():
            self._replay_journal(journal_path)

    def _replay_journal(self, path: Path) -> None:
        """Rebuild the spine from durable JSONL and fail closed on any corruption."""
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OrganicError(f"invalid PentaSpine journal line {line_number}") from exc
            if not isinstance(event, dict):
                raise OrganicError("PentaSpine journal entries must be objects")
            signal_id = event.get("signal_id")
            if not isinstance(signal_id, str) or not signal_id or signal_id in self.signal_ids:
                raise OrganicError("PentaSpine journal contains a duplicate or invalid signal ID")
            self.signal_ids.add(signal_id)
            self.events.append(event)
        if not self.verify_spine():
            raise OrganicError("PentaSpine journal integrity failure")

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
        if self.journal_path:
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            with self.journal_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        self.events.append(body)
        return body

    def assess(self, organ: OrganState) -> dict[str, Any]:
        """PentaBrain assessment using health, pressure, redundancy and cost."""
        utilization = organ.load / organ.capacity if organ.capacity else None
        cost_limit = float(self.contract["cost_policy"]["per_organ_limit"])
        minimum_redundancy = int(self.contract["resilience_policy"]["minimum_redundancy"])
        reasons: list[str] = []
        if organ.health < 0.25:
            disposition = "quarantine_and_recover"
            reasons.append("critical_health")
        elif organ.redundancy < minimum_redundancy:
            disposition = "restore_redundancy"
            reasons.append("redundancy_below_floor")
        elif utilization is None and organ.load > 0:
            disposition = "shed_and_rebalance_load"
            reasons.append("zero_capacity_with_load")
        elif utilization is not None and utilization > 1:
            disposition = "shed_and_rebalance_load"
            reasons.append("capacity_exceeded")
        elif organ.cost > cost_limit:
            disposition = "recede_noncritical_capacity"
            reasons.append("cost_limit_exceeded")
        elif utilization is not None and utilization >= 0.8:
            disposition = "grow_capacity"
            reasons.append("high_utilization")
        elif (
            utilization is not None
            and utilization < 0.25
            and organ.capacity > float(self.contract["resilience_policy"]["reserve_capacity_floor"])
        ):
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

    @staticmethod
    def _timestamp(value: str, field: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise OrganicError(f"{field} must be ISO-8601") from exc
        if parsed.tzinfo is None:
            raise OrganicError(f"{field} requires a timezone")
        return parsed.astimezone(timezone.utc)

    def ingest(
        self,
        signal: Mapping[str, Any],
        *,
        observed_at: str | None = None,
        received_at: str | None = None,
    ) -> dict[str, Any]:
        """PentaNerves intake → PentaSpine event → PentaBrain assessment."""
        if signal.get("schema") != "ct.penta.nerve-signal.v1":
            raise OrganicError("unsupported nerve signal")
        signal_id = signal.get("signal_id")
        if not isinstance(signal_id, str) or not signal_id:
            raise OrganicError("signal_id is required")
        if signal_id in self.signal_ids:
            raise OrganicError("duplicate signal_id rejected by idempotency gate")
        identity = signal.get("identity")
        if not isinstance(identity, Mapping):
            raise OrganicError("signal identity is required")
        validate_vault_identity(identity)
        signal_type = signal.get("signal_type")
        if not isinstance(signal_type, str):
            raise OrganicError("signal_type is required")
        direction = signal.get("information_direction", "afferent")
        directions = self.contract.get("information_routes", {})
        if direction not in directions:
            raise OrganicError("unknown information direction fails closed")
        organ = OrganState.from_mapping(signal.get("organ", {}))
        governance_destination = self.route_governance(signal_type)
        assessment = self.assess(organ)
        observed_text = observed_at or datetime.now(timezone.utc).isoformat()
        received_text = received_at or datetime.now(timezone.utc).isoformat()
        observed_time = self._timestamp(observed_text, "observed_at")
        received_time = self._timestamp(received_text, "received_at")
        age_seconds = (received_time - observed_time).total_seconds()
        time_policy = self.contract.get("time_policy", {})
        if age_seconds < -float(time_policy.get("max_future_skew_seconds", 300)):
            raise OrganicError("future-dated signal rejected")
        if age_seconds > float(time_policy.get("max_signal_age_seconds", 604800)):
            raise OrganicError("stale signal rejected")
        event = {
            "schema": "ct.penta.spine-event.v1",
            "signal_id": signal_id,
            "signal_sha256": digest(signal),
            "source_vault_id": identity["vault_id"],
            "source_public_key_fingerprint": identity["public_key_fingerprint"],
            "governance_destination": governance_destination,
            "information_direction": direction,
            "information_route": directions[direction]["path"],
            "assessment": assessment,
            "observed_at": observed_time.isoformat(),
            "received_at": received_time.isoformat(),
        }
        appended = self._append(event)
        self.signal_ids.add(signal_id)
        return appended

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
            "spine_durability": "journal_replay_verified" if self.journal_path else "process_memory_only",
        }
        if any(state.get("utilization") is not None and not math.isfinite(state["utilization"]) for state in states):
            raise OrganicError("non-finite utilization cannot enter Command Center projection")
        snapshot["snapshot_sha256"] = digest(snapshot)
        return snapshot
