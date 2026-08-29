#!/usr/bin/env python3
"""Finalize the generated Penta portal into the governed PentaDocs surface.

This stage removes aggregate prose captures that are not single Penta identities,
materializes route-safe directory pages, lists every dedicated Penta page exactly
once in Mintlify navigation, and applies the repository-wide PentaDocs audience
and metadata standard. It never promotes runtime maturity or authority.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CENSUS = ROOT / "data/penta/namespace-census.v1.json"
OS_REGISTRY = ROOT / "data/penta/os-v1.registry.json"
CANDIDATE_SEED = ROOT / "data/penta/namespace-candidates.v1.json"
FAMILY_REGISTRY = ROOT / "penta/registry/penta-families.v1.json"
DOCS_CONFIG = ROOT / "docs.json"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def single_identity(name: str) -> bool:
    return len(re.findall(r"\bPenta", name)) == 1


def fm(title: str, description: str, *, page_type: str = "registry", content_state: str = "current_with_holds") -> str:
    return "\n".join([
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        f"sidebarTitle: {json.dumps(title, ensure_ascii=False)}",
        'standard_version: "1.0.0"',
        'primary_audience: "operator"',
        f"page_type: {json.dumps(page_type)}",
        f"content_state: {json.dumps(content_state)}",
        "---",
        "",
    ])


def link(record: dict[str, Any]) -> str:
    return "/" + record["docs_path"]


def table(records: list[dict[str, Any]], status_field: str) -> str:
    rows = []
    for record in records:
        status = record.get(status_field) or "unspecified"
        family = record.get("family_name") or "Pending canonical family"
        rows.append(f'| [{record["name"]}]({link(record)}) | `{status}` | {family} |')
    return "\n".join(rows)


def orientation_safe_intro() -> str:
    return "Documentation is a governed projection of registry and namespace evidence. Page presence never creates runtime, legal, rights, financial, provider, production, release, security, credential, governance, or D3 authority."


def render_indexes(records: list[dict[str, Any]], family_registry: dict[str, Any]) -> dict[str, str]:
    canonical = sorted((r for r in records if r["namespace_state"] == "canonical"), key=lambda r: r["name"].casefold())
    candidates = sorted((r for r in records if r["namespace_state"] != "canonical"), key=lambda r: r["name"].casefold())
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pending: list[dict[str, Any]] = []
    for record in records:
        if record.get("family_id"):
            by_family[record["family_id"]].append(record)
        else:
            pending.append(record)
    for members in by_family.values():
        members.sort(key=lambda r: r["name"].casefold())
    pending.sort(key=lambda r: r["name"].casefold())

    out: dict[str, str] = {}
    out["pentas.mdx"] = fm("Penta Portal", "Registry-driven PentaDocs portal for every canonical and preserved Penta identity.") + f"""## Penta Portal

{orientation_safe_intro()}

| Census | Count |
| --- | ---: |
| Total documented Penta identities | **{len(records)}** |
| Canonical Penta OS V1.5 entries | **{len(canonical)}** |
| Noncanonical aliases, extensions, and candidates | **{len(candidates)}** |
| Institutional families | **{len(family_registry['families'])}** |
| Family classification pending | **{len(pending)}** |

## Enter the system

- [Complete A–Z directory](/pentas/all)
- [Canonical registry directory](/pentas/canonical)
- [Canonicalization queue](/pentas/candidates)
- [15-family directory](/pentas/families)
- [Penta OS V1.5 registry](/automation/penta-os-v1)
- [Penta Family operating model](/automation/penta-family)

## Operating rule

Every identity receives a dedicated page. Canonical members project their recorded maturity and readiness. Noncanonical identities remain fail-closed until PentaScribe/PentaPology and the applicable governance/build/certification lanes determine whether each is a distinct system, alias, primitive, subcomponent, engine, superseded name, or retired reference.
"""
    out["pentas/canonical.mdx"] = fm("Canonical Pentas", "Every canonical Penta OS V1.5 registry identity.") + f"""## Canonical Pentas

{orientation_safe_intro()}

**{len(canonical)} canonical registry entries.** Runtime maturity and strict readiness remain sourced from `data/penta/os-v1.registry.json`.

| Penta | Maturity | Family |
| --- | --- | --- |
{table(canonical, 'maturity')}
"""
    out["pentas/candidates.mdx"] = fm("Penta Canonicalization Queue", "Every noncanonical Penta alias, governed extension, founder-declared candidate, and preserved reference.", content_state="candidate") + f"""## Penta Canonicalization Queue

{orientation_safe_intro()}

**{len(candidates)} noncanonical identities are preserved.** Documentation is not production promotion.

| Penta | Class | Provisional or registry family |
| --- | --- | --- |
{table(candidates, 'candidate_class')}
"""
    all_records = sorted(records, key=lambda r: r["name"].casefold())
    out["pentas/all.mdx"] = fm("All Pentas A–Z", "Complete A–Z Penta namespace directory.") + """## All Pentas A–Z

""" + orientation_safe_intro() + "\n\n| Penta | Namespace | Family |\n| --- | --- | --- |\n" + "\n".join(
        f'| [{r["name"]}]({link(r)}) | `{r["namespace_state"]}` | {r.get("family_name") or "Pending canonical family"} |'
        for r in all_records
    ) + "\n"

    family_rows = []
    for family in family_registry["families"]:
        members = by_family.get(family["family_id"], [])
        family_rows.append(f'| [{family["canonical_name"]}](/pentas/families/{family["slug"]}) | **{len(members)}** |')
        out[f'pentas/families/{family["slug"]}.mdx'] = fm(family["canonical_name"], family["mission"]) + f"""## {family['canonical_name']}

{orientation_safe_intro()}

**Mission:** {family['mission']}

**Operator family route:** `{family['portal_route']}`

## Members documented in this portal

| Penta | Namespace | Assignment |
| --- | --- | --- |
""" + "\n".join(
            f'| [{r["name"]}]({link(r)}) | `{r["namespace_state"]}` | `{r.get("assignment_state")}` |'
            for r in members
        ) + f"""

## Cross-family handoffs

{', '.join(f'`{x}`' for x in family.get('handoffs_to', [])) or 'None declared.'}

## Authority boundary

Family placement, connectivity, documentation, readiness, or confidence never creates child maturity or provider, financial, rights, governance, credential, legal, security, or D3 authority.

## Evidence & operations

Use `penta/registry/penta-families.v1.json`, `runtime/penta_families.py`, each child page, PentaStatus, PentaAssure, DAIL, and CHLOM authority traces.
"""
    out["pentas/families.mdx"] = fm("Penta Families", "The 15-family Penta institutional topology.") + """## Penta Families

""" + orientation_safe_intro() + "\n\n| Family | Documented identities |\n| --- | ---: |\n" + "\n".join(family_rows) + (
        f"\n\n## Pending family canonicalization\n\n**{len(pending)}** namespace references remain family-pending rather than being force-fit. See the [canonicalization queue](/pentas/candidates).\n"
        if pending else "\n"
    )
    out["changelog/penta-portal-full-census-2026-08-28.mdx"] = fm(
        "Penta Portal Full Census — 2026-08-28",
        "Registry-driven PentaDocs portal expansion and namespace reconciliation.",
        page_type="changelog",
        content_state="current",
    ) + f"""## Penta Portal Full Census — August 28, 2026

{orientation_safe_intro()}

- Canonical Penta OS V1.5 entries documented: **{len(canonical)}**
- Noncanonical aliases, extensions, and candidates documented: **{len(candidates)}**
- Total dedicated Penta identity pages: **{len(records)}**
- Family portals: **{len(family_registry['families'])}**
- Production promotion performed by this documentation release: **none**

The generation pipeline fails closed on canonical-count drift, aggregate prose captures, missing dedicated pages, navigation drift, and PentaDocs governance violations.
"""
    return out


def build_navigation(records: list[dict[str, Any]], family_registry: dict[str, Any], docs: dict[str, Any]) -> dict[str, Any]:
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pending: list[dict[str, Any]] = []
    for record in records:
        if record.get("family_id"):
            by_family[record["family_id"]].append(record)
        else:
            pending.append(record)
    for values in by_family.values():
        values.sort(key=lambda r: r["name"].casefold())
    pending.sort(key=lambda r: r["name"].casefold())

    groups: list[dict[str, Any]] = [{
        "group": "Penta Portal",
        "pages": ["pentas", "pentas/all", "pentas/canonical", "pentas/candidates", "pentas/families"],
    }]
    for family in family_registry["families"]:
        pages = [f'pentas/families/{family["slug"]}'] + [r["docs_path"] for r in by_family.get(family["family_id"], [])]
        groups.append({"group": family["canonical_name"], "pages": pages})
    if pending:
        groups.append({"group": "Pending Canonical Family", "pages": [r["docs_path"] for r in pending]})
    groups.append({"group": "Penta Release Evidence", "pages": ["changelog/penta-portal-full-census-2026-08-28"]})

    tabs = docs.setdefault("navigation", {}).setdefault("tabs", [])
    tabs[:] = [tab for tab in tabs if not (isinstance(tab, dict) and tab.get("tab") == "Pentas")]
    tabs.insert(1, {"tab": "Pentas", "groups": groups})
    return docs


def load_quality_module():
    path = ROOT / "scripts/pentadocs_quality.py"
    spec = importlib.util.spec_from_file_location("pentadocs_quality_for_penta_portal", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load PentaDocs quality engine")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def apply() -> dict[str, Any]:
    census = load_json(CENSUS)
    os_registry = load_json(OS_REGISTRY)
    seed = load_json(CANDIDATE_SEED)
    family_registry = load_json(FAMILY_REGISTRY)
    records = [r for r in census.get("records", []) if isinstance(r, dict) and single_identity(str(r.get("name", "")))]
    removed = [r for r in census.get("records", []) if isinstance(r, dict) and not single_identity(str(r.get("name", "")))]

    expected_total = int(os_registry["counts"]["total"]) + int(seed["candidate_count"])
    if len(records) != expected_total:
        raise ValueError(f"single-identity census mismatch: {len(records)} != {expected_total}")
    canonical = [r for r in records if r.get("namespace_state") == "canonical"]
    if len(canonical) != int(os_registry["counts"]["total"]):
        raise ValueError("canonical registry coverage drift")

    for record in removed:
        path = ROOT / (record["docs_path"] + ".mdx")
        if path.exists():
            path.unlink()

    for legacy in [ROOT / "pentas/index.mdx", ROOT / "pentas/canonical/index.mdx", ROOT / "pentas/candidates/index.mdx"]:
        if legacy.exists():
            legacy.unlink()

    counts = Counter((r.get("candidate_class") or "canonical") for r in records)
    census["counts"] = {
        "total": len(records),
        "canonical": len(canonical),
        "noncanonical": len(records) - len(canonical),
        "alias_references": counts["alias_reference"],
        "governed_extensions": counts["governed_extension"],
        "reference_candidates": counts["reference_candidate"],
        "families": len(family_registry["families"]),
        "family_pending": sum(1 for r in records if not r.get("family_id")),
        "aggregate_nonidentity_records_removed": len(removed),
    }
    census["records"] = records
    census["finalization"] = {
        "aggregate_capture_rule": "exactly_one_Penta_token",
        "aggregate_captures_removed": [r.get("name") for r in removed],
        "navigation_contract": "every_identity_listed_exactly_once",
        "pentadocs_quality": "deterministic_apply_and_validate",
    }
    write_json(CENSUS, census)

    for rel, content in render_indexes(records, family_registry).items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    docs = build_navigation(records, family_registry, load_json(DOCS_CONFIG))
    DOCS_CONFIG.write_text(json.dumps(docs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    quality = load_quality_module()
    receipt = quality.apply_repository(ROOT)
    errors, stats = quality.validate_repository(ROOT)
    if errors:
        raise ValueError("PentaDocs quality failed after finalization: " + " | ".join(errors[:12]))

    return {
        "status": "APPLIED",
        "total": len(records),
        "canonical": len(canonical),
        "noncanonical": len(records) - len(canonical),
        "removed_aggregate_captures": len(removed),
        "family_pending": census["counts"]["family_pending"],
        "quality": receipt,
        "quality_stats": stats,
    }


def iter_navigation_pages(docs: dict[str, Any]) -> list[str]:
    pages: list[str] = []
    for tab in docs.get("navigation", {}).get("tabs", []):
        if not isinstance(tab, dict) or tab.get("tab") != "Pentas":
            continue
        for group in tab.get("groups", []):
            if isinstance(group, dict):
                pages.extend(page for page in group.get("pages", []) if isinstance(page, str))
    return pages


def check() -> dict[str, Any]:
    census = load_json(CENSUS)
    os_registry = load_json(OS_REGISTRY)
    seed = load_json(CANDIDATE_SEED)
    records = census.get("records", [])
    expected_total = int(os_registry["counts"]["total"]) + int(seed["candidate_count"])
    errors: list[str] = []
    if len(records) != expected_total:
        errors.append(f"census total {len(records)} != {expected_total}")
    if any(not single_identity(str(r.get("name", ""))) for r in records if isinstance(r, dict)):
        errors.append("aggregate nonidentity capture remains")
    for record in records:
        path = ROOT / (record["docs_path"] + ".mdx")
        if not path.is_file():
            errors.append(f"missing dedicated page {path.relative_to(ROOT)}")
    for rel in ["pentas.mdx", "pentas/all.mdx", "pentas/canonical.mdx", "pentas/candidates.mdx", "pentas/families.mdx"]:
        if not (ROOT / rel).is_file():
            errors.append(f"missing directory surface {rel}")

    docs = load_json(DOCS_CONFIG)
    nav_pages = iter_navigation_pages(docs)
    identity_paths = [r["docs_path"] for r in records]
    for path in identity_paths:
        if nav_pages.count(path) != 1:
            errors.append(f"identity navigation multiplicity {path}={nav_pages.count(path)}")
    if len(nav_pages) != len(set(nav_pages)):
        errors.append("duplicate Penta-tab navigation page")

    quality = load_quality_module()
    quality_errors, quality_stats = quality.validate_repository(ROOT)
    errors.extend(f"PentaDocs: {e}" for e in quality_errors)
    if errors:
        raise SystemExit("Penta portal finalization drift:\n" + "\n".join(errors[:80]))
    return {"status": "PASS", "total": len(records), "navigation_pages": len(nav_pages), "quality_stats": quality_stats}


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt = apply() if args.apply else check()
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
