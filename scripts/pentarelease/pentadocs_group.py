#!/usr/bin/env python3
"""Manage the PentaRelease group inside an existing canonical PentaDocs tab.

This deliberately does not create top-level tabs. PentaRelease is a release
surface inside the institutional docs navigation, not an independent docs
universe.
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


def inspect(repo_root: Path, policy_path: Path) -> dict[str, Any]:
    release_surface, cfg, docs_path, _ = config(repo_root, policy_path)
    if not cfg.get("enabled", True):
        return {"healthy": True, "reason": "pentadocs_disabled"}

    docs = read_json(docs_path, {})
    tabs = ((docs.get("navigation") or {}).get("tabs") or [])
    max_tabs = int(release_surface.get("max_pentadocs_tabs", 8))
    tab_name = str(cfg.get("tab") or "CrownThrive OS")
    group_name = str(cfg.get("group") or "PentaRelease")
    expected_pages = list(cfg.get("pages") or [])

    if len(tabs) > max_tabs:
        return {"healthy": False, "reason": "pentadocs_tab_limit_exceeded", "tab_count": len(tabs), "max_tabs": max_tabs}

    matches = [tab for tab in tabs if isinstance(tab, dict) and tab.get("tab") == tab_name]
    if len(matches) != 1:
        return {"healthy": False, "reason": "target_tab_missing_or_duplicate", "target_tab": tab_name, "matches": len(matches)}

    pages = matches[0].get("pages")
    if not isinstance(pages, list):
        return {"healthy": False, "reason": "target_tab_pages_not_list", "target_tab": tab_name}

    groups = [item for item in pages if isinstance(item, dict) and item.get("group") == group_name]
    if len(groups) != 1:
        return {"healthy": False, "reason": "release_group_missing_or_duplicate", "group": group_name, "matches": len(groups)}
    if list(groups[0].get("pages") or []) != expected_pages:
        return {"healthy": False, "reason": "release_group_pages_mismatch", "group": group_name}

    missing = [page for page in expected_pages if not (repo_root / f"{page}.mdx").is_file()]
    if missing:
        return {"healthy": False, "reason": "missing_pentadocs_page", "missing": missing}

    return {
        "healthy": True,
        "reason": "nested_release_group_present",
        "target_tab": tab_name,
        "group": group_name,
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

    tab_name = str(cfg.get("tab") or "CrownThrive OS")
    group_name = str(cfg.get("group") or "PentaRelease")
    expected_pages = list(cfg.get("pages") or [])
    target_matches = [i for i, tab in enumerate(tabs) if isinstance(tab, dict) and tab.get("tab") == tab_name]
    if len(target_matches) != 1:
        raise RuntimeError(f"PentaRelease target PentaDocs tab {tab_name!r} must exist exactly once; observed {len(target_matches)}")

    target = tabs[target_matches[0]]
    pages = target.get("pages")
    if not isinstance(pages, list):
        raise RuntimeError(f"PentaRelease target PentaDocs tab {tab_name!r} does not expose a pages list")

    group_matches = [i for i, item in enumerate(pages) if isinstance(item, dict) and item.get("group") == group_name]
    if len(group_matches) > 1:
        raise RuntimeError(f"PentaRelease group {group_name!r} appears more than once in {tab_name!r}")

    expected = {"group": group_name, "icon": "box-archive", "pages": expected_pages}
    state = read_json(state_path, {})
    prior = state.get("pentadocs_group") or {}

    if group_matches:
        idx = group_matches[0]
        existing = pages[idx]
        if prior.get("managed_by_pentarelease"):
            pages[idx] = expected
            status = "updated_managed_group"
        elif list(existing.get("pages") or []) == expected_pages:
            status = "adopted_exact_existing_group"
        else:
            raise RuntimeError(
                f"pre-existing unmanaged PentaRelease group conflicts with governed pages in {tab_name!r}"
            )
    else:
        pages.append(expected)
        status = "created_managed_group"

    state["pentadocs_group"] = {
        "tab": tab_name,
        "group": group_name,
        "managed_by_pentarelease": True,
        "top_level_tab_created": False,
        "status": status,
        "pages": expected_pages,
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
