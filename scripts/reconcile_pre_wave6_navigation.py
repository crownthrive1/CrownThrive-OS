#!/usr/bin/env python3
"""Reconcile and validate documentation routes that must be visible before Wave 6.

This script is intentionally narrow and idempotent. It adds only the known
Sprint 6-11 documentation surfaces that already exist in the repository, keeps
Changelog and Decisions as the final CrownThrive OS navigation group, and
fails if any required backing page is missing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs.json"

REQUIRED: dict[str, dict[str, list[str]]] = {
    "CrownThrive OS": {
        "Institutional Knowledge": [
            "knowledge/documentation-substantive-rebuild-wave-1",
            "knowledge/documentation-substantive-rebuild-wave-2",
            "knowledge/documentation-substantive-rebuild-wave-3",
            "knowledge/documentation-substantive-rebuild-wave-4",
            "knowledge/documentation-substantive-rebuild-wave-5",
        ],
        "Changelog and Decisions": [
            "changelog/docs-freshness-sprint-6-final-94-2026-08-23",
            "changelog/docs-substantive-rebuild-sprint-7-wave-1-2026-08-23",
            "changelog/docs-substantive-rebuild-sprint-8-wave-2-2026-08-23",
            "changelog/docs-substantive-rebuild-sprint-9-wave-3-2026-08-23",
            "changelog/docs-substantive-rebuild-sprint-10-wave-4-2026-08-24",
            "changelog/docs-substantive-rebuild-sprint-11-wave-5-2026-08-24",
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


def group(tab_obj: dict[str, Any], name: str) -> dict[str, Any]:
    for item in tab_obj.get("groups", []):
        if item.get("group") == name:
            return item
    raise KeyError(f"missing navigation group {name!r} in tab {tab_obj.get('tab')!r}")


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

    crown_tab = tab(data, "CrownThrive OS")
    groups = crown_tab["groups"]
    changelog_index = next(
        (i for i, item in enumerate(groups) if item.get("group") == "Changelog and Decisions"),
        None,
    )
    if changelog_index is None:
        raise KeyError("missing Changelog and Decisions group")
    if changelog_index != len(groups) - 1:
        changelog = groups.pop(changelog_index)
        groups.append(changelog)
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
        crown_groups = tab(data, "CrownThrive OS")["groups"]
    except KeyError as exc:
        errors.append(str(exc))
    else:
        if not crown_groups or crown_groups[-1].get("group") != "Changelog and Decisions":
            errors.append("Changelog and Decisions must remain the final CrownThrive OS group")

    if not errors:
        print("PASS_PRE_WAVE6_DOCUMENTATION_NAVIGATION")
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
        print("FAIL_PRE_WAVE6_DOCUMENTATION_NAVIGATION")
        for error in errors:
            print(error)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
