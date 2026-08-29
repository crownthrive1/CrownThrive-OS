#!/usr/bin/env python3
"""Manage the PentaRelease group inside an existing canonical PentaDocs tab.

PentaRelease never creates a competing top-level docs universe. The synchronizer
supports Mintlify tabs whose child groups live under either ``pages`` or ``groups``
and enforces exactly one global owner for every governed PentaRelease route.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def config(repo_root: Path, policy_path: Path) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    policy = read_json(policy_path, {})
    release_surface = policy.get("release_surface") or {}
    cfg = release_surface.get("pentadocs") or {}
    docs_path = repo_root / str(cfg.get("config") or "docs.json")
    state_path = repo_root / str(release_surface.get("state_file") or ".pentarelease/state/release-surface.json")
    return release_surface, cfg, docs_path, state_path


def navigation_items(tab: dict[str, Any]) -> tuple[str | None, list[Any] | None]:
    groups = tab.get("groups")
    if isinstance(groups, list):
        return "groups", groups
    pages = tab.get("pages")
    if isinstance(pages, list):
        return "pages", pages
    return None, None


def route_owners(tabs: list[Any], routes: list[str]) -> dict[str, list[dict[str, Any]]]:
    wanted = set(routes)
    owners: dict[str, list[dict[str, Any]]] = {route: [] for route in routes}
    for tab_index, raw_tab in enumerate(tabs):
        if not isinstance(raw_tab, dict):
            continue
        nav_key, items = navigation_items(raw_tab)
        if not items:
            continue
        tab_name = str(raw_tab.get("tab") or f"tab[{tab_index}]")
        for item_index, item in enumerate(items):
            if isinstance(item, str):
                if item in wanted:
                    owners[item].append({
                        "tab": tab_name,
                        "group": None,
                        "navigation_key": nav_key,
                        "item_index": item_index,
                    })
                continue
            if not isinstance(item, dict):
                continue
            group_name = item.get("group")
            child_pages = item.get("pages")
            if not isinstance(child_pages, list):
                continue
            for page in child_pages:
                if isinstance(page, str) and page in wanted:
                    owners[page].append({
                        "tab": tab_name,
                        "group": group_name,
                        "navigation_key": nav_key,
                        "item_index": item_index,
                    })
    return owners


def route_health(tabs: list[Any], routes: list[str], tab_name: str, group_name: str) -> tuple[bool, dict[str, list[dict[str, Any]]]]:
    owners = route_owners(tabs, routes)
    for route in routes:
        matches = owners.get(route) or []
        if len(matches) != 1:
            return False, owners
        owner = matches[0]
        if owner.get("tab") != tab_name or owner.get("group") != group_name:
            return False, owners
    return True, owners


def inspect(repo_root: Path, policy_path: Path) -> dict[str, Any]:
    release_surface, cfg, docs_path, _ = config(repo_root, policy_path)
    if not cfg.get("enabled", True):
        return {"healthy": True, "reason": "pentadocs_disabled"}

    docs = read_json(docs_path, {})
    tabs = ((docs.get("navigation") or {}).get("tabs") or [])
    max_tabs = int(release_surface.get("max_pentadocs_tabs", 8))
    tab_name = str(cfg.get("tab") or "Releases & Evidence")
    group_name = str(cfg.get("group") or "PentaRelease")
    expected_pages = list(cfg.get("pages") or [])

    if len(tabs) > max_tabs:
        return {"healthy": False, "reason": "pentadocs_tab_limit_exceeded", "tab_count": len(tabs), "max_tabs": max_tabs}

    matches = [tab for tab in tabs if isinstance(tab, dict) and tab.get("tab") == tab_name]
    if len(matches) != 1:
        return {"healthy": False, "reason": "target_tab_missing_or_duplicate", "target_tab": tab_name, "matches": len(matches)}

    nav_key, items = navigation_items(matches[0])
    if not isinstance(items, list):
        return {"healthy": False, "reason": "target_tab_navigation_not_list", "target_tab": tab_name}

    groups = [item for item in items if isinstance(item, dict) and item.get("group") == group_name]
    if len(groups) != 1:
        return {"healthy": False, "reason": "release_group_missing_or_duplicate", "group": group_name, "matches": len(groups)}
    if list(groups[0].get("pages") or []) != expected_pages:
        return {"healthy": False, "reason": "release_group_pages_mismatch", "group": group_name}

    unique_routes, owners = route_health(tabs, expected_pages, tab_name, group_name)
    if not unique_routes:
        return {
            "healthy": False,
            "reason": "release_route_owner_conflict",
            "target_tab": tab_name,
            "group": group_name,
            "route_owners": owners,
        }

    missing = [page for page in expected_pages if not (repo_root / f"{page}.mdx").is_file()]
    if missing:
        return {"healthy": False, "reason": "missing_pentadocs_page", "missing": missing}

    return {
        "healthy": True,
        "reason": "nested_release_group_present_unique_routes",
        "target_tab": tab_name,
        "group": group_name,
        "navigation_key": nav_key,
        "tab_count": len(tabs),
        "max_tabs": max_tabs,
    }


def sync(repo_root: Path, policy_path: Path) -> dict[str, Any]:
    release_surface, cfg, docs_path, state_path = config(repo_root, policy_path)
    if not cfg.get("enabled", True):
        return {"status": "disabled"}

    docs = read_json(docs_path, {})
    navigation = docs.setdefault("navigation", {})
    tabs = navigation.setdefault("tabs", [])
    max_tabs = int(release_surface.get("max_pentadocs_tabs", 8))
    if len(tabs) > max_tabs:
        raise RuntimeError(f"PentaDocs contains {len(tabs)} tabs; maximum configured is {max_tabs}")

    tab_name = str(cfg.get("tab") or "Releases & Evidence")
    group_name = str(cfg.get("group") or "PentaRelease")
    expected_pages = list(cfg.get("pages") or [])
    target_matches = [i for i, tab in enumerate(tabs) if isinstance(tab, dict) and tab.get("tab") == tab_name]
    if len(target_matches) != 1:
        raise RuntimeError(f"PentaRelease target PentaDocs tab {tab_name!r} must exist exactly once; observed {len(target_matches)}")

    target = tabs[target_matches[0]]
    nav_key, items = navigation_items(target)
    if not isinstance(items, list):
        raise RuntimeError(f"PentaRelease target PentaDocs tab {tab_name!r} does not expose a groups/pages list")

    owners_before = route_owners(tabs, expected_pages)
    for route, owners in owners_before.items():
        outside = [owner for owner in owners if owner.get("tab") != tab_name or owner.get("group") != group_name]
        if outside:
            raise RuntimeError(
                f"PentaRelease route {route!r} is already owned outside canonical {tab_name!r}/{group_name!r}: {outside}"
            )
        if len(owners) > 1:
            raise RuntimeError(f"PentaRelease route {route!r} has duplicate owners: {owners}")

    group_matches = [i for i, item in enumerate(items) if isinstance(item, dict) and item.get("group") == group_name]
    if len(group_matches) > 1:
        raise RuntimeError(f"PentaRelease group {group_name!r} appears more than once in {tab_name!r}")

    state = read_json(state_path, {})
    prior = state.get("pentadocs_group") or {}

    if group_matches:
        idx = group_matches[0]
        existing = items[idx]
        existing_pages = list(existing.get("pages") or [])
        if prior.get("managed_by_pentarelease"):
            updated = dict(existing)
            updated["group"] = group_name
            updated.setdefault("icon", "box-archive")
            updated["pages"] = expected_pages
            items[idx] = updated
            status = "updated_managed_group"
        elif existing_pages == expected_pages:
            status = "adopted_exact_existing_group"
        else:
            raise RuntimeError(
                f"pre-existing unmanaged PentaRelease group conflicts with governed pages in {tab_name!r}"
            )
    else:
        items.append({"group": group_name, "icon": "box-archive", "pages": expected_pages})
        status = "created_managed_group"

    unique_routes, owners_after = route_health(tabs, expected_pages, tab_name, group_name)
    if not unique_routes:
        raise RuntimeError(f"PentaRelease route ownership is not unique after synchronization: {owners_after}")

    state["pentadocs_group"] = {
        "tab": tab_name,
        "group": group_name,
        "navigation_key": nav_key,
        "managed_by_pentarelease": True,
        "top_level_tab_created": False,
        "status": status,
        "pages": expected_pages,
        "unique_route_ownership_verified": True,
    }
    write_json(docs_path, docs)
    write_json(state_path, state)
    return state["pentadocs_group"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default=".pentarelease/policy.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy = (root / args.policy).resolve()
    if args.check:
        result = inspect(root, policy)
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("healthy") else 1

    result = sync(root, policy)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
