#!/usr/bin/env python3
"""Penta OS V1.5 deterministic registry, readiness, planning, and dispatch kernel.

This kernel performs no provider or production side effects. It validates the
complete registry, reports conservative dependency readiness, verifies plans
and receipts, and emits governed handoff envelopes only after registry-derived
operation gates pass. Specialized runtimes still own execution and readback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

try:
    from runtime.penta_promotions import (
        PROMOTION_PATH,
        PentaPromotionError,
        load_promotion_manifest,
    )
except ModuleNotFoundError:
    runtime_dir = str(Path(__file__).resolve().parent)
    if runtime_dir not in sys.path:
        sys.path.insert(0, runtime_dir)
    from penta_promotions import PROMOTION_PATH, PentaPromotionError, load_promotion_manifest


AXES = {"truth", "authority", "execution", "interoperation", "continuity"}
MATURITIES = {"specified", "implemented", "certified", "production", "hold", "retired"}
EXECUTION_ELIGIBLE = {"certified", "production"}
RISK_ORDER = {"D0": 0, "D1": 1, "D2": 2, "D3": 3}
RELEASE_VERSION = "1.5.0"
SCHEMA_VERSION = "1.2.0"
SAFE_OPERATIONS = {"describe", "status", "readiness", "validate", "verify", "plan"}
UNIVERSAL_OPERATIONS = SAFE_OPERATIONS | {"dispatch"}
CONTROL_PLANE_OPERATIONS = {"batch-plan", "verify-batch-plan", "verify-plan", "verify-receipt"}
READINESS_STATES = (
    "HOLD_DEPENDENCY_INVENTORY_UNASSESSED",
    "HOLD_EXTERNAL_DEPENDENCY_UNBOUND",
    "HOLD_UNCLASSIFIED_DEPENDENCY_CYCLE",
    "HOLD_MEMBER_MATURITY",
    "HOLD_DEPENDENCY_MATURITY",
    "READY",
)
AUTHORITY_TRACE_PATTERN = r"^A[0-3]:[A-Za-z0-9][A-Za-z0-9._:@/-]{2,239}$"
REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{2,239}$")
OPERATION_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
MACHINE_KEY_PATTERN = re.compile(r"^penta\.[a-z0-9]+(?:[._-][a-z0-9]+)*$")
EXTERNAL_DEPENDENCY_PATTERN = re.compile(r"^[a-z][a-z0-9.-]{1,127}$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
MAX_PAYLOAD_BYTES = 65_536
MAX_BATCH_ITEMS = 256
REQUEST_FIELDS = {
    "machine_key", "operation", "authority_trace", "idempotency_key",
    "provider_write", "provider_binding", "readback_contract",
    "human_approval_ref", "payload",
}


class PentaOSV1Error(ValueError):
    """Raised when a Penta OS registry or command contract is invalid."""


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise PentaOSV1Error(f"value is not canonical JSON: {exc}") from exc


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PentaOSV1Error(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PentaOSV1Error(f"JSON root must be an object: {path}")
    return value


def identity_token(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def strongly_connected_components(adjacency: Mapping[str, Sequence[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for dependency in adjacency[node]:
            if dependency not in indices:
                visit(dependency)
                lowlinks[node] = min(lowlinks[node], lowlinks[dependency])
            elif dependency in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[dependency])
        if lowlinks[node] != indices[node]:
            return
        component: list[str] = []
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        components.append(sorted(component))

    for node in sorted(adjacency):
        if node not in indices:
            visit(node)
    return sorted(components, key=lambda members: tuple(members))


def transitive_closure(adjacency: Mapping[str, Sequence[str]], source: str) -> list[str]:
    seen: set[str] = set()
    pending = list(reversed(adjacency[source]))
    while pending:
        member = pending.pop()
        if member == source or member in seen:
            continue
        seen.add(member)
        pending.extend(reversed(adjacency[member]))
    return sorted(seen)


def dependency_analysis(systems: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    adjacency = {row["machine_key"]: list(row["dependencies"]) for row in systems}
    maturity = {row["machine_key"]: row["maturity"] for row in systems}
    components = strongly_connected_components(adjacency)
    component_index = {member: index for index, component in enumerate(components) for member in component}
    cyclic_components = [
        component for component in components
        if len(component) > 1 or component[0] in adjacency[component[0]]
    ]
    cycles: list[dict[str, Any]] = []
    cycle_by_member: dict[str, str] = {}
    for component in cyclic_components:
        members = sorted(component)
        edges = sorted([
            [source, target]
            for source in members
            for target in adjacency[source]
            if target in members
        ])
        cycle_id = "penta-scc-" + sha256({"members": members})[:16]
        record = {
            "cycle_id": cycle_id,
            "members": members,
            "internal_edges": edges,
            "cycle_sha256": sha256({"members": members, "edges": edges}),
            "classification": "untyped_unclassified",
        }
        cycles.append(record)
        cycle_by_member.update({member: cycle_id for member in members})

    closures = {key: transitive_closure(adjacency, key) for key in sorted(adjacency)}
    states: dict[str, tuple[str, list[str]]] = {}
    partition = Counter()
    for row in systems:
        key = row["machine_key"]
        if not row["dependency_assessed"]:
            state = "HOLD_DEPENDENCY_INVENTORY_UNASSESSED"
            blockers = ["dependency inventory is not assessed"]
        elif row["external_dependencies"]:
            state = "HOLD_EXTERNAL_DEPENDENCY_UNBOUND"
            blockers = [f"external dependency unbound: {ref}" for ref in row["external_dependencies"]]
        elif key in cycle_by_member:
            state = "HOLD_UNCLASSIFIED_DEPENDENCY_CYCLE"
            blockers = [f"unclassified dependency cycle: {cycle_by_member[key]}"]
        elif row["maturity"] not in EXECUTION_ELIGIBLE:
            state = "HOLD_MEMBER_MATURITY"
            blockers = [f"member maturity {row['maturity']} is not execution eligible"]
        else:
            held_dependencies = [member for member in closures[key] if maturity[member] not in EXECUTION_ELIGIBLE]
            if held_dependencies:
                state = "HOLD_DEPENDENCY_MATURITY"
                blockers = [f"dependency maturity hold: {member}" for member in held_dependencies]
            else:
                state = "READY"
                blockers = []
        states[key] = (state, blockers)
        partition[state] += 1

    condensed_edges = {
        (component_index[target], component_index[source])
        for source, dependencies in adjacency.items()
        for target in dependencies
        if component_index[source] != component_index[target]
    }
    graph_payload = {
        "nodes": [
            {
                "machine_key": row["machine_key"],
                "dependency_assessed": row["dependency_assessed"],
                "direct_internal": row["dependencies"],
                "direct_external": row["external_dependencies"],
                "transitive_internal": closures[row["machine_key"]],
                "cycle_id": cycle_by_member.get(row["machine_key"]),
            }
            for row in systems
        ],
        "cycles": cycles,
    }
    summary = {
        "semantic_state": "diagnostic_untyped",
        "strict_readiness_is_diagnostic": True,
        "operation_specific_verification_required": True,
        "dependency_assessed_member_count": sum(bool(row["dependency_assessed"]) for row in systems),
        "dependency_unassessed_member_count": sum(not row["dependency_assessed"] for row in systems),
        "members_with_declared_dependencies": sum(bool(row["dependencies"] or row["external_dependencies"]) for row in systems),
        "internal_edge_count": sum(len(row["dependencies"]) for row in systems),
        "external_edge_count": sum(len(row["external_dependencies"]) for row in systems),
        "external_refs": sorted({ref for row in systems for ref in row["external_dependencies"]}),
        "cyclic_scc_count": len(cycles),
        "cyclic_member_count": sum(len(record["members"]) for record in cycles),
        "cyclic_internal_edge_count": sum(len(record["internal_edges"]) for record in cycles),
        "condensed_component_count": len(components),
        "condensed_edge_count": len(condensed_edges),
        "transitive_membership_count": sum(len(closure) for closure in closures.values()),
        "maximum_transitive_closure": max(map(len, closures.values()), default=0),
        "cycles": cycles,
        "readiness_partition": {state: partition.get(state, 0) for state in READINESS_STATES},
        "graph_payload_sha256": sha256(graph_payload),
    }
    return {
        "adjacency": adjacency,
        "components": components,
        "component_index": component_index,
        "cycles": cycles,
        "cycle_by_member": cycle_by_member,
        "closures": closures,
        "states": states,
        "summary": summary,
    }


@dataclass(frozen=True)
class DispatchRequest:
    machine_key: str
    operation: str
    authority_trace: str | None = None
    idempotency_key: str | None = None
    provider_write: bool = False
    provider_binding: str | None = None
    readback_contract: str | None = None
    human_approval_ref: str | None = None
    payload: Mapping[str, Any] | None = None


class PentaOSV1:
    def __init__(self, root: Path, registry: Mapping[str, Any] | None = None):
        self.root = Path(root).resolve()
        self.registry = dict(registry) if registry is not None else load_json(self.root / "data/penta/os-v1.registry.json")
        self.members: dict[str, dict[str, Any]] = {}
        self.alias_index: dict[str, str] = {}
        self.policy_index: dict[str, dict[str, Any]] = {}
        self.analysis: dict[str, Any] = {}
        self.validate()

    def _validate_operation_policy(self, members: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        policy = self.registry.get("operation_policy")
        if not isinstance(policy, dict):
            raise PentaOSV1Error("operation_policy must be an object")
        if policy.get("schema") != "crownthrive.penta.os-v1.operation-policies.v1":
            raise PentaOSV1Error("unexpected operation-policy schema")
        if policy.get("policy_version") != RELEASE_VERSION or policy.get("default_disposition") != "HOLD_UNKNOWN_OPERATION":
            raise PentaOSV1Error("unsafe operation-policy version or default")
        if policy.get("authority_trace_pattern") != AUTHORITY_TRACE_PATTERN:
            raise PentaOSV1Error("unsafe authority trace policy")
        policies = policy.get("policies")
        if not isinstance(policies, list) or not policies:
            raise PentaOSV1Error("operation policies must be a non-empty array")
        index: dict[str, dict[str, Any]] = {}
        effects = {"read", "local_compute", "local_write_handoff", "provider_write", "destructive_handoff"}
        for value in policies:
            if not isinstance(value, dict):
                raise PentaOSV1Error("operation policy entries must be objects")
            operation = value.get("operation")
            if not isinstance(operation, str) or not OPERATION_PATTERN.fullmatch(operation):
                raise PentaOSV1Error(f"invalid specialized operation: {operation!r}")
            if operation in UNIVERSAL_OPERATIONS or operation in index:
                raise PentaOSV1Error(f"duplicate or reserved specialized operation: {operation}")
            scope = value.get("scope")
            machine_keys = value.get("machine_keys")
            if scope not in {"all_members", "machine_keys"} or not isinstance(machine_keys, list):
                raise PentaOSV1Error(f"invalid operation scope: {operation}")
            if (
                any(not isinstance(key, str) for key in machine_keys)
                or machine_keys != sorted(machine_keys)
                or len(machine_keys) != len(set(machine_keys))
                or any(key not in members for key in machine_keys)
            ):
                raise PentaOSV1Error(f"operation has duplicate or unknown machine keys: {operation}")
            if (scope == "all_members" and machine_keys) or (scope == "machine_keys" and not machine_keys):
                raise PentaOSV1Error(f"operation scope/machine-key mismatch: {operation}")
            if value.get("effect") not in effects or value.get("risk_class") not in {"D0", "D1", "D2", "D3"}:
                raise PentaOSV1Error(f"invalid operation effect/risk: {operation}")
            if value.get("minimum_authority") not in {"A0", "A1", "A2", "A3"}:
                raise PentaOSV1Error(f"invalid operation authority: {operation}")
            flags = ("dependency_ready_required", "human_approval_required", "provider_binding_required", "readback_required")
            if any(type(value.get(flag)) is not bool for flag in flags):
                raise PentaOSV1Error(f"operation-policy flags must be booleans: {operation}")
            if value["effect"] == "provider_write" and not (value["provider_binding_required"] and value["readback_required"]):
                raise PentaOSV1Error(f"provider-write policy must require binding/readback: {operation}")
            if value["risk_class"] == "D3" and not value["human_approval_required"]:
                raise PentaOSV1Error(f"D3 operation must require human approval: {operation}")
            index[operation] = value
        if self.registry.get("operation_policy_sha256") != sha256(policy):
            raise PentaOSV1Error("operation-policy digest mismatch")
        return index

    def validate(self, *, verify_sources: bool = True) -> dict[str, Any]:
        registry = self.registry
        if registry.get("registry_id") != "crownthrive.penta.os-v1":
            raise PentaOSV1Error("unexpected registry_id")
        if registry.get("version") != RELEASE_VERSION or registry.get("schema_version") != SCHEMA_VERSION:
            raise PentaOSV1Error("unexpected Penta OS product or schema version")
        if set(registry.get("axes", [])) != AXES:
            raise PentaOSV1Error("registry must declare exactly the five Penta axes")
        if set(registry.get("operations", [])) != UNIVERSAL_OPERATIONS:
            raise PentaOSV1Error("unexpected universal operation contract")
        if set(registry.get("control_plane_operations", [])) != CONTROL_PLANE_OPERATIONS:
            raise PentaOSV1Error("unexpected control-plane operation contract")
        if registry.get("production_certification") != "HOLD":
            raise PentaOSV1Error("Penta OS V1.5 production certification must remain HOLD")
        if registry.get("promotion_registry") != "data/penta/production-promotions.v1.json":
            raise PentaOSV1Error("unexpected or missing maturity promotion registry")
        if registry.get("provider_state_promotion_authorized") is not False:
            raise PentaOSV1Error("Penta OS may not authorize provider-state promotion")
        try:
            promotion_manifest = load_promotion_manifest(self.root, required=True)
        except PentaPromotionError as exc:
            raise PentaOSV1Error(f"invalid canonical maturity promotion registry: {exc}") from exc
        canonical_promotions = {
            item["machine_key"]: {
                "promotion_id": item["promotion_id"],
                "from_maturity": item["from_maturity"],
                "to_maturity": item["to_maturity"],
                "effective_at": item["effective_at"],
                "authority_ref": item["authority_ref"],
                "evidence_bindings": item["evidence_bindings"],
                "runtime_refs": item["runtime_refs"],
                "scope": item["scope"],
                "provider_state_disposition": item["provider_state_disposition"],
                "provider_effect_authorized": item["provider_effect_authorized"],
                "self_certification_authorized": item["self_certification_authorized"],
                "promotion_registry": str(PROMOTION_PATH),
            }
            for item in promotion_manifest["promotions"]
        }

        systems = registry.get("systems")
        if not isinstance(systems, list) or not systems:
            raise PentaOSV1Error("systems must be a non-empty array")
        members: dict[str, dict[str, Any]] = {}
        canonical_names: dict[str, str] = {}
        operator_routes: set[str] = set()
        public_routes: set[str] = set()
        for index, value in enumerate(systems):
            if not isinstance(value, dict):
                raise PentaOSV1Error(f"system {index} must be an object")
            key = value.get("machine_key")
            name = value.get("canonical_name")
            if not isinstance(key, str) or not MACHINE_KEY_PATTERN.fullmatch(key):
                raise PentaOSV1Error(f"invalid machine key at system {index}: {key!r}")
            if not isinstance(name, str) or not name.startswith("Penta"):
                raise PentaOSV1Error(f"invalid canonical name for {key}: {name!r}")
            normalized_name = identity_token(name)
            if key in members or normalized_name in canonical_names:
                raise PentaOSV1Error(f"duplicate Penta identity: {key} / {name}")
            canonical_names[normalized_name] = key
            if value.get("axis") not in AXES or value.get("maturity") not in MATURITIES:
                raise PentaOSV1Error(f"invalid axis or maturity for {key}")
            promotion = value.get("maturity_promotion")
            catalog_maturity = value.get("catalog_maturity")
            if (promotion is None) is not (catalog_maturity is None):
                raise PentaOSV1Error(f"promotion lineage/catalog maturity mismatch for {key}")
            if promotion is not None:
                required_promotion_fields = {
                    "promotion_id", "from_maturity", "to_maturity", "effective_at",
                    "authority_ref", "evidence_bindings", "runtime_refs", "scope",
                    "provider_state_disposition", "provider_effect_authorized",
                    "self_certification_authorized", "promotion_registry",
                }
                if not isinstance(promotion, dict) or set(promotion) != required_promotion_fields:
                    raise PentaOSV1Error(f"invalid maturity promotion shape for {key}")
                if catalog_maturity not in MATURITIES:
                    raise PentaOSV1Error(f"invalid catalog maturity for {key}")
                if promotion["from_maturity"] != catalog_maturity or promotion["to_maturity"] != value["maturity"]:
                    raise PentaOSV1Error(f"promotion maturity lineage mismatch for {key}")
                if value["maturity"] not in EXECUTION_ELIGIBLE or value["maturity"] == catalog_maturity:
                    raise PentaOSV1Error(f"invalid effective promotion maturity for {key}")
                if promotion["provider_state_disposition"] != "UNCHANGED_SEPARATELY_GATED":
                    raise PentaOSV1Error(f"provider state is not separately gated for {key}")
                if promotion["provider_effect_authorized"] is not False:
                    raise PentaOSV1Error(f"provider effect may not be authorized by promotion for {key}")
                if promotion["self_certification_authorized"] is not False:
                    raise PentaOSV1Error(f"self-certification may not be authorized for {key}")
                if promotion["promotion_registry"] != registry["promotion_registry"]:
                    raise PentaOSV1Error(f"promotion registry lineage mismatch for {key}")
                bindings = promotion["evidence_bindings"]
                runtime_refs = promotion["runtime_refs"]
                if not isinstance(bindings, list) or not bindings:
                    raise PentaOSV1Error(f"promotion evidence bindings missing for {key}")
                if (
                    not isinstance(runtime_refs, list)
                    or not runtime_refs
                    or any(not isinstance(ref, str) or not ref for ref in runtime_refs)
                    or len(runtime_refs) != len(set(runtime_refs))
                ):
                    raise PentaOSV1Error(f"invalid promotion runtime references for {key}")
                for binding in bindings:
                    if (
                        not isinstance(binding, dict)
                        or set(binding) != {"path", "sha256", "claim"}
                        or not isinstance(binding["path"], str)
                        or not SHA256_PATTERN.fullmatch(binding["sha256"])
                        or not isinstance(binding["claim"], str)
                        or not binding["claim"]
                    ):
                        raise PentaOSV1Error(f"invalid promotion evidence binding for {key}")
            if value.get("kind") not in {"system", "primitive", "layer", "subcomponent"}:
                raise PentaOSV1Error(f"invalid kind for {key}")
            if value.get("risk_ceiling") not in {"D0", "D1", "D2", "D3"}:
                raise PentaOSV1Error(f"invalid risk ceiling for {key}")
            if value.get("execution_eligible_by_registry") is not (value["maturity"] in EXECUTION_ELIGIBLE):
                raise PentaOSV1Error(f"eligibility/maturity mismatch for {key}")
            if set(value.get("addressable_operations", [])) != UNIVERSAL_OPERATIONS:
                raise PentaOSV1Error(f"incomplete operation contract for {key}")
            operator_route = value.get("operator_route")
            public_route = value.get("public_status_route")
            if not isinstance(operator_route, str) or not operator_route.startswith("/io/pentas/"):
                raise PentaOSV1Error(f"invalid operator route for {key}")
            if not isinstance(public_route, str) or not public_route.startswith("/penta/"):
                raise PentaOSV1Error(f"invalid public route for {key}")
            if operator_route in operator_routes or public_route in public_routes:
                raise PentaOSV1Error(f"duplicate route for {key}")
            operator_routes.add(operator_route)
            public_routes.add(public_route)
            if type(value.get("dependency_assessed")) is not bool:
                raise PentaOSV1Error(f"dependency_assessed must be boolean for {key}")
            sequences = {
                "dependencies": value.get("dependencies"),
                "external_dependencies": value.get("external_dependencies"),
                "transitive_dependencies": value.get("transitive_dependencies"),
                "strict_readiness_blockers": value.get("strict_readiness_blockers"),
            }
            for field, sequence in sequences.items():
                if (
                    not isinstance(sequence, list)
                    or any(not isinstance(item, str) for item in sequence)
                    or sequence != sorted(sequence)
                    or len(sequence) != len(set(sequence))
                ):
                    raise PentaOSV1Error(f"{field} must be a sorted unique array for {key}")
            if any(not isinstance(dependency, str) or not dependency.startswith("penta.") for dependency in sequences["dependencies"]):
                raise PentaOSV1Error(f"invalid Penta dependency for {key}")
            if any(not isinstance(dependency, str) or not EXTERNAL_DEPENDENCY_PATTERN.fullmatch(dependency) for dependency in sequences["external_dependencies"]):
                raise PentaOSV1Error(f"invalid external dependency for {key}")
            expected_state = (
                "unassessed" if not value["dependency_assessed"] else
                "assessed_with_dependencies" if sequences["dependencies"] or sequences["external_dependencies"] else
                "assessed_no_dependencies"
            )
            if value.get("dependency_state") != expected_state:
                raise PentaOSV1Error(f"dependency state mismatch for {key}")
            expected_external = "declared_unverified" if sequences["external_dependencies"] else "not_declared"
            if value.get("external_dependency_state") != expected_external:
                raise PentaOSV1Error(f"external dependency state mismatch for {key}")
            if value.get("strict_readiness_state") not in READINESS_STATES:
                raise PentaOSV1Error(f"invalid strict readiness for {key}")
            members[key] = value

        embedded_promotions = {
            key: value["maturity_promotion"]
            for key, value in members.items()
            if "maturity_promotion" in value
        }
        if embedded_promotions != canonical_promotions:
            raise PentaOSV1Error(
                "embedded maturity promotion lineage does not exactly match canonical registry"
            )

        for key, value in members.items():
            parent = value.get("parent_machine_key")
            if parent is not None and parent not in members:
                raise PentaOSV1Error(f"unknown parent {parent} for {key}")
            facets = value.get("facets", [])
            if not isinstance(facets, list) or any(not isinstance(facet, dict) for facet in facets):
                raise PentaOSV1Error(f"facets must be objects for {key}")
            for facet in facets:
                if facet.get("parent_machine_key") not in members:
                    raise PentaOSV1Error(f"unknown facet parent for {key}")
            for dependency in value["dependencies"]:
                if dependency not in members or dependency == key:
                    raise PentaOSV1Error(f"unresolved or self Penta dependency for {key}: {dependency}")

        actual_systems_digest = sha256(systems)
        if registry.get("systems_sha256") != actual_systems_digest:
            raise PentaOSV1Error("systems digest mismatch")
        analysis = dependency_analysis(systems)
        for key, value in members.items():
            expected_state, expected_blockers = analysis["states"][key]
            if value["transitive_dependencies"] != analysis["closures"][key]:
                raise PentaOSV1Error(f"transitive dependency closure mismatch for {key}")
            if value.get("dependency_cycle_id") != analysis["cycle_by_member"].get(key):
                raise PentaOSV1Error(f"dependency cycle identity mismatch for {key}")
            if value["strict_readiness_state"] != expected_state or value["strict_readiness_blockers"] != expected_blockers:
                raise PentaOSV1Error(f"strict readiness mismatch for {key}")
        if registry.get("dependency_graph") != analysis["summary"]:
            raise PentaOSV1Error("dependency graph summary mismatch")
        if registry.get("dependency_graph_sha256") != sha256(analysis["summary"]):
            raise PentaOSV1Error("dependency graph digest mismatch")

        counts = registry.get("counts")
        if not isinstance(counts, dict):
            raise PentaOSV1Error("counts must be an object")
        expected_counts = {
            "total": len(systems),
            "systems": sum(row["kind"] == "system" for row in systems),
            "layers": sum(row["kind"] == "layer" for row in systems),
            "subcomponents": sum(row["kind"] == "subcomponent" for row in systems),
            "primitives": sum(row["kind"] == "primitive" for row in systems),
            "execution_eligible_by_registry": sum(row["execution_eligible_by_registry"] for row in systems),
            "dependency_assessed_members": analysis["summary"]["dependency_assessed_member_count"],
            "dependency_unassessed_members": analysis["summary"]["dependency_unassessed_member_count"],
            "members_with_declared_edges": analysis["summary"]["members_with_declared_dependencies"],
            "penta_dependency_edges": analysis["summary"]["internal_edge_count"],
            "external_dependency_edges": analysis["summary"]["external_edge_count"],
            "unresolved_penta_dependencies": 0,
            "cyclic_sccs": analysis["summary"]["cyclic_scc_count"],
            "cyclic_members": analysis["summary"]["cyclic_member_count"],
            "strict_readiness_ready": analysis["summary"]["readiness_partition"]["READY"],
        }
        for field, expected in expected_counts.items():
            if counts.get(field) != expected:
                raise PentaOSV1Error(f"registry count mismatch: {field}")
        if counts.get("evidence_bound_maturity_promotions") != sum(
            "maturity_promotion" in row for row in systems
        ):
            raise PentaOSV1Error("registry count mismatch: evidence_bound_maturity_promotions")
        if counts.get("by_strict_readiness") != analysis["summary"]["readiness_partition"]:
            raise PentaOSV1Error("strict readiness partition mismatch")

        policy_index = self._validate_operation_policy(members)
        aliases = registry.get("aliases")
        if not isinstance(aliases, list):
            raise PentaOSV1Error("aliases must be an array")
        alias_index: dict[str, str] = {}
        for alias in aliases:
            if not isinstance(alias, dict):
                raise PentaOSV1Error("alias entries must be objects")
            target = alias.get("canonical_machine_key")
            normalized = identity_token(alias.get("alias", "")) if isinstance(alias.get("alias"), str) else ""
            if target not in members or not normalized or normalized in alias_index:
                raise PentaOSV1Error("aliases must be unique and target a current member")
            if normalized in canonical_names and canonical_names[normalized] != target:
                raise PentaOSV1Error("alias shadows a canonical identity")
            alias_index[normalized] = target
        for key, value in members.items():
            member_aliases = value.get("aliases", [])
            if not isinstance(member_aliases, list) or any(not isinstance(alias, str) for alias in member_aliases):
                raise PentaOSV1Error(f"member aliases must be strings for {key}")
            for alias in member_aliases:
                if alias_index.get(identity_token(alias)) != key:
                    raise PentaOSV1Error(f"member alias missing from canonical alias table: {alias}")

        release_gate_codes = registry.get("release_gate_codes")
        if (
            not isinstance(release_gate_codes, list)
            or not release_gate_codes
            or any(not isinstance(code, str) for code in release_gate_codes)
            or release_gate_codes != sorted(release_gate_codes)
            or len(release_gate_codes) != len(set(release_gate_codes))
        ):
            raise PentaOSV1Error("release_gate_codes must be a sorted non-empty unique array")
        sources = registry.get("source_digests_sha256")
        if not isinstance(sources, dict) or not sources:
            raise PentaOSV1Error("source_digests_sha256 must be a non-empty object")
        for rel, expected in sources.items():
            if not isinstance(rel, str) or not isinstance(expected, str) or not SHA256_PATTERN.fullmatch(expected):
                raise PentaOSV1Error("invalid source digest entry")
            pure = PurePosixPath(rel)
            if pure.is_absolute() or ".." in pure.parts or "\\" in rel:
                raise PentaOSV1Error(f"unsafe registry source path: {rel}")
            if verify_sources:
                path = (self.root / Path(*pure.parts)).resolve()
                if not path.is_relative_to(self.root) or not path.is_file():
                    raise PentaOSV1Error(f"registry source missing or outside root: {rel}")
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise PentaOSV1Error(f"registry source drift: {rel}")
        if registry["promotion_registry"] not in sources:
            raise PentaOSV1Error("promotion registry is not source-digest bound")
        for key, value in members.items():
            promotion = value.get("maturity_promotion")
            if promotion is None:
                continue
            evidence_paths = value.get("evidence_paths")
            registry_sources = value.get("registry_sources")
            if not isinstance(evidence_paths, list) or not isinstance(registry_sources, list):
                raise PentaOSV1Error(f"promotion evidence/source arrays missing for {key}")
            required_sources = {
                registry["promotion_registry"],
                *promotion["runtime_refs"],
                *(binding["path"] for binding in promotion["evidence_bindings"]),
            }
            if not required_sources.issubset(set(registry_sources)):
                raise PentaOSV1Error(f"promotion source closure incomplete for {key}")
            for binding in promotion["evidence_bindings"]:
                if binding["path"] not in evidence_paths:
                    raise PentaOSV1Error(f"promotion evidence path missing from member for {key}")
                if sources.get(binding["path"]) != binding["sha256"]:
                    raise PentaOSV1Error(f"promotion evidence digest lineage mismatch for {key}")

        expected_registry_digest = registry.get("registry_sha256")
        if not isinstance(expected_registry_digest, str) or not SHA256_PATTERN.fullmatch(expected_registry_digest):
            raise PentaOSV1Error("invalid full registry digest")
        registry_body = {key: value for key, value in registry.items() if key != "registry_sha256"}
        if sha256(registry_body) != expected_registry_digest:
            raise PentaOSV1Error("full registry digest mismatch")

        self.members = members
        self.alias_index = alias_index
        self.policy_index = policy_index
        self.analysis = analysis
        return {
            "valid": True,
            "registry_id": registry["registry_id"],
            "version": registry["version"],
            "schema_version": registry["schema_version"],
            "member_count": len(members),
            "systems_sha256": actual_systems_digest,
            "dependency_graph_sha256": registry["dependency_graph_sha256"],
            "operation_policy_sha256": registry["operation_policy_sha256"],
            "registry_sha256": registry["registry_sha256"],
            "readiness_partition": analysis["summary"]["readiness_partition"],
            "production_certification": "HOLD",
            "evidence_bound_maturity_promotions": counts["evidence_bound_maturity_promotions"],
            "provider_state_promotion_authorized": False,
            "source_integrity_checked": verify_sources,
        }

    def resolve(self, identity: str) -> dict[str, Any]:
        if not isinstance(identity, str) or not identity.strip() or len(identity) > 240:
            raise PentaOSV1Error("Penta identity must be a non-empty string")
        if identity in self.members:
            return self.members[identity]
        normalized = identity_token(identity)
        if normalized in self.alias_index:
            return self.members[self.alias_index[normalized]]
        matches = [row for row in self.members.values() if identity_token(row["canonical_name"]) == normalized]
        if len(matches) == 1:
            return matches[0]
        raise PentaOSV1Error(f"unknown Penta identity: {identity}")

    def list_members(self, *, axis: str | None = None, maturity: str | None = None) -> list[dict[str, Any]]:
        if axis is not None and axis not in AXES:
            raise PentaOSV1Error(f"invalid axis: {axis}")
        if maturity is not None and maturity not in MATURITIES:
            raise PentaOSV1Error(f"invalid maturity: {maturity}")
        return [self.members[key] for key in sorted(self.members)
                if (axis is None or self.members[key]["axis"] == axis)
                and (maturity is None or self.members[key]["maturity"] == maturity)]

    def describe(self, identity: str) -> dict[str, Any]:
        row = self.resolve(identity)
        return {
            "schema": "crownthrive.penta.description.v1",
            "registry_version": self.registry["version"],
            "registry_sha256": self.registry["registry_sha256"],
            "member": dict(row),
            "production_certification_granted": False,
            "side_effect_performed": False,
        }

    def readiness(self, identity: str) -> dict[str, Any]:
        row = self.resolve(identity)
        cycle = next((record for record in self.analysis["cycles"]
                      if record["cycle_id"] == row.get("dependency_cycle_id")), None)
        return {
            "schema": "crownthrive.penta.readiness.v1",
            "registry_version": self.registry["version"],
            "registry_sha256": self.registry["registry_sha256"],
            "dependency_graph_sha256": self.registry["dependency_graph_sha256"],
            "machine_key": row["machine_key"],
            "canonical_name": row["canonical_name"],
            "dependency_semantics": "diagnostic_untyped",
            "structural_state": "CLOSED" if row["dependency_assessed"] else "UNASSESSED",
            "registry_gate": "READY_FOR_DOWNSTREAM_GATES" if row["execution_eligible_by_registry"] else "HOLD_FAIL_CLOSED",
            "strict_readiness_state": row["strict_readiness_state"],
            "strict_ready": row["strict_readiness_state"] == "READY",
            "direct_internal": row["dependencies"],
            "direct_external": row["external_dependencies"],
            "transitive_internal": row["transitive_dependencies"],
            "cycle": cycle,
            "blockers": row["strict_readiness_blockers"],
            "operation_specific_verification_required": True,
            "provider_effect_verified": False,
            "production_certification_granted": False,
            "side_effect_performed": False,
        }

    def status(self, identity: str) -> dict[str, Any]:
        row = self.resolve(identity)
        return {
            "schema": "crownthrive.penta.status.v1",
            "machine_key": row["machine_key"],
            "canonical_name": row["canonical_name"],
            "version": self.registry["version"],
            "registry_state": row["registration_state"],
            "maturity": row["maturity"],
            "execution_eligible_by_registry": row["execution_eligible_by_registry"],
            "overall_state": "READY_FOR_DOWNSTREAM_GATES" if row["execution_eligible_by_registry"] else "HOLD_FAIL_CLOSED",
            "strict_readiness_state": row["strict_readiness_state"],
            "risk_ceiling": row["risk_ceiling"],
            "axis": row["axis"],
            "dependencies": row["dependencies"],
            "external_dependencies": row["external_dependencies"],
            "dependency_state": row["dependency_state"],
            "routes": {"operator": row["operator_route"], "public_status": row["public_status_route"], "docs": row["docs_route"]},
            "authority_invariant": self.registry["authority_invariant"],
            "systems_sha256": self.registry["systems_sha256"],
            "registry_sha256": self.registry["registry_sha256"],
            "dependency_graph_sha256": self.registry["dependency_graph_sha256"],
        }

    def verification_receipt(self, identity: str | None = None) -> dict[str, Any]:
        validation = self.validate()
        body: dict[str, Any] = {
            "schema": "crownthrive.penta.verification-receipt.v1",
            "runtime_version": RELEASE_VERSION,
            "registry_id": self.registry["registry_id"],
            "registry_version": self.registry["version"],
            "registry_sha256": self.registry["registry_sha256"],
            "systems_sha256": self.registry["systems_sha256"],
            "dependency_graph_sha256": self.registry["dependency_graph_sha256"],
            "operation_policy_sha256": self.registry["operation_policy_sha256"],
            "effective_date": self.registry["effective_date"],
            "scope": "registry" if identity is None else "member",
            "subject": self.registry["registry_id"],
            "subject_sha256": self.registry["registry_sha256"],
            "registry_integrity": "PASS",
            "source_integrity": "PASS" if validation["source_integrity_checked"] else "NOT_CHECKED",
            "production_certification": "HOLD",
            "release_gate_codes": list(self.registry["release_gate_codes"]),
            "provider_effect_verified": False,
            "production_certification_granted": False,
            "promotion_performed": False,
            "side_effect_performed": False,
        }
        if identity is not None:
            row = self.resolve(identity)
            body.update({
                "subject": row["machine_key"], "subject_sha256": sha256(row),
                "canonical_name": row["canonical_name"], "maturity": row["maturity"],
                "execution_eligible_by_registry": row["execution_eligible_by_registry"],
                "strict_readiness_state": row["strict_readiness_state"],
                "disposition": "PASS_REPOSITORY_VERIFIED" if row["strict_readiness_state"] == "READY" else "HOLD_RECORDED",
            })
        else:
            body["disposition"] = "PASS_REPOSITORY_VERIFIED"
        body["receipt_id"] = "pvr-" + sha256(body)[:24]
        return {**body, "receipt_sha256": sha256(body)}

    def verify_receipt(self, receipt: Mapping[str, Any]) -> dict[str, Any]:
        reasons: list[str] = []
        if not isinstance(receipt, Mapping):
            return {"valid": False, "disposition": "HOLD_FAIL_CLOSED", "reasons": ["receipt must be an object"]}
        value = dict(receipt)
        expected_hash = value.pop("receipt_sha256", None)
        try:
            actual_hash = sha256(value)
        except PentaOSV1Error as exc:
            actual_hash = None
            reasons.append(f"receipt is not canonical JSON: {exc}")
        if not isinstance(expected_hash, str) or not SHA256_PATTERN.fullmatch(expected_hash) or actual_hash != expected_hash:
            reasons.append("receipt SHA-256 is missing or invalid")
        receipt_id = value.pop("receipt_id", None)
        try:
            expected_receipt_id = "pvr-" + sha256(value)[:24]
        except PentaOSV1Error:
            expected_receipt_id = None
        if receipt_id != expected_receipt_id:
            reasons.append("receipt identity is missing or invalid")
        if value.get("schema") != "crownthrive.penta.verification-receipt.v1":
            reasons.append("unexpected receipt schema")
        for field, expected in (
            ("runtime_version", RELEASE_VERSION), ("registry_id", self.registry["registry_id"]),
            ("registry_version", self.registry["version"]), ("registry_sha256", self.registry["registry_sha256"]),
            ("systems_sha256", self.registry["systems_sha256"]),
            ("dependency_graph_sha256", self.registry["dependency_graph_sha256"]),
            ("operation_policy_sha256", self.registry["operation_policy_sha256"]),
        ):
            if value.get(field) != expected:
                reasons.append(f"receipt {field} is stale or invalid")
        scope = value.get("scope")
        if scope == "registry":
            if value.get("subject") != self.registry["registry_id"] or value.get("subject_sha256") != self.registry["registry_sha256"]:
                reasons.append("registry receipt subject binding is invalid")
            expected_disposition = "PASS_REPOSITORY_VERIFIED"
        elif scope == "member":
            try:
                row = self.resolve(value.get("subject"))
            except PentaOSV1Error:
                reasons.append("member receipt subject is unknown")
                row = None
            if row is not None and value.get("subject_sha256") != sha256(row):
                reasons.append("member receipt subject digest is stale or invalid")
            expected_disposition = "PASS_REPOSITORY_VERIFIED" if row is not None and row["strict_readiness_state"] == "READY" else "HOLD_RECORDED"
        else:
            reasons.append("receipt scope is invalid")
            expected_disposition = None
        if expected_disposition is not None and value.get("disposition") != expected_disposition:
            reasons.append("receipt disposition does not match current truth")
        for field in ("provider_effect_verified", "production_certification_granted", "promotion_performed", "side_effect_performed"):
            if value.get(field) is not False:
                reasons.append(f"receipt boundary {field} must remain false")
        return {
            "valid": not reasons,
            "disposition": "PASS_REPOSITORY_VERIFIED" if not reasons else "HOLD_FAIL_CLOSED",
            "receipt_sha256": expected_hash,
            "reasons": reasons or ["receipt hash and exact-current registry bindings verified"],
        }

    def _optional_reference(self, value: Any, field: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not REFERENCE_PATTERN.fullmatch(value):
            raise PentaOSV1Error(f"{field} must be a bounded reference string")
        return value

    def normalize_request(self, request: DispatchRequest) -> dict[str, Any]:
        if not isinstance(request, DispatchRequest):
            raise PentaOSV1Error("request must be a DispatchRequest")
        if not isinstance(request.machine_key, str) or not request.machine_key.strip() or len(request.machine_key) > 240:
            raise PentaOSV1Error("machine_key must be a bounded identity string")
        if not isinstance(request.operation, str) or not OPERATION_PATTERN.fullmatch(request.operation):
            raise PentaOSV1Error("operation must be a canonical specialized-operation identifier")
        if type(request.provider_write) is not bool:
            raise PentaOSV1Error("provider_write must be a boolean")
        authority_trace = self._optional_reference(request.authority_trace, "authority_trace")
        if authority_trace is not None and re.fullmatch(AUTHORITY_TRACE_PATTERN, authority_trace) is None:
            raise PentaOSV1Error("authority_trace must satisfy the governed A0-A3 contract")
        if request.payload is not None and not isinstance(request.payload, Mapping):
            raise PentaOSV1Error("payload must be an object")
        payload = dict(request.payload or {})
        if any(not isinstance(key, str) for key in payload):
            raise PentaOSV1Error("payload keys must be strings")
        if len(canonical_json(payload).encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise PentaOSV1Error(f"payload exceeds {MAX_PAYLOAD_BYTES} canonical bytes")
        normalized = {
            "machine_key": request.machine_key,
            "operation": request.operation,
            "authority_trace": authority_trace,
            "idempotency_key": self._optional_reference(request.idempotency_key, "idempotency_key"),
            "provider_write": request.provider_write,
            "provider_binding": self._optional_reference(request.provider_binding, "provider_binding"),
            "readback_contract": self._optional_reference(request.readback_contract, "readback_contract"),
            "human_approval_ref": self._optional_reference(request.human_approval_ref, "human_approval_ref"),
            "payload": payload,
        }
        try:
            normalized["machine_key"] = self.resolve(request.machine_key)["machine_key"]
        except PentaOSV1Error:
            pass
        return normalized

    def gate_dispatch(self, request: DispatchRequest) -> dict[str, Any]:
        try:
            normalized = self.normalize_request(request)
        except PentaOSV1Error as exc:
            return {"eligible": False, "disposition": "HOLD_FAIL_CLOSED",
                    "machine_key": getattr(request, "machine_key", None),
                    "operation": getattr(request, "operation", None), "reasons": [str(exc)]}
        try:
            row = self.resolve(normalized["machine_key"])
        except PentaOSV1Error as exc:
            return {"eligible": False, "disposition": "HOLD_FAIL_CLOSED",
                    "machine_key": normalized["machine_key"], "operation": normalized["operation"], "reasons": [str(exc)]}
        reasons: list[str] = []
        policy = self.policy_index.get(normalized["operation"])
        if policy is None:
            reasons.append(f"unknown operation; {self.registry['operation_policy']['default_disposition']}")
        elif policy["scope"] == "machine_keys" and row["machine_key"] not in policy["machine_keys"]:
            reasons.append("operation policy does not authorize this member")
        if not row["execution_eligible_by_registry"]:
            reasons.append(f"registry maturity {row['maturity']} is not execution eligible")
        if normalized["authority_trace"] is None:
            reasons.append("authority_trace is required")
        elif policy is not None and int(normalized["authority_trace"][1]) < int(policy["minimum_authority"][1]):
            reasons.append(f"operation requires minimum authority {policy['minimum_authority']}")
        if normalized["idempotency_key"] is None:
            reasons.append("idempotency_key is required")
        if policy is not None:
            if RISK_ORDER[policy["risk_class"]] > RISK_ORDER[row["risk_ceiling"]]:
                reasons.append(
                    f"operation risk {policy['risk_class']} exceeds member ceiling {row['risk_ceiling']}"
                )
            if policy["dependency_ready_required"] and row["strict_readiness_state"] != "READY":
                reasons.append(f"operation requires strict dependency readiness; state is {row['strict_readiness_state']}")
            if policy["human_approval_required"] and normalized["human_approval_ref"] is None:
                reasons.append("operation requires an explicit human_approval_ref")
            if policy["effect"] == "provider_write" and not normalized["provider_write"]:
                reasons.append("provider-write operation requires provider_write=true")
            if policy["effect"] != "provider_write" and normalized["provider_write"]:
                reasons.append("provider_write is not permitted by the selected operation policy")
            if policy["provider_binding_required"] and normalized["provider_binding"] is None:
                reasons.append("operation requires an exact provider_binding")
            if policy["readback_required"] and normalized["readback_contract"] is None:
                reasons.append("operation requires an exact readback_contract")
        return {
            "eligible": not reasons,
            "disposition": "READY_FOR_SPECIALIZED_EXECUTOR" if not reasons else "HOLD_FAIL_CLOSED",
            "machine_key": row["machine_key"], "operation": normalized["operation"],
            "operation_policy": policy, "request_sha256": sha256(normalized),
            "risk_ceiling": row["risk_ceiling"], "strict_readiness_state": row["strict_readiness_state"],
            "reasons": reasons or ["registry gate passed; specialized execution and provider readback remain required"],
        }

    def plan(self, request: DispatchRequest) -> dict[str, Any]:
        normalized = self.normalize_request(request)
        gate = self.gate_dispatch(request)
        row = self.members.get(normalized["machine_key"])
        body = {
            "schema": "crownthrive.penta.plan.v1", "runtime_version": RELEASE_VERSION,
            "registry_version": self.registry["version"], "registry_sha256": self.registry["registry_sha256"],
            "dependency_graph_sha256": self.registry["dependency_graph_sha256"],
            "operation_policy_sha256": self.registry["operation_policy_sha256"],
            "request": normalized, "request_sha256": sha256(normalized),
            "five_stage": ["discover", "govern", "execute", "verify", "preserve"],
            "dependency_closure": None if row is None else {
                "semantic_state": "diagnostic_untyped", "strict_readiness_state": row["strict_readiness_state"],
                "direct_internal": row["dependencies"], "direct_external": row["external_dependencies"],
                "transitive_internal": row["transitive_dependencies"], "cycle_id": row.get("dependency_cycle_id"),
                "blockers": row["strict_readiness_blockers"],
            },
            "gate": gate, "provider_effect_performed": False,
            "production_certification_granted": False, "side_effect_performed": False,
        }
        return {**body, "plan_sha256": sha256(body)}

    def verify_plan(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        reasons: list[str] = []
        if not isinstance(plan, Mapping):
            return {"valid": False, "disposition": "HOLD_FAIL_CLOSED", "reasons": ["plan must be an object"]}
        value = dict(plan)
        expected_hash = value.pop("plan_sha256", None)
        try:
            actual_hash = sha256(value)
        except PentaOSV1Error as exc:
            actual_hash = None
            reasons.append(f"plan is not canonical JSON: {exc}")
        if not isinstance(expected_hash, str) or not SHA256_PATTERN.fullmatch(expected_hash) or actual_hash != expected_hash:
            reasons.append("plan SHA-256 is missing or invalid")
        if value.get("schema") != "crownthrive.penta.plan.v1":
            reasons.append("unexpected plan schema")
        if value.get("registry_sha256") != self.registry["registry_sha256"]:
            reasons.append("plan registry binding is stale or invalid")
        request = value.get("request")
        try:
            recomputed = self.plan(request_from_mapping(request)) if isinstance(request, Mapping) else None
        except PentaOSV1Error as exc:
            reasons.append(f"plan request is invalid: {exc}")
            recomputed = None
        if recomputed is None or recomputed != dict(plan):
            reasons.append("plan does not match the deterministic current-registry evaluation")
        return {"valid": not reasons, "disposition": "PASS_REPOSITORY_VERIFIED" if not reasons else "HOLD_FAIL_CLOSED",
                "plan_sha256": expected_hash,
                "reasons": reasons or ["plan hash and exact-current deterministic evaluation verified"]}

    def _component_ranks(self) -> dict[str, int]:
        components = self.analysis["components"]
        component_index = self.analysis["component_index"]
        outgoing: dict[int, set[int]] = {index: set() for index in range(len(components))}
        indegree = {index: 0 for index in range(len(components))}
        for source, dependencies in self.analysis["adjacency"].items():
            source_component = component_index[source]
            for dependency in dependencies:
                dependency_component = component_index[dependency]
                if source_component == dependency_component or source_component in outgoing[dependency_component]:
                    continue
                outgoing[dependency_component].add(source_component)
                indegree[source_component] += 1
        pending = sorted((index for index, degree in indegree.items() if degree == 0), key=lambda item: tuple(components[item]))
        ranks: dict[int, int] = {}
        rank = 0
        while pending:
            current, pending = pending, []
            for component in current:
                ranks[component] = rank
                for target in sorted(outgoing[component], key=lambda item: tuple(components[item])):
                    indegree[target] -= 1
                    if indegree[target] == 0:
                        pending.append(target)
            pending = sorted(set(pending), key=lambda item: tuple(components[item]))
            rank += 1
        if len(ranks) != len(components):
            raise PentaOSV1Error("condensed dependency graph is unexpectedly cyclic")
        return {member: ranks[component_index[member]] for member in self.members}

    def batch_plan(self, requests: Sequence[DispatchRequest]) -> dict[str, Any]:
        if not isinstance(requests, Sequence) or isinstance(requests, (str, bytes)) or not requests:
            raise PentaOSV1Error("batch plan requires at least one request")
        if len(requests) > MAX_BATCH_ITEMS:
            raise PentaOSV1Error(f"batch plan exceeds {MAX_BATCH_ITEMS} items")
        plans = [self.plan(request) for request in requests]
        ranks = self._component_ranks()
        plans.sort(key=lambda item: (ranks.get(item["request"]["machine_key"], 10**9),
                                     item["request"]["machine_key"], item["request"].get("idempotency_key") or "",
                                     item["request_sha256"]))
        keys = [plan["request"].get("idempotency_key") for plan in plans]
        present_keys = [key for key in keys if key is not None]
        duplicate_keys = sorted(key for key, count in Counter(present_keys).items() if count > 1)
        reasons: list[str] = []
        if len(present_keys) != len(plans):
            reasons.append("every batch item requires an idempotency_key")
        if duplicate_keys:
            reasons.append("duplicate batch idempotency keys: " + ", ".join(duplicate_keys))
        held = [plan["request"]["machine_key"] for plan in plans if not plan["gate"]["eligible"]]
        if held:
            reasons.append("held batch members: " + ", ".join(sorted(held)))
        stage_map: dict[int, list[dict[str, Any]]] = {}
        for plan in plans:
            key = plan["request"]["machine_key"]
            stage_map.setdefault(ranks.get(key, 10**9), []).append({
                "machine_key": key, "operation": plan["request"]["operation"],
                "request_sha256": plan["request_sha256"],
                "cycle_id": self.members.get(key, {}).get("dependency_cycle_id"),
            })
        stages = [{"stage": ordinal, "graph_rank": rank, "items": stage_map[rank]}
                  for ordinal, rank in enumerate(sorted(stage_map), start=1)]
        body = {
            "schema": "crownthrive.penta.batch-plan.v1", "runtime_version": RELEASE_VERSION,
            "registry_sha256": self.registry["registry_sha256"],
            "dependency_graph_sha256": self.registry["dependency_graph_sha256"],
            "operation_policy_sha256": self.registry["operation_policy_sha256"],
            "all_or_none_gate": True, "atomic_execution_performed": False,
            "item_count": len(plans), "items": plans, "stages": stages,
            "eligible": not reasons,
            "disposition": "READY_FOR_SPECIALIZED_EXECUTORS" if not reasons else "HOLD_FAIL_CLOSED",
            "reasons": reasons or ["all registry gates passed; specialized execution and provider readback remain required"],
            "provider_effect_performed": False, "production_certification_granted": False,
            "side_effect_performed": False,
        }
        return {**body, "batch_sha256": sha256(body)}

    def verify_batch_plan(self, batch: Mapping[str, Any]) -> dict[str, Any]:
        reasons: list[str] = []
        if not isinstance(batch, Mapping):
            return {"valid": False, "disposition": "HOLD_FAIL_CLOSED", "reasons": ["batch plan must be an object"]}
        value = dict(batch)
        expected_hash = value.pop("batch_sha256", None)
        try:
            actual_hash = sha256(value)
        except PentaOSV1Error as exc:
            actual_hash = None
            reasons.append(f"batch plan is not canonical JSON: {exc}")
        if not isinstance(expected_hash, str) or not SHA256_PATTERN.fullmatch(expected_hash) or actual_hash != expected_hash:
            reasons.append("batch-plan SHA-256 is missing or invalid")
        if value.get("schema") != "crownthrive.penta.batch-plan.v1":
            reasons.append("unexpected batch-plan schema")
        plans = value.get("items")
        try:
            requests = [request_from_mapping(plan["request"]) for plan in plans] if isinstance(plans, list) else []
            recomputed = self.batch_plan(requests) if requests else None
        except (KeyError, TypeError, PentaOSV1Error) as exc:
            reasons.append(f"batch-plan requests are invalid: {exc}")
            recomputed = None
        if recomputed is None or recomputed != dict(batch):
            reasons.append("batch plan does not match the deterministic current-registry evaluation")
        return {"valid": not reasons, "disposition": "PASS_REPOSITORY_VERIFIED" if not reasons else "HOLD_FAIL_CLOSED",
                "batch_sha256": expected_hash,
                "reasons": reasons or ["batch-plan hash and exact-current deterministic evaluation verified"]}

    def dispatch_envelope(self, request: DispatchRequest) -> dict[str, Any]:
        normalized = self.normalize_request(request)
        gate = self.gate_dispatch(request)
        if not gate["eligible"]:
            raise PentaOSV1Error("dispatch held: " + "; ".join(gate["reasons"]))
        row = self.resolve(normalized["machine_key"])
        body = {
            "schema": "crownthrive.penta.dispatch-envelope.v1", "registry_version": self.registry["version"],
            "registry_sha256": self.registry["registry_sha256"], "systems_sha256": self.registry["systems_sha256"],
            "dependency_graph_sha256": self.registry["dependency_graph_sha256"],
            "operation_policy_sha256": self.registry["operation_policy_sha256"],
            "request": normalized, "request_sha256": sha256(normalized),
            "operation_policy": gate["operation_policy"], "strict_readiness_state": row["strict_readiness_state"],
            "disposition": "READY_FOR_SPECIALIZED_EXECUTOR", "provider_effect_performed": False,
            "production_certification_granted": False, "side_effect_performed": False,
        }
        return {**body, "envelope_sha256": sha256(body)}


def request_from_mapping(value: Mapping[str, Any]) -> DispatchRequest:
    if not isinstance(value, Mapping):
        raise PentaOSV1Error("request must be an object")
    unknown = set(value) - REQUEST_FIELDS
    if unknown:
        raise PentaOSV1Error("unknown request fields: " + ", ".join(sorted(unknown)))
    if "machine_key" not in value or "operation" not in value:
        raise PentaOSV1Error("request requires machine_key and operation")
    provider_write = value.get("provider_write", False)
    if type(provider_write) is not bool:
        raise PentaOSV1Error("provider_write must be a boolean")
    payload = value.get("payload", {})
    if not isinstance(payload, Mapping):
        raise PentaOSV1Error("request payload must be an object")
    return DispatchRequest(
        machine_key=value["machine_key"], operation=value["operation"], authority_trace=value.get("authority_trace"),
        idempotency_key=value.get("idempotency_key"), provider_write=provider_write,
        provider_binding=value.get("provider_binding"), readback_contract=value.get("readback_contract"),
        human_approval_ref=value.get("human_approval_ref"), payload=payload,
    )


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))


def parse_object(raw: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PentaOSV1Error(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise PentaOSV1Error(f"{label} must be a JSON object")
    canonical_json(value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Penta OS V1.5 registry, readiness, verification, planning, and dispatch kernel")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--version", action="version", version=RELEASE_VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    list_parser = sub.add_parser("list")
    list_parser.add_argument("--axis", choices=sorted(AXES))
    list_parser.add_argument("--maturity", choices=sorted(MATURITIES))
    for name in ("describe", "status", "readiness"):
        command = sub.add_parser(name)
        command.add_argument("identity")
    sub.add_parser("validate")
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("identity", nargs="?")
    batch_parser = sub.add_parser("batch-plan")
    batch_parser.add_argument("--requests-json", required=True)
    verify_receipt_parser = sub.add_parser("verify-receipt")
    verify_receipt_parser.add_argument("--receipt-json", required=True)
    verify_plan_parser = sub.add_parser("verify-plan")
    verify_plan_parser.add_argument("--plan-json", required=True)
    verify_batch_parser = sub.add_parser("verify-batch-plan")
    verify_batch_parser.add_argument("--batch-json", required=True)
    for name in ("plan", "dispatch"):
        command = sub.add_parser(name)
        command.add_argument("identity")
        command.add_argument("--operation", required=True)
        command.add_argument("--authority-trace")
        command.add_argument("--idempotency-key")
        command.add_argument("--provider-write", action="store_true")
        command.add_argument("--provider-binding")
        command.add_argument("--readback-contract")
        command.add_argument("--human-approval-ref")
        command.add_argument("--payload-json", default="{}")
    args = parser.parse_args()
    runtime = PentaOSV1(args.root)
    if args.command == "list":
        rows = runtime.list_members(axis=args.axis, maturity=args.maturity)
        emit({"count": len(rows), "members": rows})
    elif args.command == "describe":
        emit(runtime.describe(args.identity))
    elif args.command == "status":
        emit(runtime.status(args.identity))
    elif args.command == "readiness":
        emit(runtime.readiness(args.identity))
    elif args.command == "validate":
        emit(runtime.validate())
    elif args.command == "verify":
        emit(runtime.verification_receipt(args.identity))
    elif args.command == "batch-plan":
        try:
            values = json.loads(args.requests_json)
        except json.JSONDecodeError as exc:
            raise PentaOSV1Error(f"requests-json must be valid JSON: {exc}") from exc
        if not isinstance(values, list):
            raise PentaOSV1Error("requests-json must be an array of request objects")
        emit(runtime.batch_plan([request_from_mapping(value) for value in values]))
    elif args.command == "verify-receipt":
        result = runtime.verify_receipt(parse_object(args.receipt_json, "receipt-json"))
        emit(result)
        return 0 if result["valid"] else 1
    elif args.command == "verify-plan":
        result = runtime.verify_plan(parse_object(args.plan_json, "plan-json"))
        emit(result)
        return 0 if result["valid"] else 1
    elif args.command == "verify-batch-plan":
        result = runtime.verify_batch_plan(parse_object(args.batch_json, "batch-json"))
        emit(result)
        return 0 if result["valid"] else 1
    else:
        payload = parse_object(args.payload_json, "payload-json")
        request = DispatchRequest(
            machine_key=args.identity, operation=args.operation, authority_trace=args.authority_trace,
            idempotency_key=args.idempotency_key, provider_write=args.provider_write,
            provider_binding=args.provider_binding, readback_contract=args.readback_contract,
            human_approval_ref=args.human_approval_ref, payload=payload,
        )
        emit(runtime.plan(request) if args.command == "plan" else runtime.dispatch_envelope(request))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
