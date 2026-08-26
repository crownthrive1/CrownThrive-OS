#!/usr/bin/env python3
"""Validate and inspect CrownThrive's machine-readable PENTA system registry.

This utility is intentionally dependency-free so it can run in GitHub Actions,
local clones, recovery environments, and minimal operator shells.

It validates identity, authority-boundary, risk/maturity vocabulary, five-stage
coverage, aliases, and dependency references.  The registry's `dependencies`
field describes institutional dependencies, not a workflow execution DAG, so
cycles are allowed here; PentaMation workflow contracts must still resolve a
bounded executable dependency graph per run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "data" / "penta" / "systems.registry.json"
STAGES = ("discover", "govern", "execute", "verify", "preserve")
RISK_CLASSES = {"D0", "D1", "D2", "D3"}
MACHINE_KEY_PREFIX = "penta."


class RegistryError(ValueError):
    pass


def load_registry(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RegistryError(f"registry not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RegistryError(f"invalid JSON in {path}: {exc}") from exc


def validate_registry(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    systems = data.get("systems")
    allowed_maturity = set(data.get("status_vocabulary", []))

    if not isinstance(systems, list) or not systems:
        return ["systems must be a non-empty list"]
    if not allowed_maturity:
        errors.append("status_vocabulary must be a non-empty list")

    keys: set[str] = set()
    names: set[str] = set()
    aliases: dict[str, str] = {}

    required = {
        "machine_key",
        "canonical_name",
        "aliases",
        "category",
        "purpose",
        "human_surface",
        "authority_boundary",
        "risk_ceiling",
        "maturity",
        "dependencies",
        "five_stage",
    }

    for index, system in enumerate(systems):
        label = f"systems[{index}]"
        if not isinstance(system, dict):
            errors.append(f"{label} must be an object")
            continue

        missing = sorted(required - set(system))
        if missing:
            errors.append(f"{label} missing required fields: {', '.join(missing)}")
            continue

        key = system["machine_key"]
        name = system["canonical_name"]
        if not isinstance(key, str) or not key.startswith(MACHINE_KEY_PREFIX):
            errors.append(f"{label}.machine_key must start with '{MACHINE_KEY_PREFIX}'")
        elif key in keys:
            errors.append(f"duplicate machine_key: {key}")
        else:
            keys.add(key)

        if not isinstance(name, str) or not name.strip():
            errors.append(f"{label}.canonical_name must be non-empty")
        elif name.casefold() in names:
            errors.append(f"duplicate canonical_name: {name}")
        else:
            names.add(name.casefold())

        for text_field in ("category", "purpose", "human_surface", "authority_boundary"):
            value = system.get(text_field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{key or label}.{text_field} must be non-empty")

        risk = system.get("risk_ceiling")
        if risk not in RISK_CLASSES:
            errors.append(f"{key or label}.risk_ceiling must be one of {sorted(RISK_CLASSES)}")

        maturity = system.get("maturity")
        if maturity not in allowed_maturity:
            errors.append(f"{key or label}.maturity '{maturity}' is not in status_vocabulary")

        system_aliases = system.get("aliases")
        if not isinstance(system_aliases, list):
            errors.append(f"{key or label}.aliases must be a list")
        else:
            for alias in system_aliases:
                if not isinstance(alias, str) or not alias.strip():
                    errors.append(f"{key or label} has an empty/non-string alias")
                    continue
                folded = alias.casefold()
                previous = aliases.get(folded)
                if previous and previous != key:
                    errors.append(f"alias '{alias}' is claimed by both {previous} and {key}")
                aliases[folded] = key

        deps = system.get("dependencies")
        if not isinstance(deps, list) or any(not isinstance(dep, str) for dep in deps):
            errors.append(f"{key or label}.dependencies must be a list of machine keys")
        elif key in deps:
            errors.append(f"{key} cannot depend directly on itself")

        five_stage = system.get("five_stage")
        if not isinstance(five_stage, dict):
            errors.append(f"{key or label}.five_stage must be an object")
        else:
            missing_stages = [stage for stage in STAGES if not str(five_stage.get(stage, "")).strip()]
            extra_stages = sorted(set(five_stage) - set(STAGES))
            if missing_stages:
                errors.append(f"{key or label}.five_stage missing: {', '.join(missing_stages)}")
            if extra_stages:
                errors.append(f"{key or label}.five_stage has unknown keys: {', '.join(extra_stages)}")

    # Dependency references are checked after all keys are collected.
    for system in systems:
        if not isinstance(system, dict):
            continue
        key = system.get("machine_key", "<unknown>")
        deps = system.get("dependencies", [])
        if isinstance(deps, list):
            for dep in deps:
                if isinstance(dep, str) and dep not in keys:
                    errors.append(f"{key} references unknown dependency: {dep}")

    # Aliases cannot shadow another canonical name.
    for folded_name in names:
        if folded_name in aliases:
            errors.append(
                f"alias '{folded_name}' shadows a canonical system name owned by {aliases[folded_name]}"
            )

    return errors


def system_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["machine_key"]: item for item in data["systems"]}


def resolve_system(data: dict[str, Any], query: str) -> dict[str, Any] | None:
    query_fold = query.casefold()
    for system in data["systems"]:
        if system["machine_key"].casefold() == query_fold:
            return system
        if system["canonical_name"].casefold() == query_fold:
            return system
        if any(alias.casefold() == query_fold for alias in system.get("aliases", [])):
            return system
    return None


def dependency_closure(data: dict[str, Any], machine_key: str) -> list[str]:
    """Return a deterministic institutional dependency closure.

    Cycles are tolerated and broken by the visited set because dependencies here
    express institutional relationships, not a PentaMation run DAG.
    """
    index = system_index(data)
    visited: set[str] = set()
    ordered: list[str] = []

    def visit(key: str) -> None:
        if key in visited:
            return
        visited.add(key)
        for dep in sorted(index[key].get("dependencies", [])):
            visit(dep)
        ordered.append(key)

    visit(machine_key)
    return ordered


def print_summary(data: dict[str, Any]) -> None:
    systems = data["systems"]
    print(f"registry: {data.get('registry_id')}")
    print(f"schema: {data.get('schema_version')}")
    print(f"doctrine: {data.get('doctrine')}")
    print(f"systems: {len(systems)}")
    for system in sorted(systems, key=lambda item: item["canonical_name"].casefold()):
        print(
            f"- {system['canonical_name']} [{system['machine_key']}] "
            f"category={system['category']} maturity={system['maturity']} risk={system['risk_ceiling']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and inspect the CrownThrive PENTA system registry")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--system", help="Resolve a system by machine key, canonical name, or alias")
    parser.add_argument("--closure", action="store_true", help="Include institutional dependency closure with --system")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    try:
        data = load_registry(args.registry)
    except RegistryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    errors = validate_registry(data)
    if errors:
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            print("PENTA registry validation FAILED", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
        return 1

    if args.system:
        system = resolve_system(data, args.system)
        if system is None:
            print(f"system not found: {args.system}", file=sys.stderr)
            return 3
        result: dict[str, Any] = {"valid": True, "system": system}
        if args.closure:
            result["dependency_closure"] = dependency_closure(data, system["machine_key"])
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"{system['canonical_name']} [{system['machine_key']}]")
            print(system["purpose"])
            print(f"authority: {system['authority_boundary']}")
            if args.closure:
                print("dependency closure:")
                for key in result["dependency_closure"]:
                    print(f"- {key}")
        return 0

    if args.json:
        print(json.dumps({"valid": True, "systems": len(data["systems"]), "registry_id": data.get("registry_id")}, indent=2))
    else:
        print("PENTA registry validation PASS")
        print_summary(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
