#!/usr/bin/env python3
"""Deterministic CrownThrive OS PentaRouter redundancy runtime.

The runtime validates the OS routing topology and resolves a request to a
secret-free dispatch decision across hot, warm, and cold lanes. It never calls
a provider, moves money, grants rights, publishes content, or manufactures
CHLOM/DAIL/human authority. Provider execution and readback remain downstream
responsibilities bound to the emitted receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

RISK_RANK = {"D0": 0, "D1": 1, "D2": 2, "D3": 3}
LANE_RANK = {"hot": 0, "warm": 1, "cold": 2}
SIDE_EFFECTS = {"write", "rights", "money", "publish", "reconcile", "archive"}
FORBIDDEN_KEYS = {
    "api_key",
    "api_secret",
    "access_token",
    "authorization",
    "client_secret",
    "cookie",
    "credential",
    "mnemonic",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
    "wallet_password",
}
SOURCE_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


class PentaRouterError(ValueError):
    """Raised when a manifest or request is structurally invalid."""


@dataclass(frozen=True)
class Candidate:
    node_id: str
    state: str
    priority: int
    capacity: int


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalized(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


def find_forbidden(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            key_normalized = str(key).strip().lower()
            if key_normalized in FORBIDDEN_KEYS and child not in (None, "", "REDACTED", "***"):
                findings.append(child_path)
            findings.extend(find_forbidden(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(find_forbidden(child, f"{path}[{index}]"))
    return findings


def load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PentaRouterError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise PentaRouterError(f"JSON root must be an object: {path}")
    return value


def _require_string(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")


def validate_manifest(manifest: Mapping[str, Any]) -> list[str]:
    """Return deterministic structural findings for the PentaRouter manifest."""
    errors: list[str] = []
    _require_string(manifest.get("system_id"), "system_id", errors)
    _require_string(manifest.get("version"), "version", errors)
    _require_string(manifest.get("survival_contract_ref"), "survival_contract_ref", errors)

    for collection in ("planes", "fabrics", "bridges", "meshes", "nodes"):
        value = manifest.get(collection)
        if not isinstance(value, list) or not value:
            errors.append(f"{collection} must be a non-empty list")

    route_standard = manifest.get("route_standard")
    if not isinstance(route_standard, Mapping):
        errors.append("route_standard must be an object")
        return errors

    lanes = route_standard.get("lanes")
    if not isinstance(lanes, Mapping):
        errors.append("route_standard.lanes must be an object")
        return errors
    missing_lanes = set(LANE_RANK) - set(lanes)
    if missing_lanes:
        errors.append(f"missing route lanes: {sorted(missing_lanes)}")

    for lane_name in LANE_RANK:
        lane = lanes.get(lane_name)
        if not isinstance(lane, Mapping):
            continue
        max_risk = lane.get("max_risk")
        if max_risk not in RISK_RANK:
            errors.append(f"lane {lane_name} has invalid max_risk: {max_risk}")
        effects = lane.get("allowed_effects")
        if not isinstance(effects, list) or not effects:
            errors.append(f"lane {lane_name} must declare allowed_effects")
        controls = lane.get("required_controls")
        if not isinstance(controls, list) or not controls:
            errors.append(f"lane {lane_name} must declare required_controls")
        fallback = lane.get("fallback")
        if fallback not in set(LANE_RANK) | {"hold"}:
            errors.append(f"lane {lane_name} has invalid fallback: {fallback}")
        elif fallback != "hold" and LANE_RANK[fallback] <= LANE_RANK[lane_name]:
            errors.append(f"lane {lane_name} fallback must move toward a colder lane")

    nodes = manifest.get("nodes")
    if isinstance(nodes, list):
        node_ids: set[str] = set()
        route_coverage = {lane: 0 for lane in LANE_RANK}
        for index, node in enumerate(nodes):
            if not isinstance(node, Mapping):
                errors.append(f"nodes[{index}] must be an object")
                continue
            node_id = node.get("node_id")
            if not isinstance(node_id, str) or not node_id:
                errors.append(f"nodes[{index}].node_id must be non-empty")
                continue
            if node_id in node_ids:
                errors.append(f"duplicate node_id: {node_id}")
            node_ids.add(node_id)
            if node.get("dispatch_role") == "router":
                for lane in node.get("lanes") or []:
                    if lane in route_coverage and node.get("enabled", True):
                        route_coverage[lane] += 1
            risk_ceiling = node.get("risk_ceiling")
            if risk_ceiling is not None and risk_ceiling not in RISK_RANK:
                errors.append(f"node {node_id} has invalid risk_ceiling: {risk_ceiling}")
        for lane, count in route_coverage.items():
            if count < 1:
                errors.append(f"no enabled router node covers lane: {lane}")

    redundancy = manifest.get("redundancy")
    if not isinstance(redundancy, Mapping):
        errors.append("redundancy must be an object")
    else:
        if redundancy.get("automatic_upward_escalation") is not False:
            errors.append("automatic_upward_escalation must be false")
        if redundancy.get("automatic_money_movement_fallback") is not False:
            errors.append("automatic_money_movement_fallback must be false")

    forbidden = find_forbidden(manifest)
    if forbidden:
        errors.append("manifest contains secret-bearing fields: " + ", ".join(forbidden))
    return errors


def require_valid_manifest(manifest: Mapping[str, Any]) -> None:
    errors = validate_manifest(manifest)
    if errors:
        raise PentaRouterError("invalid manifest: " + "; ".join(errors))


def validate_request(request: Mapping[str, Any]) -> None:
    errors: list[str] = []
    for field in ("subject_id", "operation", "risk_class", "source_sha", "effect"):
        _require_string(request.get(field), field, errors)
    if request.get("risk_class") not in RISK_RANK:
        errors.append(f"invalid risk_class: {request.get('risk_class')}")
    if request.get("effect") not in {"read"} | SIDE_EFFECTS:
        errors.append(f"invalid effect: {request.get('effect')}")
    requested_lane = request.get("requested_lane", "auto")
    if requested_lane not in set(LANE_RANK) | {"auto"}:
        errors.append(f"invalid requested_lane: {requested_lane}")
    source_sha = request.get("source_sha")
    if isinstance(source_sha, str) and not SOURCE_SHA_RE.fullmatch(source_sha):
        errors.append("source_sha must be an exact 40-character hexadecimal commit SHA")
    forbidden = find_forbidden(request)
    if forbidden:
        errors.append("request contains secret-bearing fields: " + ", ".join(forbidden))
    if errors:
        raise PentaRouterError("invalid request: " + "; ".join(errors))


def _operation_lane(manifest: Mapping[str, Any], operation: str) -> str | None:
    routes = manifest.get("route_standard", {}).get("operation_routes") or []
    matches: list[tuple[int, str]] = []
    for route in routes:
        if not isinstance(route, Mapping):
            continue
        prefix = str(route.get("operation_prefix") or "")
        lane = str(route.get("lane") or "")
        if prefix and lane in LANE_RANK and operation.startswith(prefix):
            matches.append((len(prefix), lane))
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], LANE_RANK[item[1]], item[1]))
    return matches[0][1]


def infer_lane(manifest: Mapping[str, Any], request: Mapping[str, Any]) -> str:
    requested = str(request.get("requested_lane") or "auto")
    if requested != "auto":
        return requested
    operation = str(request["operation"])
    registered = _operation_lane(manifest, operation)
    if registered:
        return registered
    effect = str(request["effect"])
    if effect == "read":
        return "hot"
    if effect in {"write", "rights", "money", "publish"}:
        return "warm"
    return "cold"


def lane_sequence(manifest: Mapping[str, Any], start: str) -> list[str]:
    lanes = manifest["route_standard"]["lanes"]
    sequence: list[str] = []
    current = start
    seen: set[str] = set()
    while current != "hold":
        if current in seen:
            raise PentaRouterError(f"route fallback cycle detected at {current}")
        seen.add(current)
        sequence.append(current)
        current = str(lanes[current]["fallback"])
    return sequence


def _authority_holds(request: Mapping[str, Any], start_lane: str) -> list[str]:
    holds: list[str] = []
    effect = str(request["effect"])
    risk = str(request["risk_class"])
    if effect in SIDE_EFFECTS:
        if start_lane == "hot":
            holds.append("hot lane cannot carry side effects")
        if not str(request.get("principal_id") or "").strip():
            holds.append("side-effect request missing principal_id")
        if not str(request.get("idempotency_key") or "").strip():
            holds.append("side-effect request missing idempotency_key")
        if normalized(request.get("dail_state")) != "PASS":
            holds.append("DAIL PASS is required for side-effect routing")
        if normalized(request.get("chlom_state")) != "PASS":
            holds.append("CHLOM PASS is required for side-effect routing")
        if risk == "D3" and not str(request.get("human_authority_ref") or "").strip():
            holds.append("D3 side-effect routing requires a human_authority_ref")
    if effect == "money" and normalized(request.get("wallet_state")) != "AVAILABLE":
        holds.append("money routing requires wallet_state AVAILABLE")
    return holds


def _capability_match(capabilities: Sequence[Any], operation: str) -> bool:
    for raw in capabilities:
        capability = str(raw)
        if capability == "*" or capability == operation:
            return True
        if capability.endswith("*") and operation.startswith(capability[:-1]):
            return True
    return False


def _node_health(node: Mapping[str, Any], health: Mapping[str, Any]) -> Mapping[str, Any]:
    observed = health.get(str(node.get("node_id")))
    if isinstance(observed, Mapping):
        return observed
    default = node.get("health_default")
    return default if isinstance(default, Mapping) else {"state": "unavailable", "breaker": "open", "capacity": 0}


def candidates_for_lane(
    manifest: Mapping[str, Any],
    request: Mapping[str, Any],
    lane: str,
    health: Mapping[str, Any],
) -> list[Candidate]:
    operation = str(request["operation"])
    risk = str(request["risk_class"])
    candidates: list[Candidate] = []
    for node in manifest["nodes"]:
        if not isinstance(node, Mapping):
            continue
        if node.get("dispatch_role") != "router" or not node.get("enabled", True):
            continue
        if lane not in (node.get("lanes") or []):
            continue
        if RISK_RANK[risk] > RISK_RANK.get(str(node.get("risk_ceiling")), -1):
            continue
        if not _capability_match(node.get("capabilities") or [], operation):
            continue
        observed = _node_health(node, health)
        state = str(observed.get("state") or "unavailable").lower()
        breaker = str(observed.get("breaker") or "open").lower()
        capacity = int(observed.get("capacity") or 0)
        if state not in {"healthy", "degraded"} or breaker != "closed" or capacity < 1:
            continue
        candidates.append(
            Candidate(
                node_id=str(node["node_id"]),
                state=state,
                priority=int(node.get("priority") or 1000),
                capacity=capacity,
            )
        )
    candidates.sort(key=lambda item: (0 if item.state == "healthy" else 1, item.priority, -item.capacity, item.node_id))
    return candidates


def _lane_accepts(lane_policy: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    risk = str(request["risk_class"])
    effect = str(request["effect"])
    max_risk = str(lane_policy.get("max_risk"))
    return RISK_RANK[risk] <= RISK_RANK[max_risk] and effect in (lane_policy.get("allowed_effects") or [])


def _make_receipt(
    manifest: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    start_lane: str,
    attempted_lanes: Sequence[str],
    selected_lane: str | None,
    selected: Candidate | None,
    holds: Sequence[str],
) -> dict[str, Any]:
    side_effect = str(request["effect"]) in SIDE_EFFECTS
    fallback_used = selected_lane is not None and selected_lane != start_lane
    selected_degraded = selected is not None and selected.state == "degraded"
    if holds or selected is None or selected_lane is None:
        state = "HOLD_FAIL_CLOSED"
    elif fallback_used or selected_degraded:
        state = "DEGRADED_ROUTE_READY"
    else:
        state = "ROUTE_READY"

    controls: list[str] = []
    for lane in attempted_lanes:
        for control in manifest["route_standard"]["lanes"][lane].get("required_controls") or []:
            if control not in controls:
                controls.append(str(control))
    if side_effect and "authoritative provider readback" not in controls:
        controls.append("authoritative provider readback")

    request_projection = {
        "subject_id": request["subject_id"],
        "operation": request["operation"],
        "risk_class": request["risk_class"],
        "effect": request["effect"],
        "requested_lane": request.get("requested_lane", "auto"),
        "source_sha": request["source_sha"],
        "principal_id": request.get("principal_id"),
        "idempotency_key": request.get("idempotency_key"),
        "payload_fingerprint": request.get("payload_fingerprint")
        or fingerprint(request.get("payload") or {}),
    }
    core = {
        "schema_version": "1.0.0",
        "system_id": manifest["system_id"],
        "manifest_version": manifest["version"],
        "route_contract_ref": manifest["route_contract_ref"],
        "node_contract_ref": manifest["node_contract_ref"],
        "survival_contract_ref": manifest["survival_contract_ref"],
        "request": request_projection,
        "request_fingerprint": fingerprint(request_projection),
        "start_lane": start_lane,
        "attempted_lanes": list(attempted_lanes),
        "selected_lane": selected_lane,
        "selected_node_id": selected.node_id if selected else None,
        "selected_node_state": selected.state if selected else None,
        "fallback_used": fallback_used,
        "required_controls": controls,
        "hold_reasons": list(holds),
        "provider_execution_performed": False,
        "provider_readback_required": side_effect,
        "dispatch_eligible": state in {"ROUTE_READY", "DEGRADED_ROUTE_READY"},
        "state": state,
    }
    decision_fingerprint = fingerprint(core)
    core["decision_fingerprint"] = decision_fingerprint
    core["receipt_id"] = f"ct.pentarouter.receipt.{decision_fingerprint[:24]}"
    return core


def route_request(
    manifest: Mapping[str, Any],
    request: Mapping[str, Any],
    health: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one request into a deterministic route receipt."""
    require_valid_manifest(manifest)
    validate_request(request)
    health = health or {}
    start_lane = infer_lane(manifest, request)
    authority_holds = _authority_holds(request, start_lane)
    if authority_holds:
        return _make_receipt(
            manifest,
            request,
            start_lane=start_lane,
            attempted_lanes=(),
            selected_lane=None,
            selected=None,
            holds=authority_holds,
        )

    attempted: list[str] = []
    route_holds: list[str] = []
    selected_lane: str | None = None
    selected: Candidate | None = None
    for lane in lane_sequence(manifest, start_lane):
        attempted.append(lane)
        lane_policy = manifest["route_standard"]["lanes"][lane]
        if not _lane_accepts(lane_policy, request):
            route_holds.append(f"lane {lane} cannot carry {request['effect']} at {request['risk_class']}")
            continue
        candidates = candidates_for_lane(manifest, request, lane, health)
        if candidates:
            selected_lane = lane
            selected = candidates[0]
            route_holds = []
            break
        route_holds.append(f"no healthy closed-breaker router node available for lane {lane}")

    return _make_receipt(
        manifest,
        request,
        start_lane=start_lane,
        attempted_lanes=attempted,
        selected_lane=selected_lane,
        selected=selected,
        holds=route_holds if selected is None else (),
    )


def topology_inventory(manifest: Mapping[str, Any]) -> dict[str, Any]:
    require_valid_manifest(manifest)
    return {
        "system_id": manifest["system_id"],
        "version": manifest["version"],
        "state": manifest.get("state"),
        "planes": len(manifest["planes"]),
        "fabrics": len(manifest["fabrics"]),
        "bridges": len(manifest["bridges"]),
        "meshes": len(manifest["meshes"]),
        "nodes": len(manifest["nodes"]),
        "router_nodes": sum(1 for node in manifest["nodes"] if node.get("dispatch_role") == "router"),
        "lanes": sorted(manifest["route_standard"]["lanes"], key=LANE_RANK.get),
        "commercialization_bridge_ref": manifest.get("commercialization_bridge_ref"),
        "production_activation": manifest.get("production_activation"),
    }


def self_test(manifest: Mapping[str, Any]) -> dict[str, Any]:
    require_valid_manifest(manifest)
    healthy = {
        "ct.node.pentarouter.primary": {"state": "healthy", "breaker": "closed", "capacity": 100},
        "ct.node.pentarouter.secondary": {"state": "healthy", "breaker": "closed", "capacity": 80},
        "ct.node.pentarouter.recovery": {"state": "healthy", "breaker": "closed", "capacity": 50},
    }
    base = {
        "subject_id": "ct.selftest.subject",
        "operation": "system.status.read",
        "risk_class": "D0",
        "effect": "read",
        "requested_lane": "auto",
        "source_sha": "a" * 40,
        "payload": {"probe": True},
    }
    first = route_request(manifest, base, healthy)
    second = route_request(manifest, base, healthy)
    if first != second or first["state"] != "ROUTE_READY":
        raise PentaRouterError("deterministic hot-route self-test failed")

    failed_hot = dict(healthy)
    failed_hot["ct.node.pentarouter.primary"] = {"state": "unavailable", "breaker": "open", "capacity": 0}
    failed_hot["ct.node.pentarouter.secondary"] = {"state": "unavailable", "breaker": "open", "capacity": 0}
    fallback = route_request(manifest, base, failed_hot)
    if fallback["selected_lane"] != "warm" or fallback["state"] != "DEGRADED_ROUTE_READY":
        raise PentaRouterError("hot-to-warm failover self-test failed")

    d3 = {
        **base,
        "operation": "commercial.license.accept",
        "risk_class": "D3",
        "effect": "rights",
        "principal_id": "did:crownthrive:selftest",
        "idempotency_key": "selftest-d3",
        "dail_state": "PASS",
        "chlom_state": "PASS",
    }
    held = route_request(manifest, d3, healthy)
    if held["state"] != "HOLD_FAIL_CLOSED":
        raise PentaRouterError("D3 human-authority hold self-test failed")

    try:
        route_request(manifest, {**base, "payload": {"access_token": "forbidden"}}, healthy)
    except PentaRouterError:
        secret_guard = "PASS"
    else:
        raise PentaRouterError("secret guard self-test failed")

    return {
        "system_id": manifest["system_id"],
        "determinism": "PASS",
        "hot_route": "PASS",
        "hot_to_warm_failover": "PASS",
        "d3_human_authority_hold": "PASS",
        "secret_guard": secret_guard,
        "provider_execution_performed": False,
        "production_activation": manifest.get("production_activation"),
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate a PentaRouter manifest")
    validate.add_argument("--manifest", type=Path, required=True)

    route = subparsers.add_parser("route", help="resolve a secret-free route receipt")
    route.add_argument("--manifest", type=Path, required=True)
    route.add_argument("--request", type=Path, required=True)
    route.add_argument("--health", type=Path)
    route.add_argument("--output", type=Path, required=True)

    inventory = subparsers.add_parser("inventory", help="emit topology inventory")
    inventory.add_argument("--manifest", type=Path, required=True)

    selftest = subparsers.add_parser("self-test", help="run deterministic embedded tests")
    selftest.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        manifest = load_json(args.manifest)
        if args.command == "validate":
            require_valid_manifest(manifest)
            result: Mapping[str, Any] = {"state": "PASS", "system_id": manifest["system_id"]}
        elif args.command == "route":
            request = load_json(args.request)
            health = load_json(args.health) if args.health else {}
            result = route_request(manifest, request, health)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif args.command == "inventory":
            result = topology_inventory(manifest)
        else:
            result = self_test(manifest)
    except PentaRouterError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
