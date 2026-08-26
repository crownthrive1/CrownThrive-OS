"""Production control-plane runtime for the CrownThrive Penta Family.

The Penta Family is an umbrella registry and dispatch guard. A production family
never promotes a child system automatically: each member retains its own
maturity and may execute only when its own state and authority gates permit it.

This module is dependency-free so it can run in CI, local operator checks, and
minimal recovery environments.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

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
                raise PentaFamilyError(
                    f"duplicate machine_key {machine_key}: {first} and {rel}"
                )
            members[machine_key] = system
            member_sources[machine_key] = rel

    if missing_catalogs:
        raise PentaFamilyError(
            "missing required family catalogs: " + ", ".join(sorted(missing_catalogs))
        )
    if not members:
        raise PentaFamilyError("family has no registered members")

    maturity_counts = Counter(system["maturity"] for system in members.values())
    execution_eligible = sorted(
        key for key, system in members.items() if system["maturity"] in EXECUTION_ELIGIBLE
    )
    held = sorted(
        key for key, system in members.items() if system["maturity"] in {"hold", "retired"}
    )

    return {
        "family_registry_id": registry["registry_id"],
        "family_status": "production",
        "production_scope": registry["production_scope"],
        "fail_closed": True,
        "member_count": len(members),
        "maturity_counts": dict(sorted(maturity_counts.items())),
        "execution_eligible_members": execution_eligible,
        "held_members": held,
        "members": {
            key: {
                "canonical_name": members[key]["canonical_name"],
                "maturity": members[key]["maturity"],
                "source": member_sources[key],
            }
            for key in sorted(members)
        },
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


def load_family(root: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    registry = _load_json(root / "data/penta/family.registry.json")
    return registry, compose_family(root, registry)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and snapshot the CrownThrive Penta Family")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--member", help="optionally evaluate one member dispatch gate")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        _, snapshot = load_family(root)
        output: Dict[str, Any] = {"ok": True, "snapshot": snapshot}
        if args.member:
            output["dispatch_gate"] = member_dispatch_gate(snapshot, args.member)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except PentaFamilyError as exc:
        print(json.dumps({"ok": False, "family_status": "hold_fail_closed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
