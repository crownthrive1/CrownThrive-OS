"""Production control-plane runtime for the CrownThrive Penta Family.

The Penta Family is an umbrella registry, census, portal contract and dispatch
guard. Child maturity is never promoted automatically. A child may advance only
through an explicit production-promotion record whose evidence/runtime paths are
present and whose prior maturity matches the source catalog. Provider, legal,
economic, security, licensing, governance, fiduciary and D3 authority remain
independent and fail closed.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

ALLOWED_MATURITY = {"specified", "implemented", "certified", "production", "hold", "retired"}
EXECUTION_ELIGIBLE = {"certified", "production"}
PROMOTION_PATH = Path("data/penta/production-promotions.v1.json")
REQUIRED_FAMILY_TRUE_FLAGS = {
    "fail_closed", "member_status_is_independent", "production_family_does_not_promote_members",
    "unknown_members_block_dispatch", "duplicate_machine_keys_block_dispatch",
    "missing_required_catalogs_block_dispatch", "execution_requires_member_eligibility",
}
REQUIRED_PORTAL_SECTIONS = {
    "overview", "status", "responsibilities", "inputs_outputs", "authority_boundary",
    "dependencies", "sops_slas", "runbooks", "guides", "evidence", "api_mcp",
    "changelog", "support",
}
REQUIRED_SELF_BUILD_TRUE_FLAGS = {
    "applies_to_all_registered_members", "typed_gap_required", "penta_factory_builder_required",
    "independent_certification_required", "negative_and_stress_tests_required", "rollback_required",
    "authority_never_manufactured", "d3_human_reserved",
}


class PentaFamilyError(ValueError):
    pass


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
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _portal_route(machine_key: str, base_route: str = "/penta") -> str:
    return f"{base_route.rstrip('/')}/{machine_key.split('.', 1)[1]}"


def _safe_repo_ref(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and not value.startswith(("/", "..")) and "\\" not in value


def validate_family_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("registry_id") != "crownthrive.penta.family": raise PentaFamilyError("unexpected family registry_id")
    if registry.get("canonical_name") != "Penta Family": raise PentaFamilyError("canonical_name must be Penta Family")
    if registry.get("status") != "production": raise PentaFamilyError("Penta Family control plane must declare production status")
    if registry.get("production_scope") != "institutional_control_plane": raise PentaFamilyError("unexpected Penta Family production_scope")

    contract = registry.get("production_contract")
    if not isinstance(contract, dict): raise PentaFamilyError("production_contract must be an object")
    for flag in sorted(REQUIRED_FAMILY_TRUE_FLAGS):
        if contract.get(flag) is not True: raise PentaFamilyError(f"production_contract.{flag} must be true")
    if set(contract.get("execution_eligible_maturity") or []) != EXECUTION_ELIGIBLE:
        raise PentaFamilyError("execution_eligible_maturity must be exactly certified + production")

    catalogs = registry.get("catalogs")
    if not isinstance(catalogs, list) or not catalogs: raise PentaFamilyError("at least one family catalog is required")
    seen_ids: set[str] = set(); seen_paths: set[str] = set()
    for item in catalogs:
        if not isinstance(item, dict): raise PentaFamilyError("catalog entries must be objects")
        catalog_id, path = item.get("catalog_id"), item.get("path")
        if not isinstance(catalog_id, str) or not catalog_id: raise PentaFamilyError("catalog_id must be a non-empty string")
        if not isinstance(path, str) or not path.startswith("data/penta/") or not path.endswith(".json"): raise PentaFamilyError(f"unsafe catalog path: {path!r}")
        if catalog_id in seen_ids or path in seen_paths: raise PentaFamilyError("catalog ids and paths must be unique")
        seen_ids.add(catalog_id); seen_paths.add(path)

    cv = registry.get("control_plane_validation")
    if not isinstance(cv, dict): raise PentaFamilyError("control_plane_validation must be an object")
    if cv.get("registered_penta_refs_required") is not True: raise PentaFamilyError("registered_penta_refs_required must be true")
    if cv.get("normalize_display_names") is not True: raise PentaFamilyError("normalize_display_names must be true")
    if cv.get("unresolved_reference_disposition") != "hold_fail_closed": raise PentaFamilyError("unresolved control-plane references must fail closed")
    if not isinstance(cv.get("external_refs_allowed"), list) or not all(isinstance(v, str) and v for v in cv["external_refs_allowed"]): raise PentaFamilyError("external_refs_allowed must be a string array")

    planes = registry.get("control_planes")
    if not isinstance(planes, dict) or not planes: raise PentaFamilyError("control_planes must be a non-empty object")
    for plane, refs in planes.items():
        if not isinstance(plane, str) or not plane: raise PentaFamilyError("control plane names must be non-empty strings")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs): raise PentaFamilyError(f"control plane {plane!r} must contain string references")

    portal = registry.get("portal_contract")
    if not isinstance(portal, dict): raise PentaFamilyError("portal_contract must be an object")
    for flag in ("every_registered_member_has_portal", "portal_state_is_independent_from_maturity", "portal_does_not_create_execution_authority"):
        if portal.get(flag) is not True: raise PentaFamilyError(f"portal_contract.{flag} must be true")
    if portal.get("base_route") != "/penta": raise PentaFamilyError("portal_contract.base_route must be /penta")
    if portal.get("route_pattern") != "/penta/{machine_key_suffix}": raise PentaFamilyError("unexpected portal route_pattern")
    missing = sorted(REQUIRED_PORTAL_SECTIONS - set(portal.get("required_sections") or []))
    if missing: raise PentaFamilyError("portal contract missing required sections: " + ", ".join(missing))

    sb = registry.get("self_build_contract")
    if not isinstance(sb, dict): raise PentaFamilyError("self_build_contract must be an object")
    for flag in sorted(REQUIRED_SELF_BUILD_TRUE_FLAGS):
        if sb.get(flag) is not True: raise PentaFamilyError(f"self_build_contract.{flag} must be true")
    expected = {"contract_path": "data/penta/self-build.contract.json", "candidate_schema_path": "schemas/penta/self-build-candidate.schema.json", "runtime_path": "runtime/penta_self_build.py"}
    for field, value in expected.items():
        if sb.get(field) != value: raise PentaFamilyError(f"self_build_contract.{field} must be {value}")


def _iter_systems(catalog: Mapping[str, Any], *, source: str) -> Iterable[Tuple[str, Dict[str, Any]]]:
    systems = catalog.get("systems")
    if not isinstance(systems, list): raise PentaFamilyError(f"catalog has no systems array: {source}")
    for index, system in enumerate(systems):
        if not isinstance(system, dict): raise PentaFamilyError(f"system entry {index} in {source} is not an object")
        key, name, maturity = system.get("machine_key"), system.get("canonical_name"), system.get("maturity")
        if not isinstance(key, str) or not key.startswith("penta."): raise PentaFamilyError(f"invalid PENTA machine_key in {source}: {key!r}")
        if not isinstance(name, str) or not name.strip(): raise PentaFamilyError(f"missing canonical_name for {key}")
        if maturity not in ALLOWED_MATURITY: raise PentaFamilyError(f"invalid maturity for {key}: {maturity!r}")
        yield key, dict(system)


def _apply_promotions(root: Path, members: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    path = root / PROMOTION_PATH
    if not path.exists(): return {}
    manifest = _load_json(path)
    if manifest.get("schema") != "ct.penta.production-promotions.v1" or manifest.get("version") != "1.0.0" or manifest.get("fail_closed") is not True:
        raise PentaFamilyError("invalid production promotion manifest contract")
    promotions = manifest.get("promotions")
    if not isinstance(promotions, list): raise PentaFamilyError("production promotions must be a list")
    applied: Dict[str, Dict[str, Any]] = {}
    seen: set[str] = set()
    for item in promotions:
        if not isinstance(item, dict): raise PentaFamilyError("promotion entry must be an object")
        required = {"machine_key", "from_maturity", "to_maturity", "effective_at", "authority_ref", "evidence_status", "evidence_refs", "runtime_refs", "scope"}
        missing = required - set(item)
        if missing: raise PentaFamilyError("promotion missing fields: " + ", ".join(sorted(missing)))
        key = item["machine_key"]
        if not isinstance(key, str) or not key.startswith("penta.") or key not in members: raise PentaFamilyError(f"promotion targets unknown member: {key!r}")
        if key in seen: raise PentaFamilyError(f"duplicate promotion for {key}")
        seen.add(key)
        current = members[key].get("maturity")
        if item["from_maturity"] != current: raise PentaFamilyError(f"promotion prior maturity mismatch for {key}: expected {current!r}")
        if item["to_maturity"] not in EXECUTION_ELIGIBLE: raise PentaFamilyError(f"promotion target maturity must be certified/production for {key}")
        if item["evidence_status"] != "PASS": raise PentaFamilyError(f"promotion evidence is not PASS for {key}")
        if not isinstance(item["authority_ref"], str) or not item["authority_ref"].strip(): raise PentaFamilyError(f"promotion authority_ref missing for {key}")
        if not isinstance(item["scope"], str) or not item["scope"].strip(): raise PentaFamilyError(f"promotion scope missing for {key}")
        evidence_refs, runtime_refs = item["evidence_refs"], item["runtime_refs"]
        if not isinstance(evidence_refs, list) or not evidence_refs or not all(_safe_repo_ref(v) for v in evidence_refs): raise PentaFamilyError(f"invalid promotion evidence refs for {key}")
        if not isinstance(runtime_refs, list) or not runtime_refs or not all(_safe_repo_ref(v) for v in runtime_refs): raise PentaFamilyError(f"invalid promotion runtime refs for {key}")
        absent = [ref for ref in [*evidence_refs, *runtime_refs] if not (root / ref).exists()]
        if absent: raise PentaFamilyError(f"promotion evidence/runtime missing for {key}: {', '.join(absent)}")
        members[key]["maturity"] = item["to_maturity"]
        applied[key] = {
            "from_maturity": current,
            "to_maturity": item["to_maturity"],
            "effective_at": item["effective_at"],
            "authority_ref": item["authority_ref"],
            "evidence_refs": list(evidence_refs),
            "runtime_refs": list(runtime_refs),
            "scope": item["scope"],
            "promotion_manifest": str(PROMOTION_PATH),
        }
    return applied


def _resolve_control_planes(registry: Mapping[str, Any], members: Mapping[str, Mapping[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
    external = set(registry["control_plane_validation"].get("external_refs_allowed") or [])
    index: Dict[str, set[str]] = {}
    for key, system in members.items():
        names = [key, str(system.get("canonical_name", ""))]
        aliases = system.get("aliases") or []
        if isinstance(aliases, list): names.extend(v for v in aliases if isinstance(v, str))
        for name in names:
            token = _name_token(name)
            if token: index.setdefault(token, set()).add(key)
    resolved: Dict[str, List[Dict[str, str]]] = {}
    for plane, refs in registry["control_planes"].items():
        rows: List[Dict[str, str]] = []
        for ref in refs:
            if ref in external:
                rows.append({"reference": ref, "kind": "external_authority", "resolved_to": ref}); continue
            matches = sorted(index.get(_name_token(ref), set()))
            if not matches: raise PentaFamilyError(f"unresolved control-plane reference {ref!r} in {plane!r}")
            if len(matches) != 1: raise PentaFamilyError(f"ambiguous control-plane reference {ref!r} in {plane!r}: {', '.join(matches)}")
            rows.append({"reference": ref, "kind": "penta_member", "resolved_to": matches[0]})
        resolved[plane] = rows
    return resolved


def compose_family(root: Path, registry: Mapping[str, Any]) -> Dict[str, Any]:
    validate_family_registry(registry)
    members: Dict[str, Dict[str, Any]] = {}; sources: Dict[str, str] = {}; missing_catalogs: List[str] = []
    for cref in registry["catalogs"]:
        rel = cref["path"]; path = root / rel
        if not path.exists():
            if cref.get("required") is True: missing_catalogs.append(rel)
            continue
        for key, system in _iter_systems(_load_json(path), source=rel):
            if key in members: raise PentaFamilyError(f"duplicate machine_key {key}: {sources[key]} and {rel}")
            members[key] = system; sources[key] = rel
    if missing_catalogs: raise PentaFamilyError("missing required family catalogs: " + ", ".join(sorted(missing_catalogs)))
    if not members: raise PentaFamilyError("family has no registered members")

    promotions = _apply_promotions(root, members)
    control_plane_resolution = _resolve_control_planes(registry, members)
    base_route = registry["portal_contract"]["base_route"]
    counts = Counter(system["maturity"] for system in members.values())
    eligible = sorted(key for key, system in members.items() if system["maturity"] in EXECUTION_ELIGIBLE)
    held = sorted(key for key, system in members.items() if system["maturity"] in {"hold", "retired"})
    member_snapshot: Dict[str, Dict[str, Any]] = {}; portal_index: Dict[str, str] = {}
    for key in sorted(members):
        system = members[key]; route = _portal_route(key, base_route); portal_index[key] = route
        row = {
            "canonical_name": system["canonical_name"], "aliases": system.get("aliases", []), "category": system.get("category"),
            "purpose": system.get("purpose"), "human_surface": system.get("human_surface"), "authority_boundary": system.get("authority_boundary"),
            "risk_ceiling": system.get("risk_ceiling"), "maturity": system["maturity"], "dependencies": system.get("dependencies", []),
            "source": sources[key], "portal_route": route, "portal_state": "contracted",
            "self_build": {"enabled": True, "gap_intake": "penta.rfa", "builder": "penta.factory", "independent_certifier": "penta.certify", "production_promotion_automatic": False},
        }
        if key in promotions: row["maturity_promotion"] = promotions[key]
        member_snapshot[key] = row
    return {
        "family_registry_id": registry["registry_id"], "family_status": "production", "production_scope": registry["production_scope"], "fail_closed": True,
        "member_count": len(members), "maturity_counts": dict(sorted(counts.items())), "execution_eligible_members": eligible, "held_members": held,
        "promotion_count": len(promotions), "promoted_members": sorted(promotions), "promotion_manifest": str(PROMOTION_PATH) if promotions else None,
        "control_plane_resolution": control_plane_resolution, "portal_index": portal_index,
        "self_build_coverage": {"covered_member_count": len(member_snapshot), "all_registered_members_covered": len(member_snapshot) == len(members), "contract_path": registry["self_build_contract"]["contract_path"]},
        "members": member_snapshot,
    }


def member_dispatch_gate(snapshot: Mapping[str, Any], machine_key: str) -> Dict[str, Any]:
    members = snapshot.get("members")
    if not isinstance(members, dict) or machine_key not in members:
        return {"machine_key": machine_key, "eligible": False, "disposition": "hold_fail_closed", "reason": "unknown or unregistered Penta Family member"}
    maturity = members[machine_key].get("maturity")
    if maturity not in EXECUTION_ELIGIBLE:
        return {"machine_key": machine_key, "eligible": False, "disposition": "hold_fail_closed", "reason": f"member maturity {maturity!r} is not execution-eligible"}
    return {"machine_key": machine_key, "eligible": True, "disposition": "member_gate_passed", "reason": "member is registered and maturity is execution-eligible; downstream authority/provider gates still apply"}


def member_portal(snapshot: Mapping[str, Any], registry: Mapping[str, Any], machine_key: str) -> Dict[str, Any]:
    members = snapshot.get("members")
    if not isinstance(members, dict) or machine_key not in members: raise PentaFamilyError(f"cannot render portal for unknown member {machine_key!r}")
    member = members[machine_key]; maturity = member.get("maturity"); required = registry["portal_contract"]["required_sections"]
    sections = {
        "overview": {"canonical_name": member.get("canonical_name"), "category": member.get("category"), "purpose": member.get("purpose")},
        "status": {"family_status": snapshot.get("family_status"), "member_maturity": maturity, "execution_eligible": maturity in EXECUTION_ELIGIBLE, "portal_state": member.get("portal_state"), "maturity_promotion": member.get("maturity_promotion")},
        "responsibilities": {"human_surface": member.get("human_surface"), "risk_ceiling": member.get("risk_ceiling")},
        "inputs_outputs": {"dependency_inputs": member.get("dependencies", []), "output_contract": "bounded governed results plus verification/readback evidence"},
        "authority_boundary": member.get("authority_boundary"), "dependencies": member.get("dependencies", []),
        "sops_slas": {"state": "required", "rule": "System-specific SOP/SLA records must be versioned in PentaDocs before consequential production dispatch when policy requires them."},
        "runbooks": {"state": "required", "rule": "Operational, failure, rollback and recovery procedures are required for production-scoped capabilities."},
        "guides": {"state": "required", "rule": "Operator, developer and governance guides are part of the portal contract and must stay aligned to system maturity."},
        "evidence": {"source_catalog": member.get("source"), "promotion": member.get("maturity_promotion"), "rule": "Claims and maturity changes require evidence; portal presence is not deployment evidence."},
        "api_mcp": {"rule": "Only registered/certified API, MCP, tool and provider bindings may be exposed as executable capabilities."},
        "changelog": {"rule": "Material identity, maturity, authority, provider, portal or behavior changes require versioned change evidence."},
        "support": {"owner": "CrownThrive LLC", "family_registry_id": snapshot.get("family_registry_id")},
    }
    missing = [section for section in required if section not in sections]
    if missing: raise PentaFamilyError("portal payload missing required sections: " + ", ".join(missing))
    return {"machine_key": machine_key, "portal_route": member.get("portal_route"), "portal_contract_state": "contracted", "sections": sections}


def load_family(root: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    registry = _load_json(root / "data/penta/family.registry.json")
    return registry, compose_family(root, registry)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify, snapshot and render the CrownThrive Penta Family"); parser.add_argument("--root", default="."); parser.add_argument("--member"); parser.add_argument("--portal", action="store_true"); args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        registry, snapshot = load_family(root); output: Dict[str, Any] = {"ok": True, "snapshot": snapshot}
        if args.member: output["dispatch_gate"] = member_dispatch_gate(snapshot, args.member)
        if args.portal: output["portal"] = member_portal(snapshot, registry, args.member) if args.member else snapshot["portal_index"]
        print(json.dumps(output, indent=2, sort_keys=True)); return 0
    except PentaFamilyError as exc:
        print(json.dumps({"ok": False, "family_status": "hold_fail_closed", "error": str(exc)}, indent=2)); return 1


if __name__ == "__main__": raise SystemExit(main())
