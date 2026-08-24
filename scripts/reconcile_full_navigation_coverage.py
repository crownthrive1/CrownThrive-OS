#!/usr/bin/env python3
"""Reconcile every substantive MDX page into CrownThrive Mintlify navigation.

This tool exists for recovery/institutionalization branches where hundreds of
recovered atomic articles may be created faster than hand-maintained navigation.
It preserves the existing navigation, routes CHLOM artifacts into typed groups,
routes remaining institutional pages into an explicit archive group, removes
page duplicates while preserving first occurrence, and fails if coverage is not
exact after reconciliation.

It does not create, delete, rename, or merge article bodies.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs.json"
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", ".mintlify", "__pycache__"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--write", action="store_true", help="Write reconciled docs.json")
    return p.parse_args()


def iter_pages(node: Any):
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for item in node:
            yield from iter_pages(item)
    elif isinstance(node, dict):
        for key in ("pages", "groups", "tabs", "dropdowns", "products", "versions", "languages"):
            if key in node:
                yield from iter_pages(node[key])


def all_mdx_pages() -> list[str]:
    pages: list[str] = []
    for path in ROOT.rglob("*.mdx"):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        pages.append(rel.with_suffix("").as_posix())
    return sorted(pages)


def get_tab(cfg: dict, name: str) -> dict:
    tabs = cfg.setdefault("navigation", {}).setdefault("tabs", [])
    for tab in tabs:
        if tab.get("tab") == name:
            return tab
    tab = {"tab": name, "groups": []}
    tabs.append(tab)
    return tab


def get_group(tab: dict, name: str, icon: str) -> dict:
    groups = tab.setdefault("groups", [])
    for group in groups:
        if group.get("group") == name:
            group.setdefault("pages", [])
            return group
    group = {"group": name, "icon": icon, "pages": []}
    groups.append(group)
    return group


def chlom_group(page: str) -> tuple[str, str]:
    if page.startswith("chlom/papers/"):
        return "Exact-Title Papers & Technical Documents", "file-lines"
    if page.startswith("chlom/algorithms/"):
        return "Algorithms & Procedures", "code"
    if page.startswith("chlom/formulas/"):
        return "Formulas & Mathematical Models", "square-root-variable"
    if page.startswith("chlom/theorems/"):
        return "Formal Guarantees & Theorems", "function"
    if page.startswith("chlom/widgets/"):
        return "UI Components & Widgets", "window-maximize"
    if page.startswith("chlom/workflows/"):
        return "Institutional Workflows", "diagram-project"
    if page.startswith("chlom/schemas/"):
        return "Machine Schemas & Manifests", "database"
    if page.startswith("chlom/components/"):
        return "Rights & Marketplace Components", "right-left"
    if page.startswith("chlom/privacy/"):
        return "Privacy & ZK Proof Families", "shield-halved"
    if page.startswith("chlom/interoperability/"):
        return "Interoperability & Bridge Components", "bridge"
    if page.startswith("chlom/runtime/"):
        return "Smart Contract & Runtime Research", "cubes"
    if page.startswith("chlom/research/"):
        return "Historical & Protocol Research", "flask"
    if page.startswith("chlom/storage/"):
        return "Storage & Persistence Architecture", "hard-drive"
    if page.startswith("chlom/developer/"):
        return "Developer Interfaces & SDKs", "code"
    if page.startswith("chlom/surfaces/"):
        return "Role Surface Contracts", "users"
    if page.startswith("chlom/systems/"):
        return "Canonical Systems & Split Lineage", "sitemap"
    if page.startswith("chlom/pallet-"):
        return "CHLOM Pallets & Containers", "boxes-stacked"
    if page.startswith("chlom/wireframe-") or page == "chlom/functional-specification-and-ui-wireframe-outline":
        return "Wireframes, Portals & UI", "table-columns"
    if page.startswith("chlom/engine-") or page.startswith("chlom/service-") or page.startswith("chlom/runtime-"):
        return "Runtime Modules & Engines", "microchip"
    return "CHLOM Core & Recovery", "network-wired"


def dedupe_pages(cfg: dict) -> int:
    seen: set[str] = set()
    removed = 0
    for tab in cfg.get("navigation", {}).get("tabs", []):
        for group in tab.get("groups", []):
            pages = group.get("pages")
            if not isinstance(pages, list):
                continue
            kept = []
            for page in pages:
                if not isinstance(page, str) or page.startswith(("http://", "https://", "mailto:")):
                    kept.append(page)
                    continue
                if page in seen:
                    removed += 1
                    continue
                seen.add(page)
                kept.append(page)
            group["pages"] = kept
    return removed


def main() -> int:
    args = parse_args()
    cfg = json.loads(DOCS.read_text(encoding="utf-8"))

    removed = dedupe_pages(cfg)
    existing = set(iter_pages(cfg.get("navigation", {})))
    mdx = all_mdx_pages()
    missing = [page for page in mdx if page not in existing]

    chlom_tab = get_tab(cfg, "CHLOM")
    os_tab = get_tab(cfg, "CrownThrive OS")
    archive = get_group(os_tab, "Institutional Archive & Recovery", "box-archive")

    added = 0
    for page in missing:
        if page.startswith("chlom/"):
            group_name, icon = chlom_group(page)
            group = get_group(chlom_tab, group_name, icon)
        else:
            group = archive
        if page not in group["pages"]:
            group["pages"].append(page)
            added += 1

    # Deterministic order for only the catch-all archive; typed CHLOM groups
    # preserve their curated existing order and append recovered pages in the
    # globally sorted discovery order above.
    archive["pages"] = sorted(dict.fromkeys(archive["pages"]))

    # Final duplicate pass protects against a page having been introduced by
    # two recovery routes during the same reconciliation.
    removed += dedupe_pages(cfg)

    nav_pages = [p for p in iter_pages(cfg.get("navigation", {})) if isinstance(p, str) and not p.startswith(("http://", "https://", "mailto:"))]
    nav_set = set(nav_pages)
    mdx_set = set(mdx)
    still_missing = sorted(mdx_set - nav_set)
    duplicates = len(nav_pages) - len(nav_set)
    missing_files = sorted(page for page in nav_set if page not in mdx_set and not (ROOT / page).with_suffix(".md").is_file())

    print(f"MDX pages: {len(mdx_set)}")
    print(f"Navigation pages: {len(nav_pages)}")
    print(f"Added: {added}")
    print(f"Duplicates removed: {removed}")
    print(f"Still unlisted: {len(still_missing)}")
    print(f"Duplicate navigation pages: {duplicates}")
    print(f"Navigation targets without MDX/MD file: {len(missing_files)}")

    if still_missing:
        print("Unlisted pages:")
        for page in still_missing:
            print(f"  {page}")
        return 2
    if duplicates:
        return 3
    if missing_files:
        print("Missing navigation targets:")
        for page in missing_files:
            print(f"  {page}")
        return 4

    rendered = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        DOCS.write_text(rendered, encoding="utf-8")
        print("docs.json reconciled and written.")
    else:
        current = DOCS.read_text(encoding="utf-8")
        if current != rendered:
            print("docs.json requires reconciliation; run with --write.")
            return 5
        print("docs.json already has exact MDX coverage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
