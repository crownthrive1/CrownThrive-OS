#!/usr/bin/env python3
"""Build the deterministic Penta OS V1.5 union registry and PentaDocs census.

The builder reconciles the institutional Markdown registry, production-family
catalogs, component registry, public service registry, and governed discovery
intake. It never infers certification or production maturity from a name.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from runtime.penta_promotions import (
        PROMOTION_PATH,
        PentaPromotionError,
        apply_promotions,
    )
except ModuleNotFoundError:
    runtime_dir = str(Path(__file__).resolve().parents[1] / "runtime")
    if runtime_dir not in sys.path:
        sys.path.insert(0, runtime_dir)
    from penta_promotions import PROMOTION_PATH, PentaPromotionError, apply_promotions


AXES = ("truth", "authority", "execution", "interoperation", "continuity")
EXECUTION_ELIGIBLE = {"certified", "production"}
MATURITY_ORDER = {"specified": 0, "implemented": 1, "certified": 2, "production": 3, "hold": -1, "retired": -2}
GENERATED_DATE = "2026-08-26"
RELEASE_VERSION = "1.5.0"
SCHEMA_VERSION = "1.2.0"
ADDRESSABLE_OPERATIONS = ["describe", "status", "readiness", "validate", "verify", "plan", "dispatch"]
MACHINE_KEY_PATTERN = re.compile(r"^penta\.[a-z0-9]+(?:[._-][a-z0-9]+)*$")
OPERATION_POLICY_PATH = Path("data/penta/os-v1.operation-policies.json")
FAMILY_REGISTRY_PATH = Path("data/penta/family.registry.json")
READINESS_STATES = (
    "HOLD_DEPENDENCY_INVENTORY_UNASSESSED",
    "HOLD_EXTERNAL_DEPENDENCY_UNBOUND",
    "HOLD_UNCLASSIFIED_DEPENDENCY_CYCLE",
    "HOLD_MEMBER_MATURITY",
    "HOLD_DEPENDENCY_MATURITY",
    "READY",
)
RELEASE_GATE_CODES = [
    "governed_merge_and_exact_head_ci",
    "migration_source_custody_and_clean_replay",
    "provider_execution_queue_and_scheduler_reliability",
    "production_receipts_for_release_scoped_members",
    "command_center_deployment_and_exact_source_readback",
    "institutional_recovery_and_current_cie_assurance",
]
REGISTRY_PATH = Path("data/penta/os-v1.registry.json")
DOCS_PATH = Path("automation/penta-os-v1.mdx")
CANONICAL_NAME_OVERRIDES = {
    "pentacontrol": "PentaControl",
    "pentamcp": "PentaMCP",
    "pentaworkforceos": "PentaWorkforceOS",
}
TRUE_ALIASES = {
    "PentaOS": ["CrownThrive OS"],
    "PentaControl": ["Penta Control"],
    "PentaMCP": ["Penta MCP"],
    "PentaFederation": ["Penta Federation"],
    "PentaFactory": ["PentaFramework Factory", "Software Factory v2", "Software Factory v3", "Software Factory v4"],
    "PentaScribe": ["Penta Scribe"],
    "PentaMarketer": ["Penta Marketer"],
    "PentaGreen": ["ThriveEvergreen"],
    "PentaAgents": ["PentaAgentic"],
    "PentaMCL": ["PentaML"],
    "PentaSecure": ["PentaSecure Layer"],
    "PentaFabric": ["Penta Fabric", "Pentafabric"],
    "PentaMesh": ["Penta Mesh"],
    "PentaBeata": ["Penta Beata"],
    "PentaHeartbeat": ["Penta Heartbeat"],
    "PentaMetric": ["PentaMetrics"],
    "PentaProcure": ["PentaProcurement"],
    "PentaVendor": ["PentaVendors"],
    "PentaLicense": ["PentaLicensing"],
    "PentaBenefits": ["PentaBenfits"],
    "PentaRFA": ["Penta Request for Agent"],
    "PentaOD": ["Penta On Demand"],
    "PentaSnapshot": ["PentaSnapShot"],
    "PentaHarvestor": ["PentaHarvester"],
    "PentaWorkforceOS": ["PentaWorkforce OS"],
}
RELATIONSHIPS = {
    "PentaDocs": [
        {"type": "documentation_provider", "name": "Mintlify"},
        {"type": "documentation_surface", "name": "Help Center"},
    ],
    "PentaBase": [
        {"type": "runtime_data_service", "name": "ThriveBase"},
        {"type": "provider", "name": "Supabase"},
    ],
    "PentaMaps": [{"type": "design_provider", "name": "Canva"}],
}


class PentaOSBuildError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise PentaOSBuildError(f"value is not canonical JSON: {exc}") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PentaOSBuildError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PentaOSBuildError(f"JSON root must be an object: {path}")
    return value


def strongly_connected_components(adjacency: dict[str, list[str]]) -> list[list[str]]:
    """Return deterministic SCC membership for an exact machine-key graph."""
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
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


def transitive_closure(adjacency: dict[str, list[str]], source: str) -> list[str]:
    seen: set[str] = set()
    pending = list(reversed(adjacency[source]))
    while pending:
        member = pending.pop()
        if member == source or member in seen:
            continue
        seen.add(member)
        pending.extend(reversed(adjacency[member]))
    return sorted(seen)


def token(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def strip_mark(value: str) -> str:
    return value.replace("™", "").strip()


def slug_for(name: str) -> str:
    value = strip_mark(name)
    value = re.sub(r"^Penta\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+OS$", "", value, flags=re.IGNORECASE) or "os"
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "os"


def machine_key_for(name: str, route: str | None = None) -> str:
    if route:
        suffix = route.rstrip("/").split("/")[-1]
        if suffix and suffix not in {"pentas", "primitives"}:
            return "penta." + suffix.replace("-", ".")
    return "penta." + slug_for(name).replace("-", ".")


def infer_axis(name: str, role: str) -> str:
    haystack = f"{name} {role}".casefold()
    rules = {
        "authority": ("authority", "governance", "policy", "legal", "security", "secure", "privacy", "compliance", "risk", "audit", "license", "rights", "ofac", "credential", "board", "director", "vault", "contract", "boundary"),
        "continuity": ("continuity", "succession", "archive", "rollback", "restore", "backup", "snapshot", "version", "serialized", "sop", "sla", "health", "nurture", "temporal", "time", "recovery", "benefit"),
        "interoperation": ("interoper", "federation", "fabric", "mesh", "route", "transport", "wire", "binding", "bind", "mcp", "http", "request primitive", "event relay", "fetch"),
        "truth": ("truth", "documentation", "knowledge", "record", "evidence", "status", "report", "result", "data", "map", "topology", "glossar", "format", "query", "search", "read", "parse", "validate"),
    }
    for axis in ("authority", "continuity", "interoperation", "truth"):
        if any(word in haystack for word in rules[axis]):
            return axis
    return "execution"


def parse_institutional_registry(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("| Penta | Institutional role | Canonical portal |"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|---"):
            continue
        if not line.startswith("|"):
            break
        fields = [field.strip() for field in line.strip().strip("|").split("|")]
        if len(fields) != 3:
            raise PentaOSBuildError(f"invalid institutional registry row: {line}")
        name, role, route = fields
        name = strip_mark(name)
        route = route.strip("`")
        rows.append({
            "canonical_name": name,
            "machine_key": machine_key_for(name, route),
            "role": role,
            "operator_route": route,
            "axis": infer_axis(name, role),
            "maturity": "specified",
            "risk_ceiling": "D3",
            "source": "PENTA-FAMILY-REGISTRY.md",
            "source_kind": "institutional_registry",
        })

    primitive_match = re.search(r"family also includes registered capability primitives such as \*\*(.+?)\*\*\.", text)
    if not primitive_match:
        raise PentaOSBuildError("registered primitive list not found")
    for name in re.findall(r"Penta[A-Za-z0-9]+", primitive_match.group(1)):
        role = "Governed capability primitive under PentaRoute and the universal Penta OS contract."
        rows.append({
            "canonical_name": name,
            "machine_key": machine_key_for(name),
            "role": role,
            "operator_route": f"/io/pentas/primitives#{slug_for(name)}",
            "axis": infer_axis(name, role),
            "maturity": "specified",
            "risk_ceiling": "D2",
            "source": "PENTA-FAMILY-REGISTRY.md",
            "source_kind": "registered_primitive",
            "kind": "primitive",
        })
    return rows


def family_members(root: Path) -> list[dict[str, Any]]:
    family_path = root / FAMILY_REGISTRY_PATH
    family = read_json(family_path)
    catalog_members: dict[str, dict[str, Any]] = {}
    catalog_sources: dict[str, str] = {}
    for ref in family.get("catalogs", []):
        rel = Path(ref["path"])
        catalog = read_json(root / rel)
        for item in catalog.get("systems", []):
            machine_key = item.get("machine_key")
            if not isinstance(machine_key, str):
                raise PentaOSBuildError(f"family catalog member has no machine_key: {rel}")
            if machine_key in catalog_members:
                raise PentaOSBuildError(
                    f"duplicate family machine_key {machine_key}: "
                    f"{catalog_sources[machine_key]} and {rel}"
                )
            catalog_members[machine_key] = dict(item)
            catalog_sources[machine_key] = str(rel)

    try:
        effective_members, promotions = apply_promotions(
            root,
            catalog_members,
            required=True,
        )
    except PentaPromotionError as exc:
        raise PentaOSBuildError(f"invalid evidence-bound family promotion: {exc}") from exc

    rows: list[dict[str, Any]] = []
    for machine_key in sorted(effective_members):
        row = dict(effective_members[machine_key])
        axis_is_explicit = row.get("axis") in AXES
        promotion = promotions.get(machine_key)
        evidence_paths = [
            binding["path"] for binding in promotion.get("evidence_bindings", [])
        ] if promotion else []
        additional_sources = (
            [str(PROMOTION_PATH), *evidence_paths, *promotion.get("runtime_refs", [])]
            if promotion else []
        )
        row.update({
            "source": catalog_sources[machine_key],
            "source_kind": "production_family_catalog",
            "additional_registry_sources": additional_sources,
            "evidence_paths": sorted(set(row.get("evidence_paths", [])) | set(evidence_paths)),
            "dependency_assessed": "dependencies" in row,
            "operator_route": f"/io/pentas/{machine_key.split('.', 1)[1]}",
            "axis": row.get("axis") or infer_axis(row.get("canonical_name", ""), row.get("purpose", "")),
            "axis_is_explicit": axis_is_explicit,
            "role": row.get("purpose", ""),
        })
        rows.append(row)
    return rows


def component_members(root: Path) -> list[dict[str, Any]]:
    rel = Path("penta/registry/penta-component-registry.v1.json")
    registry = read_json(root / rel)
    rows: list[dict[str, Any]] = []
    for item in registry.get("components", []):
        rows.append({
            "machine_key": item["key"],
            "canonical_name": item["name"],
            "role": item["role"],
            "axis": item["axis"],
            "contract": item.get("contract"),
            "aliases": item.get("aliases", []),
            "maturity": "specified",
            "risk_ceiling": "D3",
            "operator_route": f"/io/pentas/{item['key'].split('.', 1)[1]}",
            "source": str(rel),
            "source_kind": "component_registry",
        })
        for primitive in item.get("primitives", []):
            rows.append({
                "machine_key": machine_key_for(primitive),
                "canonical_name": primitive,
                "role": f"Governed {item['name']} capability primitive.",
                "axis": item["axis"],
                "maturity": "specified",
                "risk_ceiling": "D2",
                "operator_route": f"/io/pentas/primitives#{slug_for(primitive)}",
                "source": str(rel),
                "source_kind": "component_primitive",
                "kind": "primitive",
            })
    return rows


def public_services(root: Path) -> list[dict[str, Any]]:
    rel = Path("penta-family/registry.public.json")
    registry = read_json(root / rel)
    rows = []
    for item in registry.get("services", []):
        rows.append({
            "machine_key": machine_key_for(item["id"]),
            "canonical_name": item["id"],
            "role": item["role"],
            "axis": infer_axis(item["id"], item["role"]),
            "maturity": "specified",
            "risk_ceiling": "D2",
            "operator_route": f"/io/pentas/{slug_for(item['id'])}",
            "source": str(rel),
            "source_kind": "public_service_registry",
        })
    return rows


def discovery_members(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rel = Path("data/penta/os-v1.discoveries.json")
    registry = read_json(root / rel)
    rows = []
    for item in registry.get("systems", []):
        row = dict(item)
        if row.get("parent_machine_key") == "penta.green" and not row.get("contract"):
            row["contract"] = f"ct.pentagreen.{row['machine_key'].split('.', 1)[1]}.v1"
        row.update({
            "operator_route": f"/io/pentas/{row['machine_key'].split('.', 1)[1]}",
            "source": str(rel),
            "source_kind": "governed_discovery",
        })
        rows.append(row)
    return rows, registry.get("aliases", [])


def merge_rows(rows: list[dict[str, Any]], aliases: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_token: dict[str, dict[str, Any]] = {}
    for incoming in rows:
        machine_key = incoming.get("machine_key")
        if not isinstance(machine_key, str) or not MACHINE_KEY_PATTERN.fullmatch(machine_key):
            raise PentaOSBuildError(f"invalid machine key: {machine_key!r}")
        incoming_aliases = incoming.get("aliases", [])
        if not isinstance(incoming_aliases, list) or any(
            not isinstance(alias, str) or not alias.strip() for alias in incoming_aliases
        ):
            raise PentaOSBuildError(f"invalid source aliases for {incoming['machine_key']}")
        name_token = token(incoming["canonical_name"])
        current = by_token.get(name_token)
        if current is None:
            current = {
                "machine_key": incoming["machine_key"],
                "canonical_name": CANONICAL_NAME_OVERRIDES.get(token(incoming["canonical_name"]), strip_mark(incoming["canonical_name"])),
                "kind": incoming.get("kind", "system"),
                "parent_machine_key": incoming.get("parent_machine_key"),
                "role": incoming.get("role") or incoming.get("purpose") or "Governed Penta subsystem.",
                "axis": incoming.get("axis") or infer_axis(incoming["canonical_name"], incoming.get("role", "")),
                "maturity": incoming.get("maturity", "specified"),
                "risk_ceiling": incoming.get("risk_ceiling", "D3"),
                "aliases": sorted({strip_mark(alias) for alias in incoming_aliases}),
                "contracts": sorted({incoming["contract"]} if incoming.get("contract") else set()),
                "dependencies": sorted(set(incoming.get("dependencies", []))),
                "dependency_assessed": incoming.get("dependency_assessed") is True,
                "registry_sources": sorted({
                    incoming["source"],
                    *incoming.get("additional_registry_sources", []),
                }),
                "source_kinds": [incoming["source_kind"]],
                "evidence_paths": sorted(set(incoming.get("evidence_paths", []))),
                "operator_route": incoming.get("operator_route") or f"/io/pentas/{slug_for(incoming['canonical_name'])}",
                "intake_state": incoming.get("intake_state"),
                "explicit_registration_state": incoming.get("registration_state"),
                "catalog_maturity": incoming.get("catalog_maturity"),
                "maturity_promotion": incoming.get("maturity_promotion"),
            }
            by_token[name_token] = current
            continue

        if current["machine_key"] != incoming["machine_key"]:
            # Route spellings can differ while the canonical display identity is the same.
            current.setdefault("machine_key_aliases", []).append(incoming["machine_key"])
        if MATURITY_ORDER.get(incoming.get("maturity", "specified"), -99) > MATURITY_ORDER.get(current["maturity"], -99):
            current["maturity"] = incoming["maturity"]
        if incoming.get("source_kind") == "production_family_catalog":
            current["machine_key"] = incoming["machine_key"]
            current["canonical_name"] = CANONICAL_NAME_OVERRIDES.get(token(incoming["canonical_name"]), strip_mark(incoming["canonical_name"]))
            current["role"] = incoming.get("role") or current["role"]
            current["risk_ceiling"] = incoming.get("risk_ceiling", current["risk_ceiling"])
            if incoming.get("axis_is_explicit"):
                current["axis"] = incoming["axis"]
        elif incoming.get("source_kind") == "institutional_registry":
            current["operator_route"] = incoming["operator_route"]
            current["axis"] = incoming.get("axis", current["axis"])
        elif incoming.get("source_kind") == "governed_discovery" and "production_family_catalog" not in current["source_kinds"]:
            # An explicit discovery ceiling is stronger than a synthetic/default
            # ceiling. Full semantic precedence is limited to evidence-backed
            # runtime or macro-layer records so candidate prose cannot overwrite
            # a newer technical component contract.
            current["risk_ceiling"] = incoming.get("risk_ceiling", current["risk_ceiling"])
            discovery_is_macro_layer = incoming.get("registration_state") == "macro_layer"
            discovery_is_authoritative = incoming.get("intake_state") == "evidence_backed_runtime" or discovery_is_macro_layer
            if discovery_is_authoritative:
                current["role"] = incoming.get("role") or current["role"]
                current["axis"] = incoming.get("axis", current["axis"])
                if discovery_is_macro_layer and incoming.get("kind"):
                    current["kind"] = incoming["kind"]
        if incoming.get("axis") in AXES and "component_registry" in {incoming.get("source_kind"), *current["source_kinds"]} and not (
            incoming.get("source_kind") == "governed_discovery"
            and (
                incoming.get("intake_state") == "evidence_backed_runtime"
                or incoming.get("registration_state") == "macro_layer"
            )
        ):
            current["axis"] = incoming.get("axis", current["axis"])
        current["contracts"] = sorted(set(current["contracts"]) | ({incoming["contract"]} if incoming.get("contract") else set()))
        current["aliases"] = sorted(set(current["aliases"]) | {strip_mark(alias) for alias in incoming_aliases})
        current["dependencies"] = sorted(set(current["dependencies"]) | set(incoming.get("dependencies", [])))
        current["dependency_assessed"] = current["dependency_assessed"] or incoming.get("dependency_assessed") is True
        current["registry_sources"] = sorted(
            set(current["registry_sources"])
            | {incoming["source"]}
            | set(incoming.get("additional_registry_sources", []))
        )
        current["source_kinds"] = sorted(set(current["source_kinds"]) | {incoming["source_kind"]})
        current["evidence_paths"] = sorted(set(current["evidence_paths"]) | set(incoming.get("evidence_paths", [])))
        current["intake_state"] = current.get("intake_state") or incoming.get("intake_state")
        current["parent_machine_key"] = current.get("parent_machine_key") or incoming.get("parent_machine_key")
        current["explicit_registration_state"] = current.get("explicit_registration_state") or incoming.get("registration_state")
        if incoming.get("maturity_promotion") is not None:
            existing_promotion = current.get("maturity_promotion")
            if existing_promotion is not None and existing_promotion != incoming["maturity_promotion"]:
                raise PentaOSBuildError(
                    f"conflicting maturity promotion for {incoming['machine_key']}"
                )
            current["catalog_maturity"] = incoming.get("catalog_maturity")
            current["maturity_promotion"] = incoming["maturity_promotion"]

    canonical_key_owner: dict[str, str] = {}
    systems: list[dict[str, Any]] = []
    for row in by_token.values():
        key = row["machine_key"]
        if key in canonical_key_owner and canonical_key_owner[key] != row["canonical_name"]:
            raise PentaOSBuildError(f"duplicate machine key {key}: {canonical_key_owner[key]} and {row['canonical_name']}")
        canonical_key_owner[key] = row["canonical_name"]
        row["axis"] = row["axis"] if row["axis"] in AXES else infer_axis(row["canonical_name"], row["role"])
        row["canonical_name"] = CANONICAL_NAME_OVERRIDES.get(token(row["canonical_name"]), row["canonical_name"])
        row["aliases"] = sorted(
            set(row["aliases"]) | set(TRUE_ALIASES.get(row["canonical_name"], []))
        )
        if row["canonical_name"] in RELATIONSHIPS:
            row["relationships"] = RELATIONSHIPS[row["canonical_name"]]
        row["docs_route"] = "/automation/penta-os-v1"
        row["public_status_route"] = f"/penta/{key.split('.', 1)[1]}"
        row["addressable_operations"] = list(ADDRESSABLE_OPERATIONS)
        row["execution_eligible_by_registry"] = row["maturity"] in {"certified", "production"}
        row["registration_state"] = row.pop("explicit_registration_state", None) or (
            "family_registered" if "production_family_catalog" in row["source_kinds"] else
            "institutional_registered" if "institutional_registry" in row["source_kinds"] else
            "documented_subcomponent" if row["kind"] == "subcomponent" else
            "discovered_implemented" if row["maturity"] == "implemented" else
            "candidate"
        )
        if not row.get("parent_machine_key"):
            row.pop("parent_machine_key", None)
        elif row["kind"] != "subcomponent":
            row["facets"] = [{
                "kind": "subcomponent",
                "parent_machine_key": row.pop("parent_machine_key"),
                "contracts": list(row["contracts"]),
            }]
        if not row.get("intake_state"):
            row.pop("intake_state", None)
        if not row.get("machine_key_aliases"):
            row.pop("machine_key_aliases", None)
        else:
            row["machine_key_aliases"] = sorted(set(row["machine_key_aliases"]))
        if row.get("maturity_promotion") is None:
            row.pop("catalog_maturity", None)
            row.pop("maturity_promotion", None)
        systems.append(row)

    systems = sorted(systems, key=lambda item: item["machine_key"])
    known_keys = {row["machine_key"] for row in systems}
    for row in systems:
        penta_dependencies: set[str] = set()
        external_dependencies: set[str] = set()
        for dependency in row.pop("dependencies", []):
            if not isinstance(dependency, str) or not dependency or dependency.strip() != dependency:
                raise PentaOSBuildError(f"invalid dependency for {row['machine_key']}: {dependency!r}")
            if dependency.startswith("penta."):
                if dependency not in known_keys:
                    raise PentaOSBuildError(f"unknown Penta dependency {dependency} for {row['machine_key']}")
                if dependency == row["machine_key"]:
                    raise PentaOSBuildError(f"self dependency {dependency} for {row['machine_key']}")
                penta_dependencies.add(dependency)
            else:
                if not re.fullmatch(r"[a-z][a-z0-9.-]{1,127}", dependency):
                    raise PentaOSBuildError(f"invalid external dependency {dependency!r} for {row['machine_key']}")
                external_dependencies.add(dependency)
        row["dependencies"] = sorted(penta_dependencies)
        row["external_dependencies"] = sorted(external_dependencies)
        row["dependency_state"] = (
            "unassessed" if not row["dependency_assessed"] else
            "assessed_with_dependencies" if penta_dependencies or external_dependencies else
            "assessed_no_dependencies"
        )
        row["external_dependency_state"] = "declared_unverified" if external_dependencies else "not_declared"
    return systems


def load_operation_policy(root: Path, known_keys: set[str]) -> dict[str, Any]:
    policy = read_json(root / OPERATION_POLICY_PATH)
    if policy.get("schema") != "crownthrive.penta.os-v1.operation-policies.v1":
        raise PentaOSBuildError("unexpected operation-policy schema")
    if policy.get("policy_version") != RELEASE_VERSION:
        raise PentaOSBuildError("operation-policy version must match the Penta OS release")
    if policy.get("default_disposition") != "HOLD_UNKNOWN_OPERATION":
        raise PentaOSBuildError("unknown operations must fail closed")
    if policy.get("authority_trace_pattern") != r"^A[0-3]:[A-Za-z0-9][A-Za-z0-9._:@/-]{2,239}$":
        raise PentaOSBuildError("authority trace pattern must remain the governed A0-A3 contract")
    policies = policy.get("policies")
    if not isinstance(policies, list) or not policies:
        raise PentaOSBuildError("operation policies must be a non-empty array")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    effects = {"read", "local_compute", "local_write_handoff", "provider_write", "destructive_handoff"}
    for item in policies:
        if not isinstance(item, dict):
            raise PentaOSBuildError("operation policy entries must be objects")
        operation = item.get("operation")
        if not isinstance(operation, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", operation):
            raise PentaOSBuildError(f"invalid specialized operation: {operation!r}")
        if operation in ADDRESSABLE_OPERATIONS or operation in seen:
            raise PentaOSBuildError(f"duplicate or reserved specialized operation: {operation}")
        seen.add(operation)
        scope = item.get("scope")
        machine_keys = item.get("machine_keys")
        if scope not in {"all_members", "machine_keys"}:
            raise PentaOSBuildError(f"invalid operation scope for {operation}")
        if not isinstance(machine_keys, list) or any(not isinstance(key, str) for key in machine_keys):
            raise PentaOSBuildError(f"machine_keys must be an array for {operation}")
        if len(machine_keys) != len(set(machine_keys)) or any(key not in known_keys for key in machine_keys):
            raise PentaOSBuildError(f"operation policy contains duplicate or unknown machine key: {operation}")
        if (scope == "all_members" and machine_keys) or (scope == "machine_keys" and not machine_keys):
            raise PentaOSBuildError(f"operation scope/machine_keys mismatch for {operation}")
        if item.get("effect") not in effects:
            raise PentaOSBuildError(f"invalid operation effect for {operation}")
        if item.get("risk_class") not in {"D0", "D1", "D2", "D3"}:
            raise PentaOSBuildError(f"invalid operation risk for {operation}")
        if item.get("minimum_authority") not in {"A0", "A1", "A2", "A3"}:
            raise PentaOSBuildError(f"invalid minimum authority for {operation}")
        flags = (
            "dependency_ready_required",
            "human_approval_required",
            "provider_binding_required",
            "readback_required",
        )
        if any(type(item.get(flag)) is not bool for flag in flags):
            raise PentaOSBuildError(f"operation-policy flags must be booleans for {operation}")
        if item["effect"] == "provider_write" and not (
            item["provider_binding_required"] and item["readback_required"]
        ):
            raise PentaOSBuildError(f"provider-write policy must require binding and readback: {operation}")
        if item["risk_class"] == "D3" and not item["human_approval_required"]:
            raise PentaOSBuildError(f"D3 policy must require human approval: {operation}")
        normalized.append({
            "operation": operation,
            "scope": scope,
            "machine_keys": sorted(machine_keys),
            "effect": item["effect"],
            "risk_class": item["risk_class"],
            "minimum_authority": item["minimum_authority"],
            **{flag: item[flag] for flag in flags},
        })
    return {
        "schema": policy["schema"],
        "policy_version": policy["policy_version"],
        "default_disposition": policy["default_disposition"],
        "authority_trace_pattern": policy["authority_trace_pattern"],
        "policies": sorted(normalized, key=lambda item: item["operation"]),
    }


def enrich_dependency_graph(systems: list[dict[str, Any]]) -> dict[str, Any]:
    adjacency = {row["machine_key"]: list(row["dependencies"]) for row in systems}
    maturity_by_key = {row["machine_key"]: row["maturity"] for row in systems}
    components = strongly_connected_components(adjacency)
    component_index = {member: index for index, component in enumerate(components) for member in component}
    cyclic_components = [
        component for component in components
        if len(component) > 1 or component[0] in adjacency[component[0]]
    ]
    cycle_records: list[dict[str, Any]] = []
    cycle_by_member: dict[str, str] = {}
    for component in cyclic_components:
        members = sorted(component)
        edges = sorted([
            [source, target]
            for source in members
            for target in adjacency[source]
            if target in members
        ])
        cycle_id = "penta-scc-" + digest({"members": members})[:16]
        record = {
            "cycle_id": cycle_id,
            "members": members,
            "internal_edges": edges,
            "cycle_sha256": digest({"members": members, "edges": edges}),
            "classification": "untyped_unclassified",
        }
        cycle_records.append(record)
        cycle_by_member.update({member: cycle_id for member in members})

    condensed_edges = {
        (component_index[target], component_index[source])
        for source, dependencies in adjacency.items()
        for target in dependencies
        if component_index[source] != component_index[target]
    }
    closures = {key: transitive_closure(adjacency, key) for key in sorted(adjacency)}
    readiness = Counter()
    for row in systems:
        key = row["machine_key"]
        closure = closures[key]
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
            dependency_maturity_holds = [
                member for member in closure
                if maturity_by_key[member] not in EXECUTION_ELIGIBLE
            ]
            if dependency_maturity_holds:
                state = "HOLD_DEPENDENCY_MATURITY"
                blockers = [f"dependency maturity hold: {member}" for member in dependency_maturity_holds]
            else:
                state = "READY"
                blockers = []
        row["transitive_dependencies"] = closure
        if key in cycle_by_member:
            row["dependency_cycle_id"] = cycle_by_member[key]
        row["strict_readiness_state"] = state
        row["strict_readiness_blockers"] = blockers
        readiness[state] += 1

    graph_payload = {
        "nodes": [
            {
                "machine_key": row["machine_key"],
                "dependency_assessed": row["dependency_assessed"],
                "direct_internal": row["dependencies"],
                "direct_external": row["external_dependencies"],
                "transitive_internal": row["transitive_dependencies"],
                "cycle_id": row.get("dependency_cycle_id"),
            }
            for row in systems
        ],
        "cycles": cycle_records,
    }
    return {
        "semantic_state": "diagnostic_untyped",
        "strict_readiness_is_diagnostic": True,
        "operation_specific_verification_required": True,
        "dependency_assessed_member_count": sum(row["dependency_assessed"] for row in systems),
        "dependency_unassessed_member_count": sum(not row["dependency_assessed"] for row in systems),
        "members_with_declared_dependencies": sum(bool(row["dependencies"] or row["external_dependencies"]) for row in systems),
        "internal_edge_count": sum(len(row["dependencies"]) for row in systems),
        "external_edge_count": sum(len(row["external_dependencies"]) for row in systems),
        "external_refs": sorted({ref for row in systems for ref in row["external_dependencies"]}),
        "cyclic_scc_count": len(cycle_records),
        "cyclic_member_count": sum(len(record["members"]) for record in cycle_records),
        "cyclic_internal_edge_count": sum(len(record["internal_edges"]) for record in cycle_records),
        "condensed_component_count": len(components),
        "condensed_edge_count": len(condensed_edges),
        "transitive_membership_count": sum(len(closure) for closure in closures.values()),
        "maximum_transitive_closure": max(map(len, closures.values()), default=0),
        "cycles": cycle_records,
        "readiness_partition": {state: readiness.get(state, 0) for state in READINESS_STATES},
        "graph_payload_sha256": digest(graph_payload),
    }


def build_registry(root: Path) -> dict[str, Any]:
    discoveries, discovery_aliases = discovery_members(root)
    rows = (
        parse_institutional_registry(root / "PENTA-FAMILY-REGISTRY.md")
        + family_members(root)
        + component_members(root)
        + public_services(root)
        + discoveries
    )
    systems = merge_rows(rows, [])
    aliases = list(discovery_aliases)
    for system in systems:
        for alias in system["aliases"]:
            alias_token = token(alias)
            existing = next((item for item in aliases if token(item["alias"]) == alias_token), None)
            if existing:
                if existing.get("canonical_machine_key") != system["machine_key"]:
                    raise PentaOSBuildError(f"source alias targets conflict: {alias}")
                continue
            aliases.append({
                "alias": alias,
                "canonical_machine_key": system["machine_key"],
                "reason": "Canonical source, historical, compatibility, or display-name alias.",
            })
    known_keys = {row["machine_key"] for row in systems}
    dependency_graph = enrich_dependency_graph(systems)
    operation_policy = load_operation_policy(root, known_keys)
    normalized_aliases = sorted(aliases, key=lambda item: (token(item["alias"]), item["canonical_machine_key"]))
    alias_tokens: set[str] = set()
    name_tokens = {token(row["canonical_name"]): row["machine_key"] for row in systems}
    for alias in normalized_aliases:
        if not isinstance(alias, dict):
            raise PentaOSBuildError("aliases must be objects")
        alias_token = token(alias.get("alias", ""))
        target = alias.get("canonical_machine_key")
        if not alias_token or target not in known_keys or alias_token in alias_tokens:
            raise PentaOSBuildError(f"invalid or duplicate alias: {alias!r}")
        if alias_token in name_tokens and name_tokens[alias_token] != target:
            raise PentaOSBuildError(f"alias shadows a canonical identity: {alias['alias']}")
        alias_tokens.add(alias_token)

    source_paths = sorted(
        {source for row in systems for source in row["registry_sources"]}
        | {str(FAMILY_REGISTRY_PATH), str(OPERATION_POLICY_PATH)}
    )
    source_digests = {
        path: hashlib.sha256((root / path).read_bytes()).hexdigest()
        for path in source_paths
    }
    payload_digest = digest(systems)
    maturity = Counter(row["maturity"] for row in systems)
    registration = Counter(row["registration_state"] for row in systems)
    axes = Counter(row["axis"] for row in systems)
    registry = {
        "$schema": "../../schemas/penta/os-v1-registry.schema.json",
        "schema_version": SCHEMA_VERSION,
        "registry_id": "crownthrive.penta.os-v1",
        "version": RELEASE_VERSION,
        "effective_date": GENERATED_DATE,
        "release_state": "built_unreleased",
        "scope": "complete_identity_addressability_dependency_closure_verification_receipts_batch_planning_and_fail_closed_dispatch_kernel",
        "doctrine": "Discover -> Govern -> Execute -> Verify -> Preserve",
        "authority_invariant": "Penta OS V1.5 supplies identity, status, validation, deterministic verification receipts, dependency closure, batch planning, and governed dispatch gates for every registered entry. It may project a separately governed exact-digest maturity promotion, but never infers maturity, manufactures authority or credentials, accesses providers, changes provider state, or creates a provider-production claim.",
        "phase_truth": "bounded_phase_3_production_core_with_ecosystem_transition_and_open_recovery_cie_commerce_holds",
        "operations": list(ADDRESSABLE_OPERATIONS),
        "control_plane_operations": ["batch-plan", "verify-batch-plan", "verify-plan", "verify-receipt"],
        "axes": list(AXES),
        "production_certification": "HOLD",
        "promotion_registry": str(PROMOTION_PATH),
        "provider_state_promotion_authorized": False,
        "release_gate_codes": sorted(RELEASE_GATE_CODES),
        "counts": {
            "total": len(systems),
            "systems": sum(row["kind"] == "system" for row in systems),
            "layers": sum(row["kind"] == "layer" for row in systems),
            "subcomponents": sum(row["kind"] == "subcomponent" for row in systems),
            "primitives": sum(row["kind"] == "primitive" for row in systems),
            "execution_eligible_by_registry": sum(row["execution_eligible_by_registry"] for row in systems),
            "evidence_bound_maturity_promotions": sum(
                "maturity_promotion" in row for row in systems
            ),
            "dependency_assessed_members": dependency_graph["dependency_assessed_member_count"],
            "dependency_unassessed_members": dependency_graph["dependency_unassessed_member_count"],
            "members_with_declared_edges": dependency_graph["members_with_declared_dependencies"],
            "penta_dependency_edges": sum(len(row["dependencies"]) for row in systems),
            "external_dependency_edges": sum(len(row["external_dependencies"]) for row in systems),
            "unresolved_penta_dependencies": 0,
            "cyclic_sccs": dependency_graph["cyclic_scc_count"],
            "cyclic_members": dependency_graph["cyclic_member_count"],
            "strict_readiness_ready": dependency_graph["readiness_partition"]["READY"],
            "by_maturity": dict(sorted(maturity.items())),
            "by_registration_state": dict(sorted(registration.items())),
            "by_axis": {axis: axes.get(axis, 0) for axis in AXES},
            "by_strict_readiness": dependency_graph["readiness_partition"],
        },
        "source_digests_sha256": source_digests,
        "systems_sha256": payload_digest,
        "dependency_graph": dependency_graph,
        "dependency_graph_sha256": digest(dependency_graph),
        "operation_policy": operation_policy,
        "operation_policy_sha256": digest(operation_policy),
        "systems": systems,
        "aliases": normalized_aliases,
    }
    registry["registry_sha256"] = digest(registry)
    return registry


def render_docs(registry: dict[str, Any]) -> str:
    counts = registry["counts"]
    lines = [
        "---",
        'title: "Penta OS V1.5 — Complete Registry"',
        'description: "Complete reconciled Penta census with dependency closure, deterministic verification receipts, batch planning, and fail-closed execution."',
        'sidebarTitle: "Penta OS V1.5 Registry"',
        'icon: "microchip"',
        'standard_version: "1.0.0"',
        'primary_audience: "operator"',
        'page_type: "registry"',
        'content_state: "current_with_holds"',
        "---",
        "",
        "{/* pentadocs:audience-orientation:v2 */}",
        "<Note>",
        "  **Audience:** operators and administrators (`operator`).",
        "",
        "  **This page:** Penta OS V1.5 — Complete Registry — Complete reconciled Penta census with dependency closure, deterministic verification receipts, batch planning, and fail-closed execution.",
        "",
        "  **Documentation state:** `current_with_holds` for page type `registry`. Documentation state is editorial posture only; it does not certify runtime, deployment, legal, rights, financial, provider, production, release, security, or operational status.",
        "",
        "  **Related guidance:** [Operating principles](/start-here/operating-principles) and [Permissions and approvals](/automation/permissions-and-approval-gates).",
        "</Note>",
        "{/* /pentadocs:audience-orientation:v2 */}",
        "",
        "## Penta OS V1.5™ // Complete Registry",
        "",
        f"**Version:** `{RELEASE_VERSION}` · **Build state:** `built_unreleased` · **Certification:** `HOLD` · **Entries:** `{counts['total']}`",
        "",
        f"Penta OS V1.5 reconciles the institutional Penta list, the executable {counts['by_registration_state'].get('family_registered', 0)}-member Penta Family census, the technical component registry, public compatibility services, registered primitives, and governed incoming discoveries into one deterministic control-plane inventory.",
        "",
        "<Warning>",
        f"  Registry inclusion is not production promotion. {counts['evidence_bound_maturity_promotions']} entries carry separately governed, exact-digest maturity lineage; that lineage has no provider-state effect. Only entries whose effective governed maturity is `certified` or `production` may pass the first dispatch gate, and all downstream authority, credential, security, provider, readback, and human-reserved D3 gates still apply.",
        "</Warning>",
        "",
        "## Current institutional truth",
        "",
        "The bounded Phase 3 production-core bootstrap is GO. The wider ecosystem remains transitional, with institution-wide recovery, exact-current CIE assurance, commerce closure, and other release holds still open. Penta OS V1.5 preserves those holds; it does not convert them into a blanket production claim.",
        "",
        "## V1.5 completeness contract",
        "",
        "Every entry is uniquely identified, assigned to one of the five Penta axes, documented, status-addressable, validation-addressable, readiness-addressable, verification-addressable, plan-addressable, and dispatch-gated. V1.5 also resolves every declared Penta dependency, preserves unverified external dependency references, produces hash-bound verification receipts, and supports deterministic all-or-none batch gating. Specialized execution remains owned by the corresponding subsystem.",
        "",
        "| Measure | Count |",
        "| --- | ---: |",
        f"| Total reconciled entries | {counts['total']} |",
        f"| Systems | {counts['systems']} |",
        f"| Macro layers | {counts['layers']} |",
        f"| Documented subcomponents | {counts['subcomponents']} |",
        f"| Registered primitives | {counts['primitives']} |",
        f"| Family-registered | {counts['by_registration_state'].get('family_registered', 0)} |",
        f"| Independently execution-eligible by registry | {counts['execution_eligible_by_registry']} |",
        f"| Exact-evidence maturity projections | {counts['evidence_bound_maturity_promotions']} |",
        f"| Dependency-assessed members | {counts['dependency_assessed_members']} |",
        f"| Dependency-unassessed members | {counts['dependency_unassessed_members']} |",
        f"| Members with declared edges | {counts['members_with_declared_edges']} |",
        f"| Resolved Penta dependency edges | {counts['penta_dependency_edges']} |",
        f"| External dependency references | {counts['external_dependency_edges']} |",
        f"| Unresolved Penta dependencies | {counts['unresolved_penta_dependencies']} |",
        f"| Cyclic dependency groups / members | {counts['cyclic_sccs']} / {counts['cyclic_members']} |",
        f"| Strict diagnostic readiness READY | {counts['strict_readiness_ready']} |",
        "",
        "## Complete Penta census",
        "",
        "| Penta | Machine key | Kind | Axis | Maturity | Registry state | Risk | Operator route |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in registry["systems"]:
        lines.append(
            f"| {row['canonical_name']} | `{row['machine_key']}` | {row['kind']} | {row['axis']} | `{row['maturity']}` | `{row['registration_state']}` | {row['risk_ceiling']} | `{row['operator_route']}` |"
        )
    promoted = [row for row in registry["systems"] if "maturity_promotion" in row]
    lines.extend([
        "",
        "## Evidence-bound maturity projections",
        "",
        "These projections recognize bounded system maturity only. Provider state remains `UNCHANGED_SEPARATELY_GATED`; provider effects and self-certification remain prohibited.",
        "",
        "| Penta | Catalog maturity | Effective maturity | Authority | Provider disposition |",
        "| --- | --- | --- | --- | --- |",
    ])
    for row in promoted:
        promotion = row["maturity_promotion"]
        lines.append(
            f"| {row['canonical_name']} | `{row['catalog_maturity']}` | `{row['maturity']}` | `{promotion['authority_ref']}` | `{promotion['provider_state_disposition']}` |"
        )
    lines.extend([
        "",
        "## Route reconciliation",
        "",
        "`/io/pentas/{slug}` is the authenticated operator/control route. `/penta/{machine-key-suffix}` is the public-safe status/documentation route. The two surfaces are complementary and neither creates execution authority.",
        "",
        "## Executable contract",
        "",
        "```bash",
        "python runtime/penta_os_v1.py --root . list",
        "python runtime/penta_os_v1.py --root . status penta.mail",
        "python runtime/penta_os_v1.py --root . readiness penta.mail",
        "python runtime/penta_os_v1.py --root . validate",
        "python runtime/penta_os_v1.py --root . verify",
        "python runtime/penta_os_v1.py --root . verify penta.mail",
        "python runtime/penta_os_v1.py --root . plan penta.mail --operation status",
        "```",
        "",
        "The `verify` operation emits a deterministic SHA-256 repository receipt without promoting maturity. `batch-plan` evaluates multiple dispatch intents through an all-or-none gate and holds the entire batch when any item or idempotency contract fails; it does not execute a transaction. `dispatch` uses the exact registry-derived operation policy, typed A0-A3 authority trace, idempotency, readiness, human, provider-binding, and readback gates. The runtime is side-effect free.",
        "",
        "## Sources and integrity",
        "",
        f"Registry payload SHA-256: `{registry['systems_sha256']}`.",
        f"Dependency graph SHA-256: `{registry['dependency_graph_sha256']}`.",
        f"Full registry SHA-256: `{registry['registry_sha256']}`.",
        "",
        "The complete machine-readable record is `data/penta/os-v1.registry.json`; generation is deterministic through `scripts/build_penta_os_v1.py`; validation, verification receipts, batch planning, and fail-closed dispatch are implemented in `runtime/penta_os_v1.py`.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    registry = build_registry(root)
    registry_text = json.dumps(registry, indent=2, sort_keys=False) + "\n"
    docs_text = render_docs(registry)
    outputs = {root / REGISTRY_PATH: registry_text, root / DOCS_PATH: docs_text}
    if args.write:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        print(f"wrote {registry['counts']['total']} entries; sha256={registry['systems_sha256']}")
        return 0
    stale = [str(path.relative_to(root)) for path, content in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
    if stale:
        raise SystemExit("generated outputs are stale: " + ", ".join(stale))
    print(f"Penta OS V1.5 registry current: {registry['counts']['total']} entries; sha256={registry['systems_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
