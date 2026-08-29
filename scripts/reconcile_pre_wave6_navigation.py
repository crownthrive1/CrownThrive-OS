#!/usr/bin/env python3
"""Reconcile and validate required documentation navigation continuity.

The filename is retained for backward compatibility with the navigation-governance
workflow introduced before substantive Wave 6. The contract is cumulative: every
new governed substantive wave must extend REQUIRED rather than allowing prior
routes to fall out of PentaDocs navigation.

PentaDocs has used multiple valid Mintlify tab shapes over its lifetime:

1. tabs with a top-level ``groups`` array;
2. tabs with a ``pages`` array containing group objects and standalone routes; and
3. nested groups used to keep large documentation estates bounded on mobile.

This validator accepts all three while preserving the same cumulative route
continuity guarantees. Nested presentation structure never weakens route,
backing-page, or ordering invariants.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs.json"

REQUIRED: dict[str, dict[str, list[str]]] = {
    "CrownThrive OS": {
        "Institutional Doctrine": [
            "doctrine/cie-framework-reconciliation-contract",
        ],
        "Institutional Knowledge": [
            "knowledge/documentation-substantive-rebuild-wave-1",
            "knowledge/documentation-substantive-rebuild-wave-2",
            "knowledge/documentation-substantive-rebuild-wave-3",
            "knowledge/documentation-substantive-rebuild-wave-4",
            "knowledge/documentation-substantive-rebuild-wave-5",
            "knowledge/documentation-substantive-rebuild-wave-6",
        ],
        "Changelog and Decisions": [
            "changelog/docs-freshness-sprint-6-final-94-2026-08-23",
            "changelog/docs-substantive-rebuild-sprint-7-wave-1-2026-08-23",
            "changelog/docs-substantive-rebuild-sprint-8-wave-2-2026-08-23",
            "changelog/docs-substantive-rebuild-sprint-9-wave-3-2026-08-23",
            "changelog/docs-substantive-rebuild-sprint-10-wave-4-2026-08-24",
            "changelog/docs-substantive-rebuild-sprint-11-wave-5-2026-08-24",
            "changelog/docs-substantive-rebuild-sprint-12-wave-6-2026-08-24",
        ],
    },
    "CHLOM": {
        "CHLOM": [
            "chlom/identity-trust-reconciliation-contract",
            "chlom/evidence-audit-reconciliation-contract",
            "chlom/component-framework-reconciliation-contract",
            "chlom/interface-surface-reconciliation-contract",
        ],
    },
    "Developers": {
        "Technology, Identity & Data": [
            "technology/crownthrive-io-surface-machine-contract-reconciliation",
        ],
    },
}


def load_docs() -> dict[str, Any]:
    return json.loads(DOCS.read_text(encoding="utf-8"))


def tab(data: dict[str, Any], name: str) -> dict[str, Any]:
    for item in data["navigation"]["tabs"]:
        if item.get("tab") == name:
            return item
    raise KeyError(f"missing navigation tab: {name}")


def navigation_items(container: dict[str, Any]) -> list[Any]:
    """Return a container's navigation children for current or legacy schemas."""
    groups = container.get("groups")
    if isinstance(groups, list):
        return groups
    pages = container.get("pages")
    if isinstance(pages, list):
        return pages
    raise KeyError(
        f"navigation container {container.get('tab') or container.get('group')!r} "
        "has neither a groups nor pages array"
    )


def iter_group_locations(
    container: dict[str, Any],
) -> Iterable[tuple[dict[str, Any], list[Any]]]:
    """Yield every descendant group together with its owning sibling list."""
    try:
        items = navigation_items(container)
    except KeyError:
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("group"), str):
            yield item, items
        yield from iter_group_locations(item)


def group(tab_obj: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [item for item, _ in iter_group_locations(tab_obj) if item.get("group") == name]
    if not matches:
        raise KeyError(f"missing navigation group {name!r} in tab {tab_obj.get('tab')!r}")
    if len(matches) > 1:
        raise KeyError(f"duplicate navigation group {name!r} in tab {tab_obj.get('tab')!r}")
    return matches[0]


def group_location(tab_obj: dict[str, Any], name: str) -> tuple[dict[str, Any], list[Any]]:
    matches = [
        (item, owner)
        for item, owner in iter_group_locations(tab_obj)
        if item.get("group") == name
    ]
    if not matches:
        raise KeyError(f"missing navigation group {name!r} in tab {tab_obj.get('tab')!r}")
    if len(matches) > 1:
        raise KeyError(f"duplicate navigation group {name!r} in tab {tab_obj.get('tab')!r}")
    return matches[0]


def backing_page_exists(route: str) -> bool:
    return (ROOT / f"{route}.mdx").is_file() or (ROOT / f"{route}.md").is_file()


def reconcile(data: dict[str, Any]) -> int:
    added = 0
    for tab_name, groups in REQUIRED.items():
        tab_obj = tab(data, tab_name)
        for group_name, routes in groups.items():
            group_obj = group(tab_obj, group_name)
            pages = group_obj.setdefault("pages", [])
            for route in routes:
                if route not in pages:
                    pages.append(route)
                    added += 1

    # Changelog and Decisions must remain the final group among its siblings.
    # The parent may be the tab itself or a native nested wrapper group.
    crown_tab = tab(data, "CrownThrive OS")
    changelog, items = group_location(crown_tab, "Changelog and Decisions")
    changelog_index = items.index(changelog)
    later_group_indexes = [
        i
        for i, item in enumerate(items)
        if i > changelog_index and isinstance(item, dict) and item.get("group")
    ]
    if later_group_indexes:
        items.pop(changelog_index)
        last_group_index = max(
            i for i, item in enumerate(items) if isinstance(item, dict) and item.get("group")
        )
        items.insert(last_group_index + 1, changelog)
    return added


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_count = 0
    for tab_name, groups in REQUIRED.items():
        try:
            tab_obj = tab(data, tab_name)
        except KeyError as exc:
            errors.append(str(exc))
            continue
        for group_name, routes in groups.items():
            expected_count += len(routes)
            try:
                group_obj = group(tab_obj, group_name)
            except KeyError as exc:
                errors.append(str(exc))
                continue
            pages = group_obj.get("pages", [])
            for route in routes:
                if route not in pages:
                    errors.append(f"required route missing from navigation: {route}")
                if not backing_page_exists(route):
                    errors.append(f"required backing page missing: {route}")

    try:
        changelog, owner = group_location(tab(data, "CrownThrive OS"), "Changelog and Decisions")
    except KeyError as exc:
        errors.append(str(exc))
    else:
        sibling_groups = [
            item for item in owner if isinstance(item, dict) and isinstance(item.get("group"), str)
        ]
        if not sibling_groups or sibling_groups[-1] is not changelog:
            errors.append(
                "Changelog and Decisions must remain the final group within its CrownThrive OS parent"
            )

    if not errors:
        print("PASS_DOCUMENTATION_NAVIGATION_CONTINUITY")
        print(f"required_routes={expected_count}")
        print("missing_routes=0")
        print("backing_pages_missing=0")
        print("changelog_group_last=true")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    data = load_docs()
    if args.write:
        added = reconcile(data)
        DOCS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"navigation_routes_added={added}")
        data = load_docs()

    errors = validate(data)
    if errors:
        print("FAIL_DOCUMENTATION_NAVIGATION_CONTINUITY")
        for error in errors:
            print(error)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
