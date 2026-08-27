"""Production control-plane runtime for the CrownThrive Penta Family.

The Penta Family is an umbrella registry, census, portal contract and dispatch
guard. A production family never promotes a child system automatically. A child
may advance only through a separate evidence-bound promotion registry whose
prior maturity and exact evidence digests validate. Provider state and authority
remain independent and fail closed.

This module is dependency-free so it can run in CI, local operator checks, and
minimal recovery environments. It performs no provider side effects.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Mapping, Tuple

try:
    from runtime.penta_promotions import PentaPromotionError, apply_promotions
except ModuleNotFoundError:
    runtime_dir = str(Path(__file__).resolve().parent)
    if runtime_dir not in sys.path:
        sys.path.insert(0, runtime_dir)
    from penta_promotions import PentaPromotionError, apply_promotions

ALLOWED_MATURITY = {"specified", "implemented", "certified", "production", "hold", "retired"}
EXECUTION_ELIGIBLE = {"certified", "production"}
REQUIRED_FAMILY_TRUE_FLAGS = {
    "fail_closed",
    "member_status_is_independent",
    "production_family_does_not_promote_members",
    "unknown_members_block_dispatch",
    "duplicate_machine_keys_block_dispatch",
    "missing_required_catalogs_block_dispatch",
    "execution_requires_member_eligibility",
}
REQUIRED_PORTAL_SECTIONS = {
    "overview",
    "status",
    "responsibilities",
    "inputs_outputs",
    "authority_boundary",
    "dependencies",
    "sops_slas",
    "runbooks",
    "guides",
    "evidence",
    "api_mcp",
    "changelog",
    "support",
}
REQUIRED_SELF_BUILD_TRUE_FLAGS = {
    "applies_to_all_registered_members",
    "typed_gap_required",
    "penta_factory_builder_required",
    "independent_certification_required",
    "negative_and_stress_tests_required",
    "rollback_required",
    "authority_never_manufactured",
    "d3_human_reserved",
}


class PentaFamilyError(ValueError):
    """Raised when the family contract or composed catalogs are invalid."""


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PentaFamilyError(f"cannot read required catalog: {path}") from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PentaFamilyError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PentaFamilyError(f"JSON root must be an object: {path}")
    return value


def _name_token(value: str) -> str:
    """Normalize display-name differences such as Penta Control/PentaControl."""
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _portal_route(machine_key: str, base_route: str = "/penta") -> str:
    suffix = machine_key.split(".", 1)[1]
    return f"{base_route.rstrip('/')}/{suffix}"


def validate_family_registry(registry: Mapping[str, Any]) -> None:
    """Validate the non-negotiable production invariants of the umbrella."""
    if registry.get("registry_id") != "crownthrive.penta.family":
        raise PentaFamilyError("unexpected family registry_id")
    if registry.get("canonical_name") != "Penta Family":
        raise PentaFamilyError("canonical_name must be Penta Family")
    if registry.get("status") != "production":
        raise PentaFamilyError("Penta Family control plane must declare production status")
    if registry.get("production_scope") != "institutional_control_plane":
        raise PentaFamilyError("unexpected Penta Family production_scope")

    contract = registry.get("production_contract")
    if not isinstance(contract, dict):
        raise PentaFamilyError("production_contract must be an object")
    for flag in sorted(REQUIRED_FAMILY_TRUE_FLAGS):
        if contract.get(flag) is not True:
            raise PentaFamilyError(f"production_contract.{flag} must be true")

    eligible = set(contract.get("execution_eligible_maturity") or [])
    if eligible != EXECUTION_ELIGIBLE:
        raise PentaFamilyError("execution_eligible_maturity must be exactly certified + production")

    catalogs = registry.get("catalogs")
    if not isinstance(catalogs, list) or not catalogs:
        raise PentaFamilyError("at least one family catalog is required")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for item in catalogs:
        if not isinstance(item, dict):
            raise PentaFamilyError("catalog entries must be objects")
        catalog_id = item.get("catalog_id")
        path = item.get("path")
        if not isinstance(catalog_id, str) or not catalog_id:
            raise PentaFamilyError("catalog_id must be a non-empty string")
        if not isinstance(path, str) or not path.startswith("data/penta/") or not path.endswith(".json"):
            raise PentaFamilyError(f"unsafe catalog path: {path!r}")
        if catalog_id in seen_ids or path in seen_paths:
            raise PentaFamilyError("catalog ids and paths must be unique")
        seen_ids.add(catalog_id)
        seen_paths.add(path)

    control_validation = registry.get("control_plane_validation")
    if not isinstance(control_validation, dict):
        raise PentaFamilyError("control_plane_validation must be an object")
    if control_validation.get("registered_penta_refs_required") is not True:
        raise PentaFamilyError("registered_penta_refs_required must be true")
    if control_validation.get("normalize_display_names") is not True:
        raise PentaFamilyError("normalize_display_names must be true")
    if control_validation.get("unresolved_reference_disposition") != "hold_fail_closed":
        raise PentaFamilyError("unresolved control-plane references must fail closed")
    external_refs = control_validation.get("external_refs_allowed")
    if not isinstance(external_refs, list) or not all(isinstance(item, str) and item for item in external_refs):
        raise PentaFamilyError("external_refs_allowed must be a string array")

    control_planes = registry.get("control_planes")
    if not isinstance(control_planes, dict) or not control_planes:
        raise PentaFamilyError("control_planes must be a non-empty object")
    for plane, refs in control_planes.items():
        if not isinstance(plane, str) or not plane:
            raise PentaFamilyError("control plane names must be non-empty strings")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
            raise PentaFamilyError(f"control plane {plane!r} must contain string references")

    portal = registry.get("portal_contract")
    if not isinstance(portal, dict):
        raise PentaFamilyError("portal_contract must be an object")
    required_true = (
        "every_registered_member_has_portal",
        "portal_state_is_independent_from_maturity",
        "portal_does_not_create_execution_authority",
    )
    for flag in required_true:
        if portal.get(flag) is not True:
            raise PentaFamilyError(f"portal_contract.{flag} must be true")
    if portal.get("base_route") != "/penta":
        raise PentaFamilyError("portal_contract.base_route must be /penta")
    if portal.get("route_pattern") != "/penta/{machine_key_suffix}":
        raise PentaFamilyError("unexpected portal route_pattern")
    sections = set(portal.get("required_sections") or [])
    missing_sections = sorted(REQUIRED_PORTAL_SECTIONS - sections)
    if missing_sections:
        raise PentaFamilyError("portal contract missing required sections: " + ", ".join(missing_sections))

    self_build = registry.get("self_build_contract")
    if not isinstance(self_build, dict):
        raise PentaFamilyError("self_build_contract must be an object")
    for flag in sorted(REQUIRED_SELF_BUILD_TRUE_FLAGS):
        if self_build.get(flag) is not True:
            raise PentaFamilyError(f"self_build_contract.{flag} must be true")
    expected_paths = {
        "contract_path": "data/penta/self-build.contract.json",
        "candidate_schema_path": "schemas/penta/self-build-candidate.schema.json",
        "runtime_path": "runtime/penta_self_build.py",
    }
    for field, expected in expected_paths.items():
        if self_build.get(field) != expected:
            raise PentaFamilyError(f"self_build_contract.{field} must be {expected}")


def _iter_systems(catalog: Mapping[str, Any], *, source: str) -> Iterable[Tuple[str, Dict[str, Any]]]:
    systems = catalog.get("systems")
    if not isinstance(systems, list):
        raise PentaFamilyError(f"catalog has no systems array: {source}")
    for index, system in enumerate(systems):
        if not isinstance(system, dict):
            raise PentaFamilyError(f"system entry {index} in {source} is not an object")
        machine_key = system.get("machine_key")
        canonical_name = system.get("canonical_name")
        maturity = system.get("maturity")
        if not isinstance(machine_key, str) or not machine_key.startswith("penta."):
            raise PentaFamilyError(f"invalid PENTA machine_key in {source}: {machine_key!r}")
        if not isinstance(canonical_name, str) or not canonical_name.strip():
            raise PentaFamilyError(f"missing canonical_name for {machine_key}")
        if maturity not in ALLOWED_MATURITY:
            raise PentaFamilyError(f"invalid maturity for {machine_key}: {maturity!r}")
        yield machine_key, dict(system)


def _resolve_control_planes(
    registry: Mapping[str, Any], members: Mapping[str, Mapping[str, Any]]
) -> Dict[str, List[Dict[str, str]]]:
    validation = registry["control_plane_validation"]
    external_refs = set(validation.get("external_refs_allowed") or [])

    token_index: Dict[str, set[str]] = {}
    for machine_key, system in members.items():
        names = [machine_key, str(system.get("canonical_name", ""))]
        aliases = system.get("aliases") or []
        if isinstance(aliases, list):
            names.extend(alias for alias in aliases if isinstance(alias, str))
        for name in names:
            token = _name_token(name)
            if token:
                token_index.setdefault(token, set()).add(machine_key)

    resolved: Dict[str, List[Dict[str, str]]] = {}
    for plane, refs in registry["control_planes"].items():
        plane_resolved: List[Dict[str, str]] = []
        for ref in refs:
            if ref in external_refs:
                plane_resolved.append({"reference": ref, "kind": "external_authority", "resolved_to": ref})
                continue
            matches = sorted(token_index.get(_name_token(ref), set()))
            if not matches:
                raise PentaFamilyError(f"unresolved control-plane reference {ref!r} in {plane!r}")
            if len(matches) != 1:
                raise PentaFamilyError(
                    f"ambiguous control-plane reference {ref!r} in {plane!r}: {', '.join(matches)}"
                )
            plane_resolved.append({"reference": ref, "kind": "penta_member", "resolved_to": matches[0]})
        resolved[plane] = plane_resolved
    return resolved


def compose_family(root: Path, registry: Mapping[str, Any]) -> Dict[str, Any]:
    """Load required catalogs and return a deterministic family snapshot."""
    validate_family_registry(registry)
    members: Dict[str, Dict[str, Any]] = {}
    member_sources: Dict[str, str] = {}
    missing_catalogs: List[str] = []

    for catalog_ref in registry["catalogs"]:
        rel = catalog_ref["path"]
        path = root / rel
        if not path.exists():
            if catalog_ref.get("required") is True:
                missing_catalogs.append(rel)
            continue
        catalog = _load_json(path)
        for machine_key, system in _iter_systems(catalog, source=rel):
            if machine_key in members:
                first = member_sources[machine_key]
                raise PentaFamilyError(f"duplicate machine_key {machine_key}: {first} and {rel}")
            members[machine_key] = system
            member_sources[machine_key] = rel

    if missing_catalogs:
        raise PentaFamilyError(
            "missing required family catalogs: " + ", ".join(sorted(missing_catalogs))
        )
    if not members:
        raise PentaFamilyError("family has no registered members")

    try:
        members, promotions = apply_promotions(root, members)
    except PentaPromotionError as exc:
        raise PentaFamilyError(f"invalid evidence-bound maturity promotion: {exc}") from exc

    control_plane_resolution = _resolve_control_planes(registry, members)
    base_route = registry["portal_contract"]["base_route"]

    maturity_counts = Counter(system["maturity"] for system in members.values())
    execution_eligible = sorted(
        key for key, system in members.items() if system["maturity"] in EXECUTION_ELIGIBLE
    )
    held = sorted(
        key for key, system in members.items() if system["maturity"] in {"hold", "retired"}
    )

    member_snapshot: Dict[str, Dict[str, Any]] = {}
    portal_index: Dict[str, str] = {}
    for key in sorted(members):
        system = members[key]
        route = _portal_route(key, base_route)
        portal_index[key] = route
        member_snapshot[key] = {
            "canonical_name": system["canonical_name"],
            "aliases": system.get("aliases", []),
            "category": system.get("category"),
            "purpose": system.get("purpose"),
            "human_surface": system.get("human_surface"),
            "authority_boundary": system.get("authority_boundary"),
            "risk_ceiling": system.get("risk_ceiling"),
            "maturity": system["maturity"],
            "catalog_maturity": system.get("catalog_maturity", system["maturity"]),
            "maturity_promotion": system.get("maturity_promotion"),
            "dependencies": system.get("dependencies", []),
            "source": member_sources[key],
            "portal_route": route,
            "portal_state": "contracted",
            "self_build": {
                "enabled": True,
                "gap_intake": "penta.rfa",
                "builder": "penta.factory",
                "independent_certifier": "penta.certify",
                "production_promotion_automatic": False,
            },
        }

    return {
        "family_registry_id": registry["registry_id"],
        "family_status": "production",
        "production_scope": registry["production_scope"],
        "fail_closed": True,
        "member_count": len(members),
        "maturity_counts": dict(sorted(maturity_counts.items())),
        "execution_eligible_members": execution_eligible,
        "held_members": held,
        "promotion_count": len(promotions),
        "promoted_members": sorted(promotions),
        "promotion_registry": "data/penta/production-promotions.v1.json" if promotions else None,
        "control_plane_resolution": control_plane_resolution,
        "portal_index": portal_index,
        "self_build_coverage": {
            "covered_member_count": len(member_snapshot),
            "all_registered_members_covered": len(member_snapshot) == len(members),
            "contract_path": registry["self_build_contract"]["contract_path"],
        },
        "members": member_snapshot,
    }


def member_dispatch_gate(snapshot: Mapping[str, Any], machine_key: str) -> Dict[str, Any]:
    """Return a fail-closed eligibility decision; this function executes nothing."""
    members = snapshot.get("members")
    if not isinstance(members, dict) or machine_key not in members:
        return {
            "machine_key": machine_key,
            "eligible": False,
            "disposition": "hold_fail_closed",
            "reason": "unknown or unregistered Penta Family member",
        }
    maturity = members[machine_key].get("maturity")
    if maturity not in EXECUTION_ELIGIBLE:
        return {
            "machine_key": machine_key,
            "eligible": False,
            "disposition": "hold_fail_closed",
            "reason": f"member maturity {maturity!r} is not execution-eligible",
        }
    return {
        "machine_key": machine_key,
        "eligible": True,
        "disposition": "member_gate_passed",
        "reason": "member is registered and maturity is execution-eligible; downstream authority/provider gates still apply",
    }


def member_portal(snapshot: Mapping[str, Any], registry: Mapping[str, Any], machine_key: str) -> Dict[str, Any]:
    """Return the canonical portal payload for one registered family member."""
    members = snapshot.get("members")
    if not isinstance(members, dict) or machine_key not in members:
        raise PentaFamilyError(f"cannot render portal for unknown member {machine_key!r}")
    member = members[machine_key]
    maturity = member.get("maturity")
    required_sections = registry["portal_contract"]["required_sections"]
    sections = {
        "overview": {
            "canonical_name": member.get("canonical_name"),
            "category": member.get("category"),
            "purpose": member.get("purpose"),
        },
        "status": {
            "family_status": snapshot.get("family_status"),
            "member_maturity": maturity,
            "catalog_maturity": member.get("catalog_maturity", maturity),
            "maturity_promotion": member.get("maturity_promotion"),
            "execution_eligible": maturity in EXECUTION_ELIGIBLE,
            "portal_state": member.get("portal_state"),
        },
        "responsibilities": {
            "human_surface": member.get("human_surface"),
            "risk_ceiling": member.get("risk_ceiling"),
        },
        "inputs_outputs": {
            "dependency_inputs": member.get("dependencies", []),
            "output_contract": "bounded governed results plus verification/readback evidence",
        },
        "authority_boundary": member.get("authority_boundary"),
        "dependencies": member.get("dependencies", []),
        "sops_slas": {
            "state": "required",
            "rule": "System-specific SOP/SLA records must be versioned in PentaDocs before consequential production dispatch when policy requires them.",
        },
        "runbooks": {
            "state": "required",
            "rule": "Operational, failure, rollback and recovery procedures are required for production-scoped capabilities.",
        },
        "guides": {
            "state": "required",
            "rule": "Operator, developer and governance guides are part of the portal contract and must stay aligned to system maturity.",
        },
        "evidence": {
            "source_catalog": member.get("source"),
            "maturity_promotion": member.get("maturity_promotion"),
            "rule": "Claims and maturity changes require evidence; portal presence is not deployment evidence.",
        },
        "api_mcp": {
            "rule": "Only registered/certified API, MCP, tool and provider bindings may be exposed as executable capabilities.",
        },
        "changelog": {
            "rule": "Material identity, maturity, authority, provider, portal or behavior changes require versioned change evidence.",
        },
        "support": {
            "owner": "CrownThrive LLC",
            "family_registry_id": snapshot.get("family_registry_id"),
        },
    }
    missing = [section for section in required_sections if section not in sections]
    if missing:
        raise PentaFamilyError("portal payload missing required sections: " + ", ".join(missing))
    return {
        "machine_key": machine_key,
        "portal_route": member.get("portal_route"),
        "portal_contract_state": "contracted",
        "sections": sections,
    }


def load_family(root: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    registry = _load_json(root / "data/penta/family.registry.json")
    return registry, compose_family(root, registry)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify, snapshot and render the CrownThrive Penta Family")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--member", help="optionally evaluate one member dispatch gate")
    parser.add_argument("--portal", action="store_true", help="render portal payload/index in addition to verification")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        registry, snapshot = load_family(root)
        output: Dict[str, Any] = {"ok": True, "snapshot": snapshot}
        if args.member:
            output["dispatch_gate"] = member_dispatch_gate(snapshot, args.member)
        if args.portal:
            if args.member:
                output["portal"] = member_portal(snapshot, registry, args.member)
            else:
                output["portal_index"] = snapshot["portal_index"]
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except PentaFamilyError as exc:
        print(json.dumps({"ok": False, "family_status": "hold_fail_closed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
