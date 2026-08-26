#!/usr/bin/env python3
"""Executable control plane for the CrownThrive Penta Family.

Every registered Penta is addressable for control-plane reads and governed
handoffs. Actual member invocation requires a statically registered adapter and
must pass the existing Penta Family + interoperability gates. This runtime never
executes arbitrary shell code, dynamically imports user-selected handlers,
accepts credential material, manufactures authority, moves money, or performs
provider writes.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Callable, Iterable, Mapping, Optional
from uuid import uuid4

try:
    from runtime.penta_family import load_family, member_dispatch_gate
    from runtime.penta_interop import build_envelope, evaluate_handoff
except ModuleNotFoundError:
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from runtime.penta_family import load_family, member_dispatch_gate
    from runtime.penta_interop import build_envelope, evaluate_handoff

RUNTIME_VERSION = "1.0.0"
ADAPTER_REGISTRY = Path("data/penta/execution-adapters.registry.json")
EXECUTION_ELIGIBLE = {"certified", "production"}
VALID_EFFECTS = {"analyze", "prepare", "route", "execute", "verify", "preserve"}


class PentaExecutionError(ValueError):
    pass


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _seal(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _receipt(kind: str, disposition: str, details: Mapping[str, Any]) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": "ct.penta.execution-receipt.v1",
        "runtime_version": RUNTIME_VERSION,
        "receipt_id": f"pex-{uuid4().hex}",
        "kind": kind,
        "disposition": disposition,
        "created_at": _utcnow(),
        "details": dict(details),
    }
    value["receipt_sha256"] = _seal(value)
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PentaExecutionError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PentaExecutionError(f"JSON root must be object: {path}")
    return value


def _members(snapshot: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    value = snapshot.get("members")
    if not isinstance(value, Mapping):
        raise PentaExecutionError("family snapshot has no members map")
    return value  # type: ignore[return-value]


def _member(snapshot: Mapping[str, Any], machine_key: str) -> Mapping[str, Any]:
    value = _members(snapshot).get(machine_key)
    if not isinstance(value, Mapping):
        raise PentaExecutionError(f"unknown or unregistered Penta member: {machine_key}")
    return value


def family_list(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for key, member in sorted(_members(snapshot).items()):
        gate = member_dispatch_gate(snapshot, key)
        rows.append({
            "machine_key": key,
            "canonical_name": member.get("canonical_name"),
            "category": member.get("category"),
            "maturity": member.get("maturity"),
            "execution_eligible": bool(gate.get("eligible")),
            "portal_route": member.get("portal_route"),
        })
    return _receipt("family_list", "completed_read_only", {"member_count": len(rows), "members": rows})


def member_status(snapshot: Mapping[str, Any], machine_key: str) -> dict[str, Any]:
    member = _member(snapshot, machine_key)
    all_members = _members(snapshot)
    deps = []
    for dep in member.get("dependencies") or []:
        deps.append({
            "machine_key": dep,
            "registered": dep in all_members,
            "maturity": all_members.get(dep, {}).get("maturity") if dep in all_members else None,
        })
    missing = sorted(item["machine_key"] for item in deps if not item["registered"])
    return _receipt(
        "member_status",
        "healthy_control_plane" if not missing else "degraded_control_plane",
        {
            "machine_key": machine_key,
            "canonical_name": member.get("canonical_name"),
            "category": member.get("category"),
            "purpose": member.get("purpose"),
            "authority_boundary": member.get("authority_boundary"),
            "risk_ceiling": member.get("risk_ceiling"),
            "maturity": member.get("maturity"),
            "portal_route": member.get("portal_route"),
            "execution_gate": member_dispatch_gate(snapshot, machine_key),
            "dependencies": deps,
            "missing_dependencies": missing,
            "source": member.get("source"),
        },
    )


def validate_adapter_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("registry_id") != "crownthrive.penta.execution-adapters":
        raise PentaExecutionError("unexpected adapter registry_id")
    if registry.get("version") != "1.0.0" or registry.get("fail_closed") is not True:
        raise PentaExecutionError("adapter registry must be v1.0.0 and fail closed")
    adapters = registry.get("adapters")
    if not isinstance(adapters, list):
        raise PentaExecutionError("adapters must be a list")
    seen_ids: set[str] = set()
    seen_routes: set[tuple[str, str]] = set()
    for adapter in adapters:
        if not isinstance(adapter, Mapping):
            raise PentaExecutionError("adapter entry must be object")
        required = {"adapter_id", "member", "operation", "handler", "requested_effect", "provider_effect", "requires_execution_eligible"}
        missing = required - set(adapter)
        if missing:
            raise PentaExecutionError(f"adapter missing fields: {sorted(missing)}")
        adapter_id = adapter["adapter_id"]
        member = adapter["member"]
        operation = adapter["operation"]
        if not isinstance(adapter_id, str) or not adapter_id:
            raise PentaExecutionError("adapter_id must be non-empty string")
        if adapter_id in seen_ids:
            raise PentaExecutionError(f"duplicate adapter_id: {adapter_id}")
        seen_ids.add(adapter_id)
        if not isinstance(member, str) or not member.startswith("penta."):
            raise PentaExecutionError("adapter member must be exact penta.* key")
        if not isinstance(operation, str) or not operation:
            raise PentaExecutionError("adapter operation must be non-empty string")
        route = (member, operation)
        if route in seen_routes:
            raise PentaExecutionError(f"duplicate member/operation adapter: {route}")
        seen_routes.add(route)
        if adapter["requested_effect"] not in VALID_EFFECTS:
            raise PentaExecutionError("invalid requested_effect")
        if adapter["handler"] not in BUILTIN_HANDLERS:
            raise PentaExecutionError(f"unregistered builtin handler: {adapter['handler']!r}")
        if not isinstance(adapter["provider_effect"], bool) or not isinstance(adapter["requires_execution_eligible"], bool):
            raise PentaExecutionError("adapter booleans are invalid")
        if adapter["provider_effect"]:
            raise PentaExecutionError("v1 builtin adapter registry does not permit provider-effect handlers")
        if adapter["requested_effect"] == "execute" and adapter["requires_execution_eligible"] is not True:
            raise PentaExecutionError("execute adapters must require execution-eligible maturity")


def load_adapter_registry(root: Path) -> dict[str, Any]:
    registry = _load_json(root / ADAPTER_REGISTRY)
    validate_adapter_registry(registry)
    return registry


def _find_adapter(registry: Mapping[str, Any], member: str, operation: str) -> Optional[Mapping[str, Any]]:
    for adapter in registry.get("adapters") or []:
        if adapter.get("member") == member and adapter.get("operation") == operation:
            return adapter
    return None


@dataclass(frozen=True)
class AdapterContext:
    root: Path
    registry: Mapping[str, Any]
    snapshot: Mapping[str, Any]
    source_member: str
    target_member: str
    operation: str
    payload: Mapping[str, Any]
    evidence_refs: tuple[str, ...]
    envelope: Mapping[str, Any]
    handoff_decision: Mapping[str, Any]


def _family_snapshot(ctx: AdapterContext) -> dict[str, Any]:
    snapshot = ctx.snapshot
    return {
        "family_status": snapshot.get("family_status"),
        "production_scope": snapshot.get("production_scope"),
        "member_count": snapshot.get("member_count"),
        "maturity_counts": snapshot.get("maturity_counts"),
        "execution_eligible_members": snapshot.get("execution_eligible_members"),
        "held_members": snapshot.get("held_members"),
    }


def _beata_heartbeat(ctx: AdapterContext) -> dict[str, Any]:
    details = member_status(ctx.snapshot, "penta.beata")["details"]
    return {
        "state": "alive" if not details["missing_dependencies"] else "degraded",
        "machine_key": "penta.beata",
        "maturity": details["maturity"],
        "missing_dependencies": details["missing_dependencies"],
        "observed_at": _utcnow(),
    }


def _mesh_route_check(ctx: AdapterContext) -> dict[str, Any]:
    candidate = ctx.payload.get("candidate_target")
    if not isinstance(candidate, str) or not candidate.startswith("penta."):
        raise PentaExecutionError("route_check payload.candidate_target must be exact penta.* machine key")
    member = _member(ctx.snapshot, candidate)
    gate = member_dispatch_gate(ctx.snapshot, candidate)
    return {
        "candidate_target": candidate,
        "registered": True,
        "maturity": member.get("maturity"),
        "execution_eligible": bool(gate.get("eligible")),
        "portal_route": member.get("portal_route"),
        "dependency_count": len(member.get("dependencies") or []),
    }


BUILTIN_HANDLERS: dict[str, Callable[[AdapterContext], dict[str, Any]]] = {
    "family_snapshot": _family_snapshot,
    "beata_heartbeat": _beata_heartbeat,
    "mesh_route_check": _mesh_route_check,
}


def family_validate(root: Path, registry: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    members = _members(snapshot)
    adapters = load_adapter_registry(root)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for key, member in members.items():
        for field in ("canonical_name", "maturity", "portal_route", "source"):
            if not member.get(field):
                blockers.append({"machine_key": key, "kind": "missing_member_field", "field": field})
        for dep in member.get("dependencies") or []:
            if dep not in members:
                warnings.append({"machine_key": key, "kind": "unresolved_dependency", "dependency": dep})
    for adapter in adapters["adapters"]:
        target = adapter["member"]
        if target not in members:
            blockers.append({"adapter_id": adapter["adapter_id"], "kind": "unknown_adapter_member", "member": target})
        elif adapter["requested_effect"] == "execute" and members[target].get("maturity") not in EXECUTION_ELIGIBLE:
            blockers.append({"adapter_id": adapter["adapter_id"], "kind": "execute_adapter_targets_ineligible_member", "member": target, "maturity": members[target].get("maturity")})
    return _receipt(
        "family_validate",
        "pass" if not blockers else "fail_closed",
        {
            "family_registry_id": registry.get("registry_id"),
            "member_count": len(members),
            "adapter_count": len(adapters["adapters"]),
            "blockers": blockers,
            "warnings": warnings,
        },
    )


def invoke_member(
    root: Path,
    *,
    source_member: str,
    target_member: str,
    operation: str,
    evidence_refs: Iterable[str],
    payload: Optional[Mapping[str, Any]] = None,
    risk_class: str = "D1",
    authority_trace: Optional[Mapping[str, Optional[str]]] = None,
    human_gate: Optional[Mapping[str, Any]] = None,
    provider_binding_ref: Optional[str] = None,
    readback_strategy: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> dict[str, Any]:
    registry, snapshot = load_family(root)
    _member(snapshot, source_member)
    target = _member(snapshot, target_member)
    adapters = load_adapter_registry(root)
    adapter = _find_adapter(adapters, target_member, operation)
    if adapter is None:
        return _receipt("member_invoke", "hold_fail_closed", {"source_member": source_member, "target_member": target_member, "operation": operation, "reason": "no registered executable adapter for member/operation"})
    if adapter["requires_execution_eligible"] and target.get("maturity") not in EXECUTION_ELIGIBLE:
        return _receipt("member_invoke", "hold_fail_closed", {"source_member": source_member, "target_member": target_member, "operation": operation, "reason": f"target maturity {target.get('maturity')!r} is not execution-eligible"})
    refs = tuple(dict.fromkeys(str(ref) for ref in evidence_refs if str(ref).strip()))
    if not refs:
        raise PentaExecutionError("at least one evidence reference is required")
    envelope = build_envelope(
        source_member=source_member,
        target_member=target_member,
        operation=operation,
        requested_effect=adapter["requested_effect"],
        evidence_refs=refs,
        risk_class=risk_class,
        authority_trace=authority_trace,
        human_gate=human_gate,
        provider_effect=adapter["provider_effect"],
        provider_binding_ref=provider_binding_ref,
        readback_strategy=readback_strategy,
        idempotency_key=idempotency_key,
        metadata={"adapter_id": adapter["adapter_id"], "runtime_version": RUNTIME_VERSION},
    )
    decision = evaluate_handoff(snapshot, envelope)
    if decision.get("eligible") is not True:
        return _receipt("member_invoke", "hold_fail_closed", {"source_member": source_member, "target_member": target_member, "operation": operation, "adapter_id": adapter["adapter_id"], "handoff_decision": decision, "envelope_sha256": envelope.get("envelope_sha256")})
    ctx = AdapterContext(root, registry, snapshot, source_member, target_member, operation, dict(payload or {}), refs, envelope, decision)
    try:
        result = BUILTIN_HANDLERS[adapter["handler"]](ctx)
    except PentaExecutionError:
        raise
    except Exception as exc:
        return _receipt("member_invoke", "handler_failed", {"source_member": source_member, "target_member": target_member, "operation": operation, "adapter_id": adapter["adapter_id"], "error_type": type(exc).__name__, "error": str(exc)})
    return _receipt(
        "member_invoke",
        "completed",
        {
            "source_member": source_member,
            "target_member": target_member,
            "operation": operation,
            "adapter_id": adapter["adapter_id"],
            "requested_effect": adapter["requested_effect"],
            "provider_effect": False,
            "handoff_disposition": decision.get("disposition"),
            "trace_id": envelope.get("trace_id"),
            "correlation_id": envelope.get("correlation_id"),
            "idempotency_key": envelope.get("idempotency_key"),
            "envelope_sha256": envelope.get("envelope_sha256"),
            "result": result,
        },
    )


def build_handoff(root: Path, *, source_member: str, target_member: str, operation: str, requested_effect: str, evidence_refs: Iterable[str], risk_class: str = "D1", authority_trace: Optional[Mapping[str, Optional[str]]] = None, human_gate: Optional[Mapping[str, Any]] = None, provider_effect: bool = False, provider_binding_ref: Optional[str] = None, readback_strategy: Optional[str] = None) -> dict[str, Any]:
    _, snapshot = load_family(root)
    _member(snapshot, source_member)
    _member(snapshot, target_member)
    envelope = build_envelope(source_member=source_member, target_member=target_member, operation=operation, requested_effect=requested_effect, evidence_refs=evidence_refs, risk_class=risk_class, authority_trace=authority_trace, human_gate=human_gate, provider_effect=provider_effect, provider_binding_ref=provider_binding_ref, readback_strategy=readback_strategy)
    decision = evaluate_handoff(snapshot, envelope)
    return _receipt("handoff", str(decision.get("disposition")), {"envelope": envelope, "decision": decision})


def _json_arg(value: Optional[str]) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise PentaExecutionError(f"invalid JSON argument: {exc}") from exc
    if not isinstance(parsed, dict):
        raise PentaExecutionError("JSON argument must be an object")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executable CrownThrive Penta Family control plane")
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    status = sub.add_parser("status"); status.add_argument("machine_key")
    sub.add_parser("validate")
    handoff = sub.add_parser("handoff")
    handoff.add_argument("source_member"); handoff.add_argument("target_member"); handoff.add_argument("operation")
    handoff.add_argument("--effect", choices=sorted(VALID_EFFECTS), default="prepare"); handoff.add_argument("--risk", choices=["D0", "D1", "D2", "D3"], default="D1")
    handoff.add_argument("--evidence-ref", action="append", required=True); handoff.add_argument("--authority-json"); handoff.add_argument("--human-gate-json")
    handoff.add_argument("--provider-effect", action="store_true"); handoff.add_argument("--provider-binding-ref"); handoff.add_argument("--readback-strategy")
    invoke = sub.add_parser("invoke")
    invoke.add_argument("source_member"); invoke.add_argument("target_member"); invoke.add_argument("operation")
    invoke.add_argument("--risk", choices=["D0", "D1", "D2", "D3"], default="D1"); invoke.add_argument("--evidence-ref", action="append", required=True)
    invoke.add_argument("--payload-json"); invoke.add_argument("--authority-json"); invoke.add_argument("--human-gate-json"); invoke.add_argument("--provider-binding-ref"); invoke.add_argument("--readback-strategy"); invoke.add_argument("--idempotency-key")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root).resolve()
    try:
        registry, snapshot = load_family(root)
        if args.command == "list": result = family_list(snapshot)
        elif args.command == "status": result = member_status(snapshot, args.machine_key)
        elif args.command == "validate": result = family_validate(root, registry, snapshot)
        elif args.command == "handoff":
            result = build_handoff(root, source_member=args.source_member, target_member=args.target_member, operation=args.operation, requested_effect=args.effect, evidence_refs=args.evidence_ref, risk_class=args.risk, authority_trace=_json_arg(args.authority_json) or None, human_gate=_json_arg(args.human_gate_json) or None, provider_effect=args.provider_effect, provider_binding_ref=args.provider_binding_ref, readback_strategy=args.readback_strategy)
        else:
            result = invoke_member(root, source_member=args.source_member, target_member=args.target_member, operation=args.operation, evidence_refs=args.evidence_ref, payload=_json_arg(args.payload_json), risk_class=args.risk, authority_trace=_json_arg(args.authority_json) or None, human_gate=_json_arg(args.human_gate_json) or None, provider_binding_ref=args.provider_binding_ref, readback_strategy=args.readback_strategy, idempotency_key=args.idempotency_key)
    except Exception as exc:
        result = _receipt("runtime_error", "hold_fail_closed", {"error_type": type(exc).__name__, "error": str(exc)})
        print(json.dumps(result, indent=2, sort_keys=True)); return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("disposition") not in {"fail_closed", "hold_fail_closed", "handler_failed"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
