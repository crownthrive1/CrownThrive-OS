"""Penta Family-of-Families discovery, validation, census, and portal runtime.

This runtime is intentionally standard-library only. It reconciles the three
canonical Penta identity surfaces without promoting maturity or authority:

1. machine Penta Family catalogs under data/penta;
2. the technical Penta component registry and PentaRoute primitive census;
3. the institutional PENTA-FAMILY-REGISTRY.md identity/portal inventory.

Every discovered Penta must resolve to exactly one primary institutional family.
Cross-family roles are secondary topology only. Unclassified or ambiguous names
fail closed so future Penta growth cannot silently escape institutionalization.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = Path("penta/registry/penta-families.v1.json")
PARENT_FAMILY_PATH = Path("data/penta/family.registry.json")
COMPONENT_REGISTRY_PATH = Path("penta/registry/penta-component-registry.v1.json")
INSTITUTIONAL_REGISTRY_PATH = Path("PENTA-FAMILY-REGISTRY.md")


class PentaFamiliesError(ValueError):
    """Raised when the family-of-families topology cannot be trusted."""


@dataclass
class DiscoveredPenta:
    normalized: str
    name: str
    source_classes: set[str] = field(default_factory=set)
    source_paths: set[str] = field(default_factory=set)
    machine_keys: set[str] = field(default_factory=set)
    categories: set[str] = field(default_factory=set)
    maturities: set[str] = field(default_factory=set)
    component_states: set[str] = field(default_factory=set)
    axes: set[str] = field(default_factory=set)
    contracts: set[str] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)
    portal_routes: set[str] = field(default_factory=set)

    def merge_name(self, candidate: str, priority: int, priorities: dict[str, int]) -> None:
        current = priorities.get(self.normalized, -1)
        if priority > current:
            self.name = canonical_display_name(candidate)
            priorities[self.normalized] = priority


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PentaFamiliesError(f"missing required source: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PentaFamiliesError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PentaFamiliesError(f"expected JSON object in {path}")
    return value


def canonical_display_name(name: str) -> str:
    return re.sub(r"[™®]", "", str(name)).strip()


def normalize_name(name: str) -> str:
    clean = canonical_display_name(name).casefold()
    return re.sub(r"[^a-z0-9]", "", clean)


def is_penta_name(name: str) -> bool:
    return normalize_name(name).startswith("penta")


def registry_family_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    families = registry.get("families")
    if not isinstance(families, list) or not families:
        raise PentaFamiliesError("families registry must contain families")
    ids: set[str] = set()
    slugs: set[str] = set()
    out: dict[str, dict[str, Any]] = {}
    for family in families:
        if not isinstance(family, dict):
            raise PentaFamiliesError("family entry is not an object")
        family_id = family.get("family_id")
        slug = family.get("slug")
        if not isinstance(family_id, str) or not family_id:
            raise PentaFamiliesError("family_id missing")
        if family_id in ids:
            raise PentaFamiliesError(f"duplicate family_id: {family_id}")
        if slug in slugs:
            raise PentaFamiliesError(f"duplicate family slug: {slug}")
        if family.get("portal_route") != f"/io/pentas/families/{slug}":
            raise PentaFamiliesError(f"family portal route drift: {family_id}")
        ids.add(family_id)
        slugs.add(str(slug))
        out[family_id] = family
    for family_id, family in out.items():
        for target in family.get("handoffs_to", []):
            if target not in out:
                raise PentaFamiliesError(f"unknown family handoff {family_id} -> {target}")
    return out


def ensure_discovered(
    inventory: dict[str, DiscoveredPenta],
    priorities: dict[str, int],
    name: str,
    source_class: str,
    source_path: str,
    display_priority: int,
) -> DiscoveredPenta:
    display = canonical_display_name(name)
    if not is_penta_name(display):
        raise PentaFamiliesError(f"non-Penta identity entered Penta inventory: {name!r}")
    normalized = normalize_name(display)
    if normalized not in inventory:
        inventory[normalized] = DiscoveredPenta(normalized=normalized, name=display)
        priorities[normalized] = display_priority
    item = inventory[normalized]
    item.merge_name(display, display_priority, priorities)
    item.source_classes.add(source_class)
    item.source_paths.add(source_path)
    return item


def system_catalog_paths(root: Path, parent_family: dict[str, Any]) -> list[Path]:
    paths: set[Path] = set()
    for catalog in parent_family.get("catalogs", []):
        rel = catalog.get("path") if isinstance(catalog, dict) else None
        if isinstance(rel, str) and rel.endswith(".json"):
            paths.add(Path(rel))
    for path in (root / "data/penta").glob("systems*.json"):
        paths.add(path.relative_to(root))
    return sorted(paths, key=lambda p: p.as_posix())


def discover_machine_catalogs(
    root: Path,
    inventory: dict[str, DiscoveredPenta],
    priorities: dict[str, int],
) -> list[str]:
    parent = load_json(root / PARENT_FAMILY_PATH)
    loaded: list[str] = []
    for rel in system_catalog_paths(root, parent):
        path = root / rel
        if not path.exists():
            # Parent required catalogs are validated elsewhere; here we preserve
            # fail-closed discovery for declared-but-missing family sources.
            declared = any(
                isinstance(c, dict) and c.get("path") == rel.as_posix() and c.get("required") is True
                for c in parent.get("catalogs", [])
            )
            if declared:
                raise PentaFamiliesError(f"missing required parent family catalog: {rel}")
            continue
        data = load_json(path)
        systems = data.get("systems")
        if not isinstance(systems, list):
            continue
        loaded.append(rel.as_posix())
        for system in systems:
            if not isinstance(system, dict):
                raise PentaFamiliesError(f"invalid system entry in {rel}")
            name = system.get("canonical_name")
            if not isinstance(name, str) or not is_penta_name(name):
                raise PentaFamiliesError(f"invalid machine Penta name in {rel}: {name!r}")
            item = ensure_discovered(inventory, priorities, name, "machine", rel.as_posix(), 30)
            key = system.get("machine_key")
            if isinstance(key, str) and key:
                item.machine_keys.add(key)
            category = system.get("category")
            if isinstance(category, str) and category:
                item.categories.add(category)
            maturity = system.get("maturity")
            if isinstance(maturity, str) and maturity:
                item.maturities.add(maturity)
            purpose = system.get("purpose")
            if isinstance(purpose, str) and purpose:
                item.roles.add(purpose)
    return loaded


def discover_component_registry(
    root: Path,
    inventory: dict[str, DiscoveredPenta],
    priorities: dict[str, int],
) -> list[str]:
    rel = COMPONENT_REGISTRY_PATH
    data = load_json(root / rel)
    components = data.get("components")
    if not isinstance(components, list):
        raise PentaFamiliesError("component registry missing components")
    primitive_names: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            raise PentaFamiliesError("invalid component registry entry")
        name = component.get("name")
        if not isinstance(name, str) or not is_penta_name(name):
            raise PentaFamiliesError(f"invalid technical Penta name: {name!r}")
        item = ensure_discovered(inventory, priorities, name, "component", rel.as_posix(), 20)
        key = component.get("key")
        if isinstance(key, str) and key:
            item.machine_keys.add(key)
        state = component.get("state")
        if isinstance(state, str) and state:
            item.component_states.add(state)
        axis = component.get("axis")
        if isinstance(axis, str) and axis:
            item.axes.add(axis)
        contract = component.get("contract")
        if isinstance(contract, str) and contract:
            item.contracts.add(contract)
        role = component.get("role")
        if isinstance(role, str) and role:
            item.roles.add(role)
        if normalize_name(name) == "pentaroute":
            primitives = component.get("primitives", [])
            if not isinstance(primitives, list):
                raise PentaFamiliesError("PentaRoute primitives must be an array")
            primitive_names.update(str(x) for x in primitives if isinstance(x, str))
    for name in sorted(primitive_names):
        ensure_discovered(inventory, priorities, name, "route_primitive", rel.as_posix(), 10)
    return [rel.as_posix()]


def parse_institutional_table(text: str) -> Iterable[tuple[str, str, str]]:
    # Three-column canonical Penta table: name | role | /io/pentas/...
    pattern = re.compile(
        r"^\|\s*(Penta[^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(`?/io/pentas/[^|`\s]+`?)\s*\|$",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        name = re.sub(r"[*`]", "", match.group(1)).strip()
        role = re.sub(r"[*`]", "", match.group(2)).strip()
        route = match.group(3).strip("` ")
        if is_penta_name(name):
            yield name, role, route


def parse_institutional_primitives(text: str) -> set[str]:
    heading = "### Registered primitive/capability family"
    if heading not in text:
        return set()
    tail = text.split(heading, 1)[1]
    tail = tail.split("\n## ", 1)[0]
    return {
        canonical_display_name(token)
        for token in re.findall(r"\*\*(Penta[^*]+)\*\*", tail)
        if is_penta_name(token)
    }


def discover_institutional_registry(
    root: Path,
    inventory: dict[str, DiscoveredPenta],
    priorities: dict[str, int],
) -> list[str]:
    rel = INSTITUTIONAL_REGISTRY_PATH
    try:
        text = (root / rel).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PentaFamiliesError(f"missing institutional registry: {rel}") from exc
    for name, role, route in parse_institutional_table(text):
        item = ensure_discovered(inventory, priorities, name, "institutional", rel.as_posix(), 15)
        item.roles.add(role)
        item.portal_routes.add(route)
    for name in sorted(parse_institutional_primitives(text)):
        ensure_discovered(inventory, priorities, name, "institutional_primitive", rel.as_posix(), 10)
    return [rel.as_posix()]


def build_inventory(root: Path) -> tuple[dict[str, DiscoveredPenta], dict[str, Any]]:
    registry = load_json(root / REGISTRY_PATH)
    if registry.get("status") != "production":
        raise PentaFamiliesError("family-of-families registry must remain production")
    if registry.get("parent_family") != "Penta Family":
        raise PentaFamiliesError("unexpected parent family")
    required_true = [
        "every_discovered_penta_has_primary_family",
        "exactly_one_primary_family",
        "family_assignment_does_not_promote_maturity",
        "family_assignment_does_not_create_authority",
        "unknown_or_unclassified_penta_fails_closed",
        "future_registry_growth_must_be_classified",
        "family_portals_required",
        "family_portal_state_independent_from_member_maturity",
    ]
    invariants = registry.get("invariants", {})
    for key in required_true:
        if invariants.get(key) is not True:
            raise PentaFamiliesError(f"family invariant must remain true: {key}")

    inventory: dict[str, DiscoveredPenta] = {}
    priorities: dict[str, int] = {}
    sources: list[str] = []
    sources.extend(discover_machine_catalogs(root, inventory, priorities))
    sources.extend(discover_component_registry(root, inventory, priorities))
    sources.extend(discover_institutional_registry(root, inventory, priorities))
    if not inventory:
        raise PentaFamiliesError("discovery returned zero Pentas")
    return inventory, {"registry": registry, "sources": sorted(set(sources))}


def explicit_assignment_map(families: dict[str, dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for family_id, family in families.items():
        for name in family.get("explicit_members", []):
            normalized = normalize_name(name)
            existing = mapping.get(normalized)
            if existing and existing != family_id:
                raise PentaFamiliesError(
                    f"explicit primary-family collision for {name}: {existing}, {family_id}"
                )
            mapping[normalized] = family_id
    return mapping


def category_matches(item: DiscoveredPenta, family: dict[str, Any]) -> bool:
    patterns = family.get("machine_category_patterns", [])
    for pattern in patterns:
        try:
            compiled = re.compile(str(pattern), re.IGNORECASE)
        except re.error as exc:
            raise PentaFamiliesError(f"invalid family category regex {pattern!r}: {exc}") from exc
        for category in item.categories:
            if compiled.search(category):
                return True
    return False


def assign_primary_families(
    inventory: dict[str, DiscoveredPenta], registry: dict[str, Any]
) -> tuple[dict[str, str], list[str]]:
    families = registry_family_map(registry)
    explicit = explicit_assignment_map(families)
    primitive_default = registry["classification"]["route_primitive_only_family"]
    if primitive_default not in families:
        raise PentaFamiliesError("route primitive default family does not exist")
    assignments: dict[str, str] = {}
    unclassified: list[str] = []

    for normalized, item in sorted(inventory.items()):
        if normalized in explicit:
            assignments[normalized] = explicit[normalized]
            continue
        matches = [fid for fid, family in families.items() if category_matches(item, family)]
        if len(matches) == 1:
            assignments[normalized] = matches[0]
            continue
        if len(matches) > 1:
            raise PentaFamiliesError(
                f"ambiguous primary family for {item.name}: {', '.join(sorted(matches))}"
            )
        if "route_primitive" in item.source_classes or "institutional_primitive" in item.source_classes:
            assignments[normalized] = primitive_default
            continue
        unclassified.append(item.name)

    if unclassified:
        raise PentaFamiliesError(
            "unclassified Penta identities: " + ", ".join(sorted(unclassified))
        )
    if len(assignments) != len(inventory):
        raise PentaFamiliesError("not every discovered Penta received a primary family")
    return assignments, unclassified


def secondary_family_map(registry: dict[str, Any], family_ids: set[str]) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for name, roles in registry.get("cross_family_assignments", {}).items():
        if not isinstance(roles, list):
            raise PentaFamiliesError(f"cross-family roles must be list for {name}")
        unknown = sorted(set(roles) - family_ids)
        if unknown:
            raise PentaFamiliesError(f"unknown secondary family for {name}: {unknown}")
        output[normalize_name(name)] = sorted(set(str(x) for x in roles))
    return output


def evidence_state(item: DiscoveredPenta) -> dict[str, Any]:
    maturity = sorted(item.maturities)
    component_states = sorted(item.component_states)
    execution_eligible = bool(set(maturity) & {"certified", "production"})
    return {
        "machine_maturity": maturity,
        "technical_component_state": component_states,
        "execution_eligible_from_machine_maturity": execution_eligible,
        "family_assignment_promoted_member": False,
    }


def compose_snapshot(root: Path) -> dict[str, Any]:
    inventory, context = build_inventory(root)
    registry = context["registry"]
    families = registry_family_map(registry)
    assignments, _ = assign_primary_families(inventory, registry)
    secondary = secondary_family_map(registry, set(families))

    members_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for normalized, item in sorted(inventory.items(), key=lambda kv: kv[1].name.casefold()):
        primary = assignments[normalized]
        secondary_roles = [x for x in secondary.get(normalized, []) if x != primary]
        members_by_family[primary].append(
            {
                "name": item.name,
                "normalized_name": normalized,
                "primary_family": primary,
                "secondary_families": secondary_roles,
                "source_classes": sorted(item.source_classes),
                "source_paths": sorted(item.source_paths),
                "machine_keys": sorted(item.machine_keys),
                "categories": sorted(item.categories),
                "axes": sorted(item.axes),
                "contracts": sorted(item.contracts),
                "portal_routes": sorted(item.portal_routes),
                "evidence_state": evidence_state(item),
            }
        )

    family_rows: list[dict[str, Any]] = []
    for family_id, family in families.items():
        members = members_by_family.get(family_id, [])
        family_rows.append(
            {
                "family_id": family_id,
                "canonical_name": family["canonical_name"],
                "slug": family["slug"],
                "mission": family["mission"],
                "portal_route": family["portal_route"],
                "member_count": len(members),
                "members": members,
                "handoffs_to": sorted(family.get("handoffs_to", [])),
            }
        )

    source_class_counts = Counter(
        source_class for item in inventory.values() for source_class in item.source_classes
    )
    maturity_counts = Counter(
        maturity for item in inventory.values() for maturity in item.maturities
    )
    return {
        "registry_id": registry["registry_id"],
        "status": "production",
        "production_scope": registry["production_scope"],
        "parent_family": registry["parent_family"],
        "family_count": len(families),
        "discovered_penta_count": len(inventory),
        "classified_penta_count": len(assignments),
        "unclassified_penta_count": 0,
        "discovery_sources": context["sources"],
        "source_class_counts": dict(sorted(source_class_counts.items())),
        "machine_maturity_counts": dict(sorted(maturity_counts.items())),
        "portal_index_route": registry["portal_contract"]["index_route"],
        "portal_state": registry["portal_contract"]["portal_state"],
        "portal_state_is_frontend_deployment_claim": False,
        "family_assignment_promotes_members": False,
        "authority_manufactured": False,
        "families": family_rows,
    }


def family_portal(snapshot: dict[str, Any], registry: dict[str, Any], family_id: str) -> dict[str, Any]:
    target = next((f for f in snapshot["families"] if f["family_id"] == family_id), None)
    if target is None:
        raise PentaFamiliesError(f"unknown family portal: {family_id}")
    family_config = registry_family_map(registry)[family_id]
    required_sections = registry["portal_contract"]["required_sections"]
    member_names = [member["name"] for member in target["members"]]
    payload: dict[str, Any] = {
        "family_id": family_id,
        "canonical_name": target["canonical_name"],
        "portal_route": target["portal_route"],
        "portal_state": "contracted",
        "frontend_deployment_claim": False,
        "primary_member_count": target["member_count"],
        "sections": {
            "story": f"{target['canonical_name']} is one operating family beneath Penta Family and groups related institutional responsibilities without changing child authority or maturity.",
            "mission": target["mission"],
            "member_census": member_names,
            "member_status": [
                {"name": m["name"], **m["evidence_state"]} for m in target["members"]
            ],
            "responsibilities": sorted({role for m in target["members"] for role in inventory_roles(m)}),
            "inputs_outputs": "Family-level topology only; exact inputs and outputs remain defined by each child system contract and interoperability envelope.",
            "authority_boundary": "Family membership never creates maturity, credentials, provider permission, rights, money-movement authority, legal sufficiency, governance authority or D3 authority.",
            "cross_family_handoffs": family_config.get("handoffs_to", []),
            "operations": "Operate through registered child portals, PentaRoute/PentaMCP interoperability, applicable readiness gates, exact provider bindings and readback.",
            "sops_slas": "Use member-specific PentaSOPs/PentaSLAs records and family escalation contracts; no family-level prose silently changes a child SLA.",
            "evidence": "Machine snapshot is composed from current registries at read time; child certification and production evidence remain independently scoped.",
            "api_mcp": "Use exact registered member machine keys and Penta interoperability envelopes; family portal is not an unrestricted API proxy.",
            "incidents_recovery": "Route incidents through PentaTriage/PentaStatus and applicable security/resilience families; preserve rollback and evidence.",
            "releases_changelog": "Family topology changes are versioned control-plane changes; member releases remain independently versioned.",
            "roadmap": "New members must be registered, classified, documented, given portal coverage, tested and reconciled before the family verifier passes.",
            "support": "PentaDocs is the documentation plane; CrownThrive IO is the operating surface; accountable owners remain system-specific."
        },
    }
    missing = [section for section in required_sections if section not in payload["sections"]]
    if missing:
        raise PentaFamiliesError(f"family portal missing required sections: {missing}")
    return payload


def inventory_roles(member: dict[str, Any]) -> set[str]:
    # Portal snapshot intentionally does not expose every raw purpose string to
    # stay concise. Source classes/categories provide deterministic role cues.
    roles = set(member.get("categories", []))
    roles.update(member.get("axes", []))
    return {role for role in roles if role}


def portal_index(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "family_id": family["family_id"],
            "canonical_name": family["canonical_name"],
            "portal_route": family["portal_route"],
            "member_count": family["member_count"],
        }
        for family in snapshot["families"]
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and render the CrownThrive Penta family-of-families topology")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--family", help="render one family portal by family_id")
    parser.add_argument("--portal-index", action="store_true", help="render family portal index")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        registry = load_json(root / REGISTRY_PATH)
        snapshot = compose_snapshot(root)
        output: dict[str, Any] = {"ok": True, "snapshot": snapshot}
        if args.portal_index:
            output["portal_index"] = portal_index(snapshot)
        if args.family:
            output["family_portal"] = family_portal(snapshot, registry, args.family)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except PentaFamiliesError as exc:
        print(json.dumps({"ok": False, "disposition": "hold_fail_closed", "error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
