#!/usr/bin/env python3
"""Resolve COS commercialization operations into governed MCP mesh envelopes.

This router never calls a provider. It validates the requested lane and emits a
secret-free dispatch envelope for an already configured CrownThrive/CHLOM MCP
server. Side-effect authority remains explicit and independently evidenced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

FORBIDDEN_KEYS = {
    "private_key",
    "mnemonic",
    "wallet_password",
    "api_secret",
    "access_token",
    "client_secret",
    "authorization",
    "cookie"
}
CHLOM_OPERATIONS = (
    "commercial.license.",
    "commercial.wallet.",
    "commercial.entitlement.",
    "commercial.settlement.",
    "commercial.refund.",
    "commercial.reversal.",
)
WALLET_OPERATIONS = (
    "commercial.wallet.",
    "commercial.settlement.",
    "commercial.refund.",
    "commercial.reversal.",
)


class MeshRouteError(RuntimeError):
    """Raised when a route or side-effect request violates mesh policy."""


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
            if str(key).lower() in FORBIDDEN_KEYS and child not in (None, "", "REDACTED", "***"):
                findings.append(child_path)
            findings.extend(find_forbidden(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(find_forbidden(child, f"{path}[{index}]"))
    return findings


def route_operation(routing: Mapping[str, Any], operation: str) -> tuple[str, Mapping[str, Any]]:
    lanes = routing.get("lanes")
    if not isinstance(lanes, Mapping):
        raise MeshRouteError("routing policy has no lanes")
    matches: list[tuple[str, Mapping[str, Any]]] = []
    for lane_name, lane in lanes.items():
        if isinstance(lane, Mapping) and operation in lane.get("operations", []):
            matches.append((str(lane_name), lane))
    if not matches:
        raise MeshRouteError(f"operation is not registered: {operation}")
    if len(matches) != 1:
        raise MeshRouteError(f"operation has ambiguous lanes: {operation}")
    return matches[0]


def target_servers(routing: Mapping[str, Any], operation: str) -> list[str]:
    refs = routing.get("mcp_server_refs")
    if not isinstance(refs, Mapping):
        raise MeshRouteError("routing policy has no MCP server references")
    crown = str(refs.get("crownthrive_os") or "")
    chlom = str(refs.get("chlom_chain_evidence") or "")
    if operation.startswith(CHLOM_OPERATIONS):
        targets = [chlom, crown]
    else:
        targets = [crown]
    if any(not value for value in targets):
        raise MeshRouteError("required MCP server reference is missing")
    return targets


def build_dispatch_envelope(
    routing: Mapping[str, Any],
    operation: str,
    request: Mapping[str, Any],
    *,
    source_sha: str,
    authorize_side_effects: bool = False,
    dail_state: str = "HOLD",
    chlom_state: str = "HOLD",
    wallet_state: str = "UNAVAILABLE",
) -> dict[str, Any]:
    forbidden = find_forbidden(request)
    if forbidden:
        raise MeshRouteError("secret-bearing request fields are prohibited: " + ", ".join(forbidden))
    if not source_sha.strip():
        raise MeshRouteError("exact source_sha is required")
    lane_name, lane = route_operation(routing, operation)
    side_effects = bool(lane.get("side_effects_allowed"))
    if lane_name == "hot" and side_effects:
        raise MeshRouteError("hot lane cannot allow side effects")
    if side_effects:
        if not authorize_side_effects:
            raise MeshRouteError("side-effect operation requires explicit authorization")
        if normalized(dail_state) != "PASS":
            raise MeshRouteError("DAIL PASS is required for side-effect dispatch")
        for required in ("principal_did", "idempotency_key"):
            if request.get(required) in (None, ""):
                raise MeshRouteError(f"side-effect request missing {required}")
    if operation.startswith(CHLOM_OPERATIONS) and normalized(chlom_state) != "PASS":
        raise MeshRouteError("CHLOM PASS is required for this operation")
    if operation.startswith(WALLET_OPERATIONS) and normalized(wallet_state) != "AVAILABLE":
        breaker = routing.get("circuit_breakers", {}).get(
            "wallet_provider_unavailable", "deny_wallet_side_effect"
        )
        raise MeshRouteError(f"wallet circuit breaker: {breaker}")

    public_request = {
        key: value for key, value in request.items() if str(key).lower() not in FORBIDDEN_KEYS
    }
    request_fingerprint = fingerprint(public_request)
    envelope = {
        "schema_version": "1.0.0",
        "envelope_id": f"ct.mesh-dispatch.{request_fingerprint[:24]}",
        "routing_id": routing.get("routing_id"),
        "operation": operation,
        "lane": lane_name,
        "side_effects": side_effects,
        "execution_authorized": bool(authorize_side_effects) if side_effects else True,
        "provider_execution_performed": False,
        "target_mcp_servers": target_servers(routing, operation),
        "source_sha": source_sha,
        "request_fingerprint": request_fingerprint,
        "required_controls": lane.get("required_controls", []),
        "request": public_request,
        "readback_required": side_effects,
        "rollback_or_compensation_required": side_effects,
        "state": "DISPATCH_READY" if side_effects else "READ_READY",
    }
    envelope["envelope_fingerprint"] = fingerprint(envelope)
    return envelope


def load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MeshRouteError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise MeshRouteError(f"JSON root must be an object: {path}")
    return value


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routing", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorize-side-effects", action="store_true")
    parser.add_argument("--dail-state", default="HOLD")
    parser.add_argument("--chlom-state", default="HOLD")
    parser.add_argument("--wallet-state", default="UNAVAILABLE")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        routing = load_json(args.routing)
        request = load_json(args.request)
        envelope = build_dispatch_envelope(
            routing,
            args.operation,
            request,
            source_sha=args.source_sha,
            authorize_side_effects=args.authorize_side_effects,
            dail_state=args.dail_state,
            chlom_state=args.chlom_state,
            wallet_state=args.wallet_state,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except MeshRouteError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(envelope["envelope_fingerprint"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
