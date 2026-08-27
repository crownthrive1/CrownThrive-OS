#!/usr/bin/env python3
"""CrownThrive Penta Family interoperability and certification runtime.

This module is the repository-native protocol fabric joining registered Penta
systems. It validates addressability and handoff contracts across the entire
Penta Family without manufacturing authority or promoting child maturity.

It performs no provider side effects. A PASS certifies repository-level
interoperability only; consequential/provider execution remains subject to the
exact member, CHLOM/DAIL, PentaHybrid, PentaCredentials/PentaCertify, readback,
and preservation gates.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Optional
from uuid import uuid4

PROTOCOL_VERSION = "1.0.0"
ENVELOPE_SCHEMA = "ct.penta.interoperability-envelope.v1"
ALLOWED_EFFECTS = {"analyze", "prepare", "route", "execute", "verify", "preserve"}
EXECUTION_ELIGIBLE = {"certified", "production"}
REQUIRED_SPINE = {
    "penta.control",
    "penta.mcp",
    "penta.route",
    "penta.federation",
    "penta.docs",
    "penta.assure",
}
REQUIRED_OBSERVABILITY = {
    "penta.error",
    "penta.logger",
    "penta.trace",
    "penta.metric",
}


class PentaInteropError(ValueError):
    """Raised when a Penta interoperability contract is structurally invalid."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PentaInteropError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PentaInteropError(f"JSON root must be object: {path}")
    return value


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PentaInteropError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def receipt_sha256(value: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def validate_interoperability_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("registry_id") != "crownthrive.penta.interoperability":
        raise PentaInteropError("unexpected interoperability registry_id")
    if registry.get("status") != "production":
        raise PentaInteropError("interoperability registry must declare production")
    if registry.get("protocol_version") != PROTOCOL_VERSION:
        raise PentaInteropError("unsupported interoperability protocol_version")

    refs = registry.get("references")
    if not isinstance(refs, dict):
        raise PentaInteropError("references must be an object")
    expected_refs = {
        "family_registry": "data/penta/family.registry.json",
        "envelope_schema": "schemas/penta/interoperability-envelope.schema.json",
        "runtime": "runtime/penta_interop.py",
    }
    for key, expected in expected_refs.items():
        if refs.get(key) != expected:
            raise PentaInteropError(f"references.{key} must be {expected}")

    invariants = registry.get("invariants")
    if not isinstance(invariants, dict):
        raise PentaInteropError("invariants must be an object")
    for flag in (
        "all_registered_members_addressable",
        "unknown_members_fail_closed",
        "exact_source_target_machine_keys",
        "trace_required",
        "idempotency_required",
        "evidence_required",
        "execution_preserves_member_maturity",
        "consequential_execution_requires_authority",
        "provider_execution_requires_certified_binding_and_readback",
        "execution_requires_dail_event_plan",
        "material_execution_requires_sealed_receipt_before_certification",
    ):
        if invariants.get(flag) is not True:
            raise PentaInteropError(f"invariants.{flag} must be true")

    spine = set(registry.get("required_spine") or [])
    if spine != REQUIRED_SPINE:
        raise PentaInteropError("required_spine does not match the canonical Penta interop spine")
    observability = set(registry.get("required_observability") or [])
    if observability != REQUIRED_OBSERVABILITY:
        raise PentaInteropError("required_observability does not match the canonical Penta observability spine")
    handoff = registry.get("handoff_contract")
    if not isinstance(handoff, Mapping):
        raise PentaInteropError("handoff_contract must be an object")
    if set(handoff.get("dail_write_modes") or []) != {"same_transaction", "transactional_outbox"}:
        raise PentaInteropError("handoff_contract.dail_write_modes drift")
    for flag in (
        "execute_requires_chlom_and_dail_authority_refs",
        "execute_requires_dail_event_plan",
        "terminal_execution_requires_dail_receipt",
    ):
        if handoff.get(flag) is not True:
            raise PentaInteropError(f"handoff_contract.{flag} must be true")


def build_envelope(
    *,
    source_member: str,
    target_member: str,
    operation: str,
    requested_effect: str,
    evidence_refs: Iterable[str],
    risk_class: str = "D1",
    authority_trace: Optional[Mapping[str, Optional[str]]] = None,
    human_gate: Optional[Mapping[str, Any]] = None,
    provider_effect: bool = False,
    provider_binding_ref: Optional[str] = None,
    readback_strategy: Optional[str] = None,
    trace_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "schema": ENVELOPE_SCHEMA,
        "protocol_version": PROTOCOL_VERSION,
        "message_id": f"pim-{uuid4().hex}",
        "source_member": source_member,
        "target_member": target_member,
        "operation": operation,
        "requested_effect": requested_effect,
        "risk_class": risk_class,
        "trace_id": trace_id or f"ptr-{uuid4().hex}",
        "correlation_id": correlation_id or f"pcr-{uuid4().hex}",
        "idempotency_key": idempotency_key or f"pik-{uuid4().hex}",
        "evidence_refs": list(evidence_refs),
        "authority_trace": dict(authority_trace or {
            "chlom_ref": None,
            "dail_ref": None,
            "accountable_owner": None,
        }),
        "human_gate": dict(human_gate or {
            "required": False,
            "satisfied": False,
            "approver_refs": [],
            "separation_of_duties": False,
        }),
        "provider_effect": bool(provider_effect),
        "provider_binding_ref": provider_binding_ref,
        "readback_strategy": readback_strategy,
        "metadata": dict(metadata or {}),
        "created_at": _iso(now or datetime.now(timezone.utc)),
    }
    validate_envelope(envelope)
    envelope["envelope_sha256"] = receipt_sha256(envelope)
    return envelope


def validate_envelope(envelope: Mapping[str, Any]) -> None:
    if not isinstance(envelope, Mapping):
        raise PentaInteropError("envelope must be an object")
    required = {
        "schema",
        "protocol_version",
        "message_id",
        "source_member",
        "target_member",
        "operation",
        "requested_effect",
        "risk_class",
        "trace_id",
        "correlation_id",
        "idempotency_key",
        "evidence_refs",
        "authority_trace",
        "human_gate",
        "provider_effect",
        "provider_binding_ref",
        "readback_strategy",
        "metadata",
        "created_at",
    }
    missing = required - set(envelope)
    if missing:
        raise PentaInteropError(f"missing envelope fields: {sorted(missing)}")
    if envelope["schema"] != ENVELOPE_SCHEMA:
        raise PentaInteropError("unexpected envelope schema")
    if envelope["protocol_version"] != PROTOCOL_VERSION:
        raise PentaInteropError("unsupported envelope protocol_version")
    for key in ("message_id", "source_member", "target_member", "operation", "trace_id", "correlation_id", "idempotency_key", "created_at"):
        if not isinstance(envelope[key], str) or not envelope[key].strip():
            raise PentaInteropError(f"{key} must be a non-empty string")
    for key in ("source_member", "target_member"):
        if not envelope[key].startswith("penta."):
            raise PentaInteropError(f"{key} must be an exact penta.* machine key")
    if envelope["requested_effect"] not in ALLOWED_EFFECTS:
        raise PentaInteropError(f"requested_effect must be one of {sorted(ALLOWED_EFFECTS)}")
    if envelope["risk_class"] not in {"D0", "D1", "D2", "D3"}:
        raise PentaInteropError("risk_class must be D0-D3")

    refs = envelope["evidence_refs"]
    if not isinstance(refs, list) or not refs:
        raise PentaInteropError("evidence_refs must contain at least one reference")
    if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise PentaInteropError("evidence_refs must contain non-empty strings")
    if len(refs) != len(set(refs)):
        raise PentaInteropError("evidence_refs must be unique")

    authority = envelope["authority_trace"]
    if not isinstance(authority, Mapping) or not {"chlom_ref", "dail_ref", "accountable_owner"} <= set(authority):
        raise PentaInteropError("authority_trace requires chlom_ref, dail_ref and accountable_owner")

    gate = envelope["human_gate"]
    gate_fields = {"required", "satisfied", "approver_refs", "separation_of_duties"}
    if not isinstance(gate, Mapping) or not gate_fields <= set(gate):
        raise PentaInteropError("human_gate is incomplete")
    if not isinstance(gate["required"], bool) or not isinstance(gate["satisfied"], bool):
        raise PentaInteropError("human_gate required/satisfied must be boolean")
    if not isinstance(gate["separation_of_duties"], bool):
        raise PentaInteropError("human_gate.separation_of_duties must be boolean")
    if not isinstance(gate["approver_refs"], list):
        raise PentaInteropError("human_gate.approver_refs must be a list")
    if gate["satisfied"] and not gate["approver_refs"]:
        raise PentaInteropError("satisfied human gate requires an approver reference")

    if not isinstance(envelope["provider_effect"], bool):
        raise PentaInteropError("provider_effect must be boolean")
    for key in ("provider_binding_ref", "readback_strategy"):
        value = envelope[key]
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise PentaInteropError(f"{key} must be null or non-empty string")
    if not isinstance(envelope["metadata"], Mapping):
        raise PentaInteropError("metadata must be an object")


def _authority_present(envelope: Mapping[str, Any]) -> bool:
    authority = envelope["authority_trace"]
    return bool(
        authority.get("chlom_ref")
        and authority.get("dail_ref")
        and authority.get("accountable_owner")
    )


def _dail_write_plan_present(envelope: Mapping[str, Any]) -> bool:
    """Require every execution handoff to declare how its material event is sealed."""
    metadata = envelope.get("metadata")
    if not isinstance(metadata, Mapping):
        return False
    return bool(
        metadata.get("dail_write_mode") in {"same_transaction", "transactional_outbox"}
        and isinstance(metadata.get("dail_event_plan_ref"), str)
        and metadata["dail_event_plan_ref"].strip()
    )


def _decision(disposition: str, reasons: list[str], *, envelope: Mapping[str, Any], source: Any = None, target: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "disposition": disposition,
        "eligible": disposition in {"workflow_ready", "execution_ready"},
        "reasons": reasons,
        "source_member": envelope["source_member"],
        "target_member": envelope["target_member"],
        "source_maturity": source.get("maturity") if isinstance(source, Mapping) else None,
        "target_maturity": target.get("maturity") if isinstance(target, Mapping) else None,
        "requested_effect": envelope["requested_effect"],
        "trace_id": envelope["trace_id"],
        "correlation_id": envelope["correlation_id"],
        "idempotency_key": envelope["idempotency_key"],
        "dail_write_mode": envelope["metadata"].get("dail_write_mode"),
        "dail_event_plan_ref": envelope["metadata"].get("dail_event_plan_ref"),
    }
    result["receipt_sha256"] = receipt_sha256(result)
    return result


def evaluate_handoff(family_snapshot: Mapping[str, Any], envelope: Mapping[str, Any]) -> dict[str, Any]:
    validate_envelope(envelope)
    members = family_snapshot.get("members")
    if not isinstance(members, Mapping):
        return _decision("hold_fail_closed", ["family snapshot has no members map"], envelope=envelope)

    source = members.get(envelope["source_member"])
    target = members.get(envelope["target_member"])
    if source is None:
        return _decision("hold_fail_closed", ["source member is not registered"], envelope=envelope, target=target)
    if target is None:
        return _decision("hold_fail_closed", ["target member is not registered"], envelope=envelope, source=source)

    source_maturity = source.get("maturity")
    target_maturity = target.get("maturity")
    if source_maturity in {"hold", "retired"} or target_maturity in {"hold", "retired"}:
        return _decision(
            "hold_fail_closed",
            ["source or target member is held/retired"],
            envelope=envelope,
            source=source,
            target=target,
        )

    effect = envelope["requested_effect"]
    if effect != "execute":
        return _decision(
            "workflow_ready",
            ["registered members may exchange bounded non-execution work; downstream domain policy still applies"],
            envelope=envelope,
            source=source,
            target=target,
        )

    reasons: list[str] = []
    if source_maturity not in EXECUTION_ELIGIBLE:
        reasons.append(f"source maturity {source_maturity!r} is not execution-eligible")
    if target_maturity not in EXECUTION_ELIGIBLE:
        reasons.append(f"target maturity {target_maturity!r} is not execution-eligible")
    if not _authority_present(envelope):
        reasons.append("execute requires both CHLOM and DAIL authority traces plus an accountable owner")
    if not _dail_write_plan_present(envelope):
        reasons.append("execute requires a canonical DAIL event plan using same_transaction or transactional_outbox")

    gate = envelope["human_gate"]
    human_required = envelope["risk_class"] in {"D2", "D3"} or gate.get("required") is True
    if human_required:
        if gate.get("required") is not True:
            reasons.append("PentaHybrid human gate must be marked required")
        elif gate.get("satisfied") is not True:
            reasons.append("PentaHybrid human gate has not been satisfied")

    if envelope["provider_effect"]:
        if not envelope.get("provider_binding_ref"):
            reasons.append("provider execution requires a certified provider binding reference")
        if not envelope.get("readback_strategy"):
            reasons.append("provider execution requires an exact readback strategy")
    elif not envelope.get("readback_strategy"):
        reasons.append("execute requires a verification/readback strategy")

    if reasons:
        return _decision(
            "governance_required",
            reasons,
            envelope=envelope,
            source=source,
            target=target,
        )
    return _decision(
        "execution_ready",
        ["all repository-level interoperability and DAIL sealing gates represented; exact domain/provider execution remains separately bounded"],
        envelope=envelope,
        source=source,
        target=target,
    )


def dependency_gaps(family_snapshot: Mapping[str, Any]) -> list[dict[str, str]]:
    members = family_snapshot.get("members")
    if not isinstance(members, Mapping):
        return [{"machine_key": "*", "dependency": "*", "reason": "family members map missing"}]
    known = set(members)
    gaps: list[dict[str, str]] = []
    for machine_key, member in sorted(members.items()):
        deps = member.get("dependencies") or []
        if not isinstance(deps, list):
            gaps.append({"machine_key": machine_key, "dependency": "*", "reason": "dependencies is not an array"})
            continue
        for dependency in deps:
            if isinstance(dependency, str) and dependency.startswith("penta.") and dependency not in known:
                gaps.append({
                    "machine_key": machine_key,
                    "dependency": dependency,
                    "reason": "registered member dependency is missing from Penta Family",
                })
    return gaps


def build_interoperability_snapshot(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    family_mod = _load_module("penta_family_interop", root / "runtime" / "penta_family.py")
    runtime_mod = _load_module("penta_runtime_suite_interop", root / "runtime" / "penta_runtime_suite.py")

    registry, family = family_mod.load_family(root)
    interop_registry = _load_json(root / "data" / "penta" / "interoperability.registry.json")
    validate_interoperability_registry(interop_registry)
    runtime_snapshot = runtime_mod.build_snapshot(root)

    family_members = set(family["members"])
    runtime_members = {row["machine_key"] for row in runtime_snapshot.get("members", [])}
    inventory_outside_family = sorted(runtime_members - family_members)
    family_without_inventory = sorted(family_members - runtime_members)
    missing_spine = sorted(REQUIRED_SPINE - family_members)
    missing_observability = sorted(REQUIRED_OBSERVABILITY - family_members)
    dependencies = dependency_gaps(family)
    provider_errors = list(runtime_snapshot.get("provider_control_plane", {}).get("contract_errors") or [])

    family_interop = registry.get("interoperability_contract")
    contract_errors: list[str] = []
    if not isinstance(family_interop, Mapping):
        contract_errors.append("family registry interoperability_contract missing")
    else:
        expected = {
            "protocol_version": PROTOCOL_VERSION,
            "registry_path": "data/penta/interoperability.registry.json",
            "envelope_schema_path": "schemas/penta/interoperability-envelope.schema.json",
            "runtime_path": "runtime/penta_interop.py",
        }
        for key, value in expected.items():
            if family_interop.get(key) != value:
                contract_errors.append(f"family interoperability_contract.{key} mismatch")
        for flag in (
            "all_registered_members_addressable",
            "unknown_members_fail_closed",
            "source_target_exact_machine_keys",
            "trace_required",
            "idempotency_required",
            "evidence_required",
            "execution_preserves_member_maturity",
            "consequential_execution_requires_authority",
            "provider_execution_requires_certified_binding_and_readback",
            "execution_requires_chlom_and_dail_authority_refs",
            "execution_requires_dail_event_plan",
            "terminal_execution_requires_dail_receipt",
        ):
            if family_interop.get(flag) is not True:
                contract_errors.append(f"family interoperability_contract.{flag} must be true")
        if set(family_interop.get("dail_write_modes") or []) != {"same_transaction", "transactional_outbox"}:
            contract_errors.append("family interoperability_contract.dail_write_modes mismatch")

    coverage = []
    for machine_key in sorted(family_members):
        member = family["members"][machine_key]
        coverage.append({
            "machine_key": machine_key,
            "canonical_name": member.get("canonical_name"),
            "maturity": member.get("maturity"),
            "execution_eligible": member.get("maturity") in EXECUTION_ELIGIBLE,
            "addressable": True,
            "portal_route": member.get("portal_route"),
            "source": member.get("source"),
        })

    blockers = {
        "inventory_outside_family": inventory_outside_family,
        "family_without_runtime_inventory": family_without_inventory,
        "missing_required_spine": missing_spine,
        "missing_required_observability": missing_observability,
        "dependency_gaps": dependencies,
        "provider_contract_errors": provider_errors,
        "family_contract_errors": contract_errors,
    }
    blocker_count = sum(len(value) for value in blockers.values())
    status = "PASS" if blocker_count == 0 else "HOLD"

    return {
        "schema": "ct.penta.interoperability-certification.v1",
        "protocol_version": PROTOCOL_VERSION,
        "status": status,
        "production_state": "production" if status == "PASS" else "hold_fail_closed",
        "truth_rule": "Repository interoperability may be certified without promoting child maturity or manufacturing authority.",
        "family_status": family.get("family_status"),
        "family_member_count": len(family_members),
        "runtime_inventory_member_count": len(runtime_members),
        "addressable_member_count": len(coverage),
        "execution_eligible_member_count": sum(1 for item in coverage if item["execution_eligible"]),
        "required_spine": sorted(REQUIRED_SPINE),
        "required_observability": sorted(REQUIRED_OBSERVABILITY),
        "coverage": coverage,
        "blockers": blockers,
        "blocker_count": blocker_count,
        "provider_control_plane": runtime_snapshot.get("provider_control_plane"),
    }


def owner_summary(snapshot: Mapping[str, Any]) -> str:
    return "\n".join([
        "Penta interoperability certification",
        f"Status: {snapshot.get('status')}",
        f"Production state: {snapshot.get('production_state')}",
        f"Family members: {snapshot.get('family_member_count')}",
        f"Addressable members: {snapshot.get('addressable_member_count')}",
        f"Execution-eligible members: {snapshot.get('execution_eligible_member_count')}",
        f"Blockers: {snapshot.get('blocker_count')}",
    ])


def _cli() -> int:
    parser = argparse.ArgumentParser(description="CrownThrive Penta Family interoperability certification")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    parser.add_argument("--certify", action="store_true")
    args = parser.parse_args()

    try:
        snapshot = build_interoperability_snapshot(Path(args.root))
    except (PentaInteropError, ValueError, OSError) as exc:
        print(json.dumps({
            "schema": "ct.penta.interoperability-certification.v1",
            "status": "HOLD",
            "production_state": "hold_fail_closed",
            "error": str(exc),
        }, indent=2, sort_keys=True))
        return 1

    text = json.dumps(snapshot, indent=2, sort_keys=True)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
    print(text)
    if args.certify:
        print(owner_summary(snapshot), file=sys.stderr)
        return 0 if snapshot["status"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
