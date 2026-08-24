#!/usr/bin/env python3
"""Reconcile the comprehensive CrownThrive docs navigation into the tabbed IA.

This script is intentionally deterministic and fail-closed. It transforms the
legacy comprehensive `navigation.groups` tree into the current four-tab model,
then scans repository MDX files and wires only genuinely unlisted pages into
bounded catch-up groups. It never edits MDX bodies.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs.json"

TAB_OS = "CrownThrive OS"
TAB_CHLOM = "CHLOM"
TAB_DEV = "Developers"
TAB_SUPPORT = "Support & Licensing"

# Root legacy groups that belong outside the CrownThrive OS tab.
CHLOM_GROUPS = {"CHLOM"}
DEV_GROUPS = {"Developer Platform"}
SUPPORT_GROUPS = {"Support, Legal & Knowledge"}

# Files that are intentionally not page routes.
IGNORE_MDX_PREFIXES = ()


def page_strings(node: Any) -> Iterable[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for item in node:
            yield from page_strings(item)
    elif isinstance(node, dict):
        if isinstance(node.get("pages"), list):
            yield from page_strings(node["pages"])
        if isinstance(node.get("groups"), list):
            yield from page_strings(node["groups"])


def normalize_route(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    assert rel.endswith(".mdx")
    return rel[:-4]


def all_mdx_routes() -> list[str]:
    routes: list[str] = []
    for p in ROOT.rglob("*.mdx"):
        rel = p.relative_to(ROOT).as_posix()
        if any(rel.startswith(prefix) for prefix in IGNORE_MDX_PREFIXES):
            continue
        routes.append(normalize_route(p))
    return sorted(set(routes))


def is_chlom_route(route: str) -> bool:
    return (
        route.startswith("chlom/")
        or route.startswith("changelog/chlom-")
        or route == "changelog/thriveledger-v1-institutionalization-2026-08-23"
    )


def is_developer_route(route: str) -> bool:
    return route.startswith("developers/")


def is_support_route(route: str) -> bool:
    return route.startswith("support/")


def catchup_group(name: str, icon: str, routes: list[str]) -> dict[str, Any] | None:
    if not routes:
        return None
    return {"group": name, "icon": icon, "pages": routes}


def find_group(groups: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for group in groups:
        if group.get("group") == name:
            return group
    return None


def dedupe_nested_pages(node: Any, seen: set[str]) -> Any:
    """Remove duplicate page strings while preserving group structure/order."""
    if isinstance(node, str):
        if node in seen:
            return None
        seen.add(node)
        return node
    if isinstance(node, list):
        out = []
        for item in node:
            cleaned = dedupe_nested_pages(item, seen)
            if cleaned is not None:
                out.append(cleaned)
        return out
    if isinstance(node, dict):
        out = dict(node)
        if isinstance(out.get("pages"), list):
            out["pages"] = dedupe_nested_pages(out["pages"], seen)
        if isinstance(out.get("groups"), list):
            out["groups"] = dedupe_nested_pages(out["groups"], seen)
        return out
    return node


def main() -> None:
    data = json.loads(DOCS.read_text(encoding="utf-8"))
    nav = data.get("navigation")
    if not isinstance(nav, dict):
        raise SystemExit("docs.json has no navigation object")

    # Accept the rich legacy tree or make an existing tabbed tree idempotent.
    if isinstance(nav.get("groups"), list):
        legacy_groups = nav["groups"]
        os_groups: list[dict[str, Any]] = []
        chlom_groups: list[dict[str, Any]] = []
        dev_groups: list[dict[str, Any]] = []
        support_groups: list[dict[str, Any]] = []

        for group in legacy_groups:
            if not isinstance(group, dict) or not group.get("group"):
                raise SystemExit(f"Unexpected legacy navigation node: {group!r}")
            name = group["group"]
            if name in CHLOM_GROUPS:
                chlom_groups.append(group)
            elif name in DEV_GROUPS:
                dev_groups.append(group)
            elif name in SUPPORT_GROUPS:
                support_groups.append(group)
            else:
                os_groups.append(group)

        tabs = [
            {"tab": TAB_OS, "groups": os_groups},
            {"tab": TAB_CHLOM, "groups": chlom_groups},
            {"tab": TAB_DEV, "groups": dev_groups},
            {"tab": TAB_SUPPORT, "groups": support_groups},
        ]
        data["navigation"] = {"tabs": tabs}
    elif isinstance(nav.get("tabs"), list):
        tabs = nav["tabs"]
    else:
        raise SystemExit("Unsupported navigation schema: expected groups or tabs")

    tab_map = {t.get("tab"): t for t in tabs if isinstance(t, dict)}
    for required in (TAB_OS, TAB_CHLOM, TAB_DEV, TAB_SUPPORT):
        if required not in tab_map:
            tab_map[required] = {"tab": required, "groups": []}
            tabs.append(tab_map[required])
        tab_map[required].setdefault("groups", [])

    # Normalize duplicates already present in the historical tree.
    seen: set[str] = set()
    for tab in tabs:
        tab["groups"] = dedupe_nested_pages(tab.get("groups", []), seen)

    repo_routes = all_mdx_routes()
    listed = set(page_strings(tabs))
    missing = [r for r in repo_routes if r not in listed]

    chlom_missing = sorted(r for r in missing if is_chlom_route(r))
    dev_missing = sorted(r for r in missing if not is_chlom_route(r) and is_developer_route(r))
    support_missing = sorted(
        r for r in missing
        if not is_chlom_route(r) and not is_developer_route(r) and is_support_route(r)
    )
    os_missing = sorted(
        r for r in missing
        if r not in set(chlom_missing) | set(dev_missing) | set(support_missing)
    )

    catchups = [
        (TAB_CHLOM, "Recovered & Exact-Title CHLOM Corpus", "file-lines", chlom_missing),
        (TAB_DEV, "Newly Institutionalized Developer Records", "code", dev_missing),
        (TAB_SUPPORT, "Newly Institutionalized Support & Licensing", "scale-balanced", support_missing),
        (TAB_OS, "Newly Institutionalized Records", "sparkles", os_missing),
    ]

    for tab_name, group_name, icon, routes in catchups:
        groups = tab_map[tab_name]["groups"]
        existing = find_group(groups, group_name)
        if existing is not None:
            existing["pages"] = routes
        else:
            group = catchup_group(group_name, icon, routes)
            if group:
                groups.append(group)

    # Final fail-closed coverage and duplicate checks.
    final_list = list(page_strings(tabs))
    final_set = set(final_list)
    still_missing = sorted(set(repo_routes) - final_set)
    duplicate_count = len(final_list) - len(final_set)
    if still_missing:
        raise SystemExit(f"Navigation reconciliation left {len(still_missing)} MDX routes unlisted: {still_missing[:25]}")
    if duplicate_count:
        raise SystemExit(f"Navigation reconciliation produced {duplicate_count} duplicate route entries")

    data["navigation"] = {"tabs": tabs}
    DOCS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Reconciled {len(repo_routes)} MDX routes into four tabs.")
    print(f"Catch-up counts: CHLOM={len(chlom_missing)}, Developers={len(dev_missing)}, Support={len(support_missing)}, OS={len(os_missing)}")


if __name__ == "__main__":
    main()
