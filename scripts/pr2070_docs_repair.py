#!/usr/bin/env python3
"""Deterministically place and normalize PR #2070 institutional pages in PentaDocs.

This helper is temporary. It runs only on the isolated generator branch and is
removed before the generated repair commit is published. It translates the
package's earlier descriptive metadata vocabulary into the governed PentaDocs
page-profile taxonomy without changing runtime/certification claims.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

DOCS = Path("docs.json")

CROWNTHRIVE_GROUP_ROUTES = {
    "Institutional Knowledge": [
        "institutional/penta-communications-personas-ads-institutionalization-2026-08-31",
        "knowledge/forked-reference-dependencies",
    ],
    "Runbooks": [
        "runbooks/penta-mail-and-persona-operations",
        "runbooks/penta-ads-release-recovery",
    ],
    "Institutional Standards": [
        "standards/penta-persona-contract-standard",
    ],
}

PENTA_GROUP = "Communications, Personas & Advertising"
PENTA_ROUTES = [
    "pentas/candidates/penta-mailer",
    "pentas/candidates/penta-personas",
    "pentas/candidates/penta-persona-execution",
    "pentas/candidates/penta-persona-factory",
    "pentas/candidates/penta-communications-factory",
    "pentas/candidates/penta-ads",
    "pentas/candidates/penta-ads-factory",
    "pentas/candidates/penta-ads-placement-os",
]

# Exact supplied pages from PR #2070 whose original package metadata predates
# the governed PentaDocs audience/page/content-state taxonomy. The normalized
# states are documentation posture only and never promote runtime maturity.
SUPPLIED_PROFILE_NORMALIZATION: dict[str, tuple[str, str, str]] = {
    "institutional/penta-communications-personas-ads-institutionalization-2026-08-31.mdx": (
        "executive", "reference", "current_with_holds"
    ),
    "knowledge/forked-reference-dependencies.mdx": (
        "operator", "registry", "current"
    ),
    "runbooks/penta-mail-and-persona-operations.mdx": (
        "operator", "runbook", "current_with_holds"
    ),
    "runbooks/penta-ads-release-recovery.mdx": (
        "operator", "runbook", "current_with_holds"
    ),
    "standards/penta-persona-contract-standard.mdx": (
        "operator", "standard", "current"
    ),
    "pentas/canonical/penta-mail.mdx": (
        "operator", "reference", "current_with_holds"
    ),
    "pentas/canonical/penta-mailer.mdx": (
        "operator", "reference", "current_with_holds"
    ),
    "pentas/canonical/penta-personas.mdx": (
        "operator", "reference", "current_with_holds"
    ),
    "pentas/canonical/penta-persona-execution.mdx": (
        "operator", "reference", "current_with_holds"
    ),
    "pentas/canonical/penta-persona-factory.mdx": (
        "developer", "reference", "candidate"
    ),
    "pentas/canonical/penta-ads.mdx": (
        "operator", "reference", "current_with_holds"
    ),
}

FRONTMATTER_FIELD_RE = re.compile(
    r"^(?P<key>primary_audience|page_type|content_state):\s*(?P<value>.*)$",
    flags=re.MULTILINE,
)


def normalize_supplied_profiles() -> dict[str, dict[str, str]]:
    changed: dict[str, dict[str, str]] = {}
    for raw_path, (audience, page_type, content_state) in SUPPLIED_PROFILE_NORMALIZATION.items():
        path = Path(raw_path)
        if not path.is_file():
            # Generated portal convergence may intentionally supersede/remove a
            # hand-authored candidate page. Missing here is therefore not an error.
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            raise SystemExit(f"{raw_path}: missing YAML frontmatter")
        closing = text.find("\n---", 4)
        if closing < 0:
            raise SystemExit(f"{raw_path}: unterminated YAML frontmatter")
        front = text[:closing]
        body = text[closing:]
        desired = {
            "primary_audience": audience,
            "page_type": page_type,
            "content_state": content_state,
        }
        seen: set[str] = set()

        def replace(match: re.Match[str]) -> str:
            key = match.group("key")
            seen.add(key)
            return f'{key}: "{desired[key]}"'

        new_front = FRONTMATTER_FIELD_RE.sub(replace, front)
        missing = set(desired) - seen
        if missing:
            raise SystemExit(f"{raw_path}: missing governed profile fields {sorted(missing)}")
        new_text = new_front + body
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed[raw_path] = desired
    return changed


def iter_string_routes(node: Any) -> Iterable[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for item in node:
            yield from iter_string_routes(item)
    elif isinstance(node, dict):
        for value in node.values():
            yield from iter_string_routes(value)


def find_tab(document: dict[str, Any], name: str) -> dict[str, Any]:
    tabs = document.get("navigation", {}).get("tabs", [])
    matches = [tab for tab in tabs if isinstance(tab, dict) and tab.get("tab") == name]
    if len(matches) != 1:
        raise SystemExit(f"expected one tab {name!r}; found {len(matches)}")
    return matches[0]


def find_groups(node: Any, group_name: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if node.get("group") == group_name and isinstance(node.get("pages"), list):
            found.append(node)
        for value in node.values():
            found.extend(find_groups(value, group_name))
    elif isinstance(node, list):
        for item in node:
            found.extend(find_groups(item, group_name))
    return found


def ensure_absent_or_once(document: dict[str, Any], route: str) -> bool:
    count = sum(1 for value in iter_string_routes(document) if value == route)
    if count > 1:
        raise SystemExit(f"route {route!r} already appears {count} times")
    return count == 1


def add_group_route(document: dict[str, Any], tab: dict[str, Any], group: str, route: str) -> None:
    if ensure_absent_or_once(document, route):
        return
    matches = find_groups(tab, group)
    if len(matches) != 1:
        raise SystemExit(f"expected one {group!r} group in {tab.get('tab')!r}; found {len(matches)}")
    matches[0]["pages"].append(route)


def ensure_penta_group(document: dict[str, Any], penta_tab: dict[str, Any]) -> dict[str, Any]:
    groups = penta_tab.get("groups")
    if not isinstance(groups, list):
        raise SystemExit("Pentas tab does not expose a top-level groups list")
    matches = [group for group in groups if isinstance(group, dict) and group.get("group") == PENTA_GROUP]
    if len(matches) > 1:
        raise SystemExit(f"duplicate {PENTA_GROUP!r} groups: {len(matches)}")
    if matches:
        group = matches[0]
        if not isinstance(group.get("pages"), list):
            raise SystemExit(f"{PENTA_GROUP!r} pages is not a list")
        return group
    group = {"group": PENTA_GROUP, "pages": []}
    groups.append(group)
    return group


def main() -> None:
    normalized = normalize_supplied_profiles()
    document = json.loads(DOCS.read_text(encoding="utf-8"))
    crownthrive_tab = find_tab(document, "CrownThrive OS")
    penta_tab = find_tab(document, "Pentas")

    for group, routes in CROWNTHRIVE_GROUP_ROUTES.items():
        for route in routes:
            add_group_route(document, crownthrive_tab, group, route)

    penta_group = ensure_penta_group(document, penta_tab)
    for route in PENTA_ROUTES:
        if not ensure_absent_or_once(document, route):
            penta_group["pages"].append(route)

    required = [route for routes in CROWNTHRIVE_GROUP_ROUTES.values() for route in routes] + PENTA_ROUTES
    counts = {route: sum(1 for value in iter_string_routes(document) if value == route) for route in required}
    bad = {route: count for route, count in counts.items() if count != 1}
    if bad:
        raise SystemExit(f"navigation convergence failed: {bad}")

    DOCS.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "normalized_profiles": normalized, "routes": counts}, sort_keys=True))


if __name__ == "__main__":
    main()
