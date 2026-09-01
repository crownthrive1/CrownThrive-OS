#!/usr/bin/env python3
"""Validate and materialize CrownThrive's composed GitHub repository resource set.

This module is intentionally local/read-only. It grants no GitHub, provider, runtime,
financial, deployment, certification, or D3 authority. Static exact heads are evidence
snapshots only; live heads must still be resolved immediately before execution.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SET = ROOT / ".crownthrive" / "resources" / "repository-resource-set.v1.json"


class RegistryError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RegistryError(f"missing registry resource: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RegistryError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RegistryError(f"registry resource must be an object: {path}")
    return value


def _resolve(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise RegistryError(f"registry path escapes repository root: {relative}") from exc
    return path


def compose(set_path: Path = DEFAULT_SET) -> dict[str, Any]:
    registry_set = _load(set_path)
    if registry_set.get("contract") != "ct.repository-resource-registry-set.v1":
        raise RegistryError("unexpected registry-set contract")

    base_spec = registry_set.get("base_registry") or {}
    extension_specs = registry_set.get("extensions") or []
    census_spec = registry_set.get("provider_census") or {}
    if not isinstance(extension_specs, list):
        raise RegistryError("extensions must be a list")

    base = _load(_resolve(str(base_spec.get("path", ""))))
    base_resources = base.get("resources") or []
    if len(base_resources) != int(base_spec.get("count", -1)):
        raise RegistryError("base registry count mismatch")

    composed: list[dict[str, Any]] = []
    seen: set[str] = set()

    def admit(item: Any, source: str) -> None:
        if not isinstance(item, dict):
            raise RegistryError(f"non-object repository entry in {source}")
        repository = item.get("repository")
        if not isinstance(repository, str) or not repository.startswith("crownthrive1/"):
            raise RegistryError(f"invalid repository identity in {source}: {repository!r}")
        if repository in seen:
            raise RegistryError(f"duplicate repository resource: {repository}")
        if item.get("requires_exact_head_before_execution") is not True:
            raise RegistryError(f"live-head requirement missing: {repository}")
        if item.get("may_grant_provider_or_d3_authority") is not False:
            raise RegistryError(f"provider/D3 authority invariant failed: {repository}")
        if item.get("resource_class") == "REFERENCE_FORK":
            if item.get("authority") != "reference_only":
                raise RegistryError(f"reference fork authority drift: {repository}")
            if item.get("sync_policy") != "PURE_REFERENCE_FAST_FORWARD":
                raise RegistryError(f"reference fork sync-policy drift: {repository}")
        seen.add(repository)
        composed.append(item)

    for item in base_resources:
        admit(item, str(base_spec.get("path")))

    for extension_spec in extension_specs:
        extension = _load(_resolve(str(extension_spec.get("path", ""))))
        resources = extension.get("resources") or []
        if len(resources) != int(extension_spec.get("count", -1)):
            raise RegistryError(f"extension count mismatch: {extension_spec.get('path')}")
        for item in resources:
            admit(item, str(extension_spec.get("path")))

    target_count = int(registry_set.get("composed_governed_resource_count", -1))
    if len(composed) != target_count:
        raise RegistryError(f"composed resource count mismatch: {len(composed)} != {target_count}")

    census = _load(_resolve(str(census_spec.get("path", ""))))
    nonempty = census.get("nonempty_repositories") or []
    empty = census.get("empty_placeholders") or []
    if len(nonempty) != int(census_spec.get("nonempty_repository_count", -1)):
        raise RegistryError("non-empty provider census count mismatch")
    if len(empty) != int(census_spec.get("empty_placeholder_count", -1)):
        raise RegistryError("empty provider census count mismatch")
    accessible = int(census_spec.get("accessible_repository_count", -1))
    if accessible != len(nonempty) + len(empty):
        raise RegistryError("accessible provider census arithmetic mismatch")
    if len(set(nonempty)) != len(nonempty) or len(set(empty)) != len(empty):
        raise RegistryError("provider census contains duplicate repository names")
    if set(nonempty) & set(empty):
        raise RegistryError("provider census non-empty/empty classes overlap")

    provider_names = {f"crownthrive1/{name}" for name in [*nonempty, *empty]}
    governed_names = set(seen)
    missing_from_provider = governed_names - provider_names
    if missing_from_provider:
        raise RegistryError(f"governed resources missing from provider census: {sorted(missing_from_provider)}")
    nonempty_full = {f"crownthrive1/{name}" for name in nonempty}
    missing_nonempty = nonempty_full - governed_names
    if missing_nonempty:
        raise RegistryError(f"non-empty provider repos missing from governed set: {sorted(missing_nonempty)}")

    governed_empty = governed_names - nonempty_full
    if governed_empty != {"crownthrive1/private-chlom"}:
        raise RegistryError(f"unexpected governed empty placeholders: {sorted(governed_empty)}")

    holds = registry_set.get("holds") or []
    for hold in holds:
        repo = hold.get("repository")
        if repo not in governed_names:
            raise RegistryError(f"hold references unknown governed repository: {repo}")
        if hold.get("mutation_authority_from_hold") is not False:
            raise RegistryError(f"hold may not grant mutation authority: {repo}")

    return {
        "contract": "ct.repository-resource-registry-materialized.v1",
        "registry_set_version": registry_set.get("version"),
        "governed_resource_count": len(composed),
        "provider_repository_count": accessible,
        "provider_nonempty_count": len(nonempty),
        "provider_empty_placeholder_count": len(empty),
        "governed_empty_placeholder_count": len(governed_empty),
        "holds": holds,
        "resources": composed,
        "authority": {
            "runtime_authority_granted": False,
            "provider_write_granted": False,
            "money_movement_granted": False,
            "d3_authority_granted": False,
            "force_reset_authority_granted": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", dest="set_path", type=Path, default=DEFAULT_SET)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    materialized = compose(args.set_path)
    if args.summary:
        print(json.dumps({k: v for k, v in materialized.items() if k != "resources"}, indent=2, sort_keys=True))
    else:
        print(json.dumps(materialized, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
