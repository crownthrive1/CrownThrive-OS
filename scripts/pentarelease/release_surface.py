#!/usr/bin/env python3
"""PentaRelease comprehensive release + bounded release-surface synchronizer.

Safety invariants:
- Never invent direct USD costs or CIE scores.
- Never delete a repository surface unless PentaRelease state proves it created it.
- Never overwrite unmanaged content in a pre-existing surface; manage one delimited block only.
- Never remove a PentaDocs tab unless state proves PentaRelease created that exact tab.
- Enforce configured repository-surface and PentaDocs top-level tab ceilings.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

RELEASE_BLOCK_START = "<!-- pentarelease:comprehensive-release:start -->"
RELEASE_BLOCK_END = "<!-- pentarelease:comprehensive-release:end -->"
DEFAULT_SURFACE_START = "<!-- pentarelease:managed-release-surface:start -->"
DEFAULT_SURFACE_END = "<!-- pentarelease:managed-release-surface:end -->"
SCORE_KEYS = {
    "cie_score",
    "cultural_imprint_score",
    "cultural_imprint_engine_score",
    "imprint_score",
}
COST_KEYS = {
    "direct_cost_usd",
    "payload_cost_usd",
    "execution_cost_usd",
    "cost_usd",
}


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_json(*args: str) -> Any:
    p = subprocess.run(args, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(args)}\n{p.stderr}")
    return json.loads(p.stdout)


def strip_managed_block(text: str, start: str, end: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end) + r"\n?", re.S)
    return pattern.sub("", text).rstrip()


def upsert_managed_block(text: str, block: str, start: str, end: str) -> str:
    base = strip_managed_block(text, start, end)
    managed = f"{start}\n{block.rstrip()}\n{end}"
    return (base + ("\n\n" if base else "") + managed + "\n")


def recursive_find_key(value: Any, keys: set[str]) -> tuple[str, Any] | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in keys and child not in (None, ""):
                return str(key), child
        for child in value.values():
            hit = recursive_find_key(child, keys)
            if hit:
                return hit
    elif isinstance(value, list):
        for child in value:
            hit = recursive_find_key(child, keys)
            if hit:
                return hit
    return None


def normalized_numeric_or_raw(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        s = value.strip().rstrip("%")
        try:
            return float(s)
        except ValueError:
            return value
    return value


def changed_files_from_manifest(manifest: dict[str, Any]) -> list[str]:
    decision = manifest.get("decision") if isinstance(manifest.get("decision"), dict) else {}
    candidates = decision.get("changed_files") or manifest.get("changed_files") or []
    return [str(x) for x in candidates if isinstance(x, str)]


def discover_cie(repo_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    hit = recursive_find_key(manifest, SCORE_KEYS)
    if hit:
        return {
            "status": "available",
            "score": normalized_numeric_or_raw(hit[1]),
            "source": f"MANIFEST.json:{hit[0]}",
            "invented": False,
        }

    candidates: list[Path] = []
    for raw in changed_files_from_manifest(manifest):
        p = repo_root / raw
        low = raw.lower()
        if p.is_file() and p.suffix.lower() == ".json" and ("cie" in low or "cultural" in low or "imprint" in low):
            if p.stat().st_size <= 1_000_000:
                candidates.append(p)

    for p in sorted(candidates):
        try:
            value = read_json(p, {})
        except Exception:
            continue
        hit = recursive_find_key(value, SCORE_KEYS)
        if hit:
            return {
                "status": "available",
                "score": normalized_numeric_or_raw(hit[1]),
                "source": str(p.relative_to(repo_root)) + f":{hit[0]}",
                "invented": False,
            }

    return {
        "status": "not_available",
        "score": None,
        "source": None,
        "reason": "No release-linked CIE score was found in the release manifest or CIE/imprint evidence JSON.",
        "invented": False,
    }


def discover_direct_cost(manifest: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    cost_asset = source_dir / "PENTARELEASE_COSTS.json"
    if not cost_asset.exists():
        cost_asset = source_dir / "COSTS.json"
    if cost_asset.exists():
        try:
            payload = read_json(cost_asset, {})
            hit = recursive_find_key(payload, COST_KEYS)
            if hit:
                return {
                    "status": "available",
                    "direct_cost_usd": normalized_numeric_or_raw(hit[1]),
                    "source": f"{cost_asset.name}:{hit[0]}",
                    "invented": False,
                }
        except Exception:
            pass

    hit = recursive_find_key(manifest, COST_KEYS)
    if hit:
        return {
            "status": "available",
            "direct_cost_usd": normalized_numeric_or_raw(hit[1]),
            "source": f"MANIFEST.json:{hit[0]}",
            "invented": False,
        }

    return {
        "status": "not_available",
        "direct_cost_usd": None,
        "source": None,
        "reason": "No release-linked direct USD execution cost was supplied.",
        "invented": False,
    }


def release_view(repository: str, tag: str) -> dict[str, Any]:
    return run_json(
        "gh", "release", "view", tag, "--repo", repository,
        "--json", "tagName,name,url,isDraft,isPrerelease,targetCommitish,assets,body,publishedAt,createdAt",
    )


def file_inventory(repo_root: Path, paths: Iterable[str]) -> list[dict[str, Any]]:
    rows = []
    for raw in paths:
        p = repo_root / raw
        if p.is_file():
            data = p.read_bytes()
            rows.append({
                "path": raw,
                "status": "available",
                "bytes": len(data),
                "sha256": sha256_bytes(data),
            })
        elif p.exists():
            rows.append({"path": raw, "status": "available_non_file", "bytes": None, "sha256": None})
        else:
            rows.append({"path": raw, "status": "not_available", "bytes": None, "sha256": None})
    return rows


def sanitize_original_release_body(body: str) -> str:
    return strip_managed_block(body or "", RELEASE_BLOCK_START, RELEASE_BLOCK_END)


def summarize_changes(changed: list[str]) -> str:
    if not changed:
        return "No changed-file list was supplied in the release manifest."
    shown = changed[:40]
    lines = [f"- `{x}`" for x in shown]
    if len(changed) > len(shown):
        lines.append(f"- … plus {len(changed) - len(shown)} additional changed paths")
    return "\n".join(lines)


def derive_targets(manifest: dict[str, Any], release: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for value in (
        manifest.get("target_ref"),
        manifest.get("target"),
        (manifest.get("decision") or {}).get("target") if isinstance(manifest.get("decision"), dict) else None,
        release.get("targetCommitish"),
    ):
        if value and str(value) not in out:
            out.append(str(value))
    return out or ["not_available"]


def discover_penta_components(manifest: dict[str, Any], changed: list[str]) -> list[str]:
    text = json.dumps(manifest, ensure_ascii=False) + "\n" + "\n".join(changed)
    names = {"PentaRelease"}
    for token in re.findall(r"\bPenta[A-Z][A-Za-z0-9]+\b", text):
        names.add(token)
    for path in changed:
        base = Path(path).stem
        if base.upper().startswith("PENTA") and len(base) <= 80:
            pretty = "Penta" + base[5:].title().replace("-", "").replace("_", "")
            if len(pretty) > 5:
                names.add(pretty)
    return sorted(names)


def derive_ecosystem_lanes(changed: list[str]) -> list[str]:
    lanes = []
    for path in changed:
        top = path.split("/", 1)[0]
        if top and top not in {".github", ".pentarelease"} and top not in lanes:
            lanes.append(top)
    return lanes


def derive_why(manifest: dict[str, Any]) -> str:
    decision = manifest.get("decision") if isinstance(manifest.get("decision"), dict) else {}
    return str(
        decision.get("why")
        or manifest.get("why")
        or "Release rationale was not separately supplied; see preserved original release notes."
    )


def release_record(
    repository: str,
    tag: str,
    release: dict[str, Any],
    manifest: dict[str, Any],
    cie: dict[str, Any],
    cost: dict[str, Any],
    inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    changed = changed_files_from_manifest(manifest)
    penta_components = discover_penta_components(manifest, changed)
    lanes = derive_ecosystem_lanes(changed)
    changed_payload_bytes = sum(int(x.get("bytes") or 0) for x in inventory if x.get("status") == "available")
    cost["changed_file_payload_bytes"] = changed_payload_bytes
    cost["changed_file_payload_count"] = sum(1 for x in inventory if x.get("status") == "available")
    cost["payload_measurement_note"] = "Payload byte measurements are operational data, not a substitute for direct USD cost."

    return {
        "schema": "ct.pentarelease.comprehensive-release.v1",
        "release_id": manifest.get("release_id") or f"ct.release.{tag}",
        "tag": tag,
        "title": release.get("name") or manifest.get("title") or tag,
        "official_release_url": release.get("url") or f"https://github.com/{repository}/releases/tag/{tag}",
        "what_pentarelease_is": (
            "PentaRelease is CrownThrive OS's governed release publication, evidence, provenance, "
            "cost/data disclosure, and release-surface synchronization layer. It packages what changed, "
            "why it changed, what evidence exists, what data is available, and what remains unknown."
        ),
        "what_changed": changed,
        "why": derive_why(manifest),
        "penta_components": penta_components,
        "ecosystem_lanes": lanes,
        "targets": derive_targets(manifest, release),
        "version_scheme": manifest.get("version_scheme"),
        "publisher": manifest.get("publisher") or "PentaRelease",
        "publisher_contract": manifest.get("publisher_contract"),
        "payload_costs": cost,
        "cie_score": cie,
        "data_availability": {
            "changed_files": inventory,
            "release_asset_count": len(release.get("assets") or []),
            "release_assets": [
                {
                    "name": a.get("name"),
                    "size": a.get("size"),
                    "url": a.get("url"),
                }
                for a in (release.get("assets") or [])
            ],
        },
        "evidence": {
            "provider_release_readback": True,
            "is_draft": bool(release.get("isDraft")),
            "is_prerelease": bool(release.get("isPrerelease")),
            "manifest_present": bool(manifest),
            "source_manifest_sha256": None,
        },
        "provenance": {
            "repository": repository,
            "release_target": release.get("targetCommitish"),
            "published_at": release.get("publishedAt"),
            "created_at": release.get("createdAt"),
            "generated_at": now_utc(),
            "unknown_values_are_explicit": True,
            "costs_invented": False,
            "cie_score_invented": False,
        },
    }


def render_comprehensive_block(record: dict[str, Any]) -> str:
    changed = record["what_changed"]
    changed_md = summarize_changes(changed)
    cost = record["payload_costs"]
    cie = record["cie_score"]
    inv = record["data_availability"]["changed_files"]
    available = sum(1 for x in inv if x["status"] == "available")
    missing = sum(1 for x in inv if x["status"] == "not_available")
    targets = ", ".join(f"`{x}`" for x in record["targets"])
    cost_value = cost.get("direct_cost_usd")
    cost_text = f"${cost_value}" if cost_value is not None else "Not available — no direct USD cost was supplied."
    cie_text = str(cie.get("score")) if cie.get("score") is not None else "Not available — no release-linked CIE score was found."
    penta_components = ", ".join(f"`{x}`" for x in record.get("penta_components") or ["PentaRelease"])
    ecosystem_lanes = ", ".join(f"`{x}`" for x in record.get("ecosystem_lanes") or []) or "No top-level ecosystem lane was declared by the changed-file set."

    return f"""## PentaRelease Comprehensive Release Record

**Official release:** {record['official_release_url']}

### What PentaRelease is

{record['what_pentarelease_is']}

### Penta / subsystem context

- **Penta components observed:** {penta_components}
- **What PentaRelease is:** {record['what_pentarelease_is']}
- **Ecosystem lanes observed from changed paths:** {ecosystem_lanes}

### What changed

{changed_md}

### Why this release exists

{record['why']}

### Targets / publication disposition

{targets}

### Payload costs

- **Direct USD execution cost:** {cost_text}
- **Cost status:** `{cost.get('status')}`
- **Cost source:** `{cost.get('source') or 'not_available'}`
- **Changed-file payload bytes:** {cost.get('changed_file_payload_bytes', 0)}
- PentaRelease does not manufacture a dollar cost when no cost ledger/value is present.

### Cultural Imprint Engine (CIE)

- **CIE score:** {cie_text}
- **CIE status:** `{cie.get('status')}`
- **CIE source:** `{cie.get('source') or 'not_available'}`
- PentaRelease does not manufacture a CIE score when release-linked evidence is absent.

### Data availability

- Changed paths declared: **{len(inv)}**
- Available as files in the synchronized checkout: **{available}**
- Not available in the synchronized checkout: **{missing}**
- Published GitHub release assets observed: **{record['data_availability']['release_asset_count']}**

See `PENTARELEASE_DATA_CATALOG.json` for the path-level inventory, byte counts, hashes, and provider asset metadata.

### Evidence and provenance

- Provider release readback: **verified**
- Manifest present: **{'yes' if record['evidence']['manifest_present'] else 'no'}**
- Release target: `{record['provenance']['release_target'] or 'not_available'}`
- Generated at: `{record['provenance']['generated_at']}`
- Unknown costs and CIE values remain explicit `null`/not-available values; they are never fabricated.
"""


def render_full_release(original_body: str, record: dict[str, Any]) -> str:
    base = sanitize_original_release_body(original_body)
    block = render_comprehensive_block(record)
    managed = f"{RELEASE_BLOCK_START}\n{block.rstrip()}\n{RELEASE_BLOCK_END}"
    return (base + ("\n\n" if base else "") + managed + "\n")


def render_faq(record: dict[str, Any]) -> str:
    cie = record["cie_score"]
    cost = record["payload_costs"]
    return f"""# Release FAQ — {record['tag']}

## Where is the official release?
{record['official_release_url']}

## What is PentaRelease?
{record['what_pentarelease_is']}

## What changed?
This release declares {len(record['what_changed'])} changed path(s). The complete path list is in `PENTARELEASE_RELEASE_RECORD.json` and `PENTARELEASE_DATA_CATALOG.json`.

## What did the release cost?
Direct USD execution cost: {cost.get('direct_cost_usd') if cost.get('direct_cost_usd') is not None else 'not available'}. Source: {cost.get('source') or 'not available'}. No value is fabricated.

## What is the CIE score?
CIE score: {cie.get('score') if cie.get('score') is not None else 'not available'}. Source: {cie.get('source') or 'not available'}. No score is fabricated.

## What evidence is available?
See `PENTARELEASE_EVIDENCE.json`, `PENTARELEASE_DATA_CATALOG.json`, the package checksums, and the official GitHub release assets.

## What is authoritative?
The official GitHub Release at the URL above is the canonical release publication. Release metadata does not manufacture governance authority, legal rights, certification, or provider state.
"""


def render_changelog(record: dict[str, Any]) -> str:
    return f"""# Changelog — {record['tag']}

- **Release:** [{record['tag']}]({record['official_release_url']})
- **Title:** {record['title']}
- **Why:** {record['why']}
- **Targets:** {', '.join(record['targets'])}
- **Changed paths:** {len(record['what_changed'])}
- **Penta components:** {', '.join(record.get('penta_components') or ['PentaRelease'])}
- **Ecosystem lanes:** {', '.join(record.get('ecosystem_lanes') or []) or 'not available'}
- **CIE:** {record['cie_score'].get('score') if record['cie_score'].get('score') is not None else 'not available'}
- **Direct USD cost:** {record['payload_costs'].get('direct_cost_usd') if record['payload_costs'].get('direct_cost_usd') is not None else 'not available'}

## Changed paths

{summarize_changes(record['what_changed'])}
"""


def surface_block(label: str, record: dict[str, Any]) -> str:
    cie = record["cie_score"]
    cost = record["payload_costs"]
    legal_note = ""
    if label.lower() == "license":
        legal_note = (
            "\n**Non-normative release metadata:** this managed block does not amend, replace, "
            "or reinterpret the license terms outside this block.\n"
        )
    return f"""## Latest PentaRelease — {record['tag']}

{legal_note}
- **Official release:** {record['official_release_url']}
- **Release title:** {record['title']}
- **Why:** {record['why']}
- **Changed paths:** {len(record['what_changed'])}
- **Penta components:** {', '.join(record.get('penta_components') or ['PentaRelease'])}
- **Direct USD payload cost:** {cost.get('direct_cost_usd') if cost.get('direct_cost_usd') is not None else 'not available'}
- **CIE score:** {cie.get('score') if cie.get('score') is not None else 'not available'}
- **Data/evidence:** comprehensive record, FAQ, changelog, costs, CIE status, data catalog, and evidence are attached to the official release.

This section is maintained by PentaRelease. Content outside the managed markers remains under its existing ownership and editorial authority.
"""


def safe_created_file_content(label: str, block: str, start: str, end: str) -> str:
    return f"# {label}\n\n{start}\n{block.rstrip()}\n{end}\n"


def safe_to_delete_created(text: str, label: str, start: str, end: str) -> bool:
    if start not in text or end not in text:
        return False
    outside = strip_managed_block(text, start, end).strip()
    return outside in ("", f"# {label}")


def sync_repository_surfaces(
    repo_root: Path,
    policy: dict[str, Any],
    record: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    cfg = policy.get("release_surface") or {}
    surfaces = cfg.get("repository_surfaces") or []
    max_surfaces = int(cfg.get("max_repository_surfaces", 7))
    if len(surfaces) > max_surfaces:
        raise RuntimeError(f"release surface policy declares {len(surfaces)} surfaces; maximum is {max_surfaces}")

    start = cfg.get("managed_block_start") or DEFAULT_SURFACE_START
    end = cfg.get("managed_block_end") or DEFAULT_SURFACE_END
    previous = (state.get("repository_surfaces") or {}).copy()
    current_paths = {str(s["path"]) for s in surfaces}
    next_state: dict[str, Any] = {}

    for path, meta in previous.items():
        if path in current_paths:
            continue
        target = repo_root / path
        if not target.exists():
            continue
        text = target.read_text(encoding="utf-8")
        if meta.get("created_by_pentarelease"):
            if safe_to_delete_created(text, meta.get("label") or Path(path).stem, start, end):
                target.unlink()
        else:
            cleaned = strip_managed_block(text, start, end)
            if cleaned != text.rstrip():
                target.write_text(cleaned.rstrip() + "\n", encoding="utf-8")

    for s in surfaces:
        path = str(s["path"])
        label = str(s.get("label") or Path(path).stem)
        target = repo_root / path
        existed = target.exists()
        old_meta = previous.get(path) or {}
        created = bool(old_meta.get("created_by_pentarelease")) if old_meta else not existed
        block = surface_block(label, record)
        target.parent.mkdir(parents=True, exist_ok=True)

        if existed:
            text = target.read_text(encoding="utf-8")
            target.write_text(upsert_managed_block(text, block, start, end), encoding="utf-8")
        else:
            target.write_text(safe_created_file_content(label, block, start, end), encoding="utf-8")

        next_state[path] = {
            "label": label,
            "created_by_pentarelease": created,
            "first_release": old_meta.get("first_release") or record["tag"],
            "last_release": record["tag"],
        }

    state["repository_surfaces"] = next_state
    return state


def docs_page(title: str, body: str, description: str) -> str:
    rendered_body = body.rstrip()
    if not re.search(r"(?m)^#\s+", rendered_body):
        rendered_body = f"# {title}\n\n{rendered_body}"
    return f"""---
title: "{title}"
description: "{description}"
---

{rendered_body}
"""


def write_pentadocs_pages(repo_root: Path, record: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    pages = {
        "pentarelease/latest.mdx": docs_page(
            f"Latest Release — {record['tag']}",
            render_comprehensive_block(record),
            "Canonical PentaRelease summary, evidence, costs, CIE status, and release data.",
        ),
        "pentarelease/faq.mdx": docs_page(
            "Release FAQ",
            render_faq(record),
            "Current PentaRelease FAQ linked to the canonical GitHub release.",
        ),
        "pentarelease/changelog.mdx": docs_page(
            "Release Changelog",
            render_changelog(record),
            "Current release changelog with changed paths and disclosure status.",
        ),
        "pentarelease/costs.mdx": docs_page(
            "Release Costs",
            f"# Payload Costs — {record['tag']}\n\n```json\n{json.dumps(record['payload_costs'], indent=2)}\n```\n",
            "Release-linked cost disclosure. Unknown values remain explicitly unavailable.",
        ),
        "pentarelease/cie.mdx": docs_page(
            "CIE Release Score",
            f"# CIE — {record['tag']}\n\n```json\n{json.dumps(record['cie_score'], indent=2)}\n```\n",
            "Release-linked Cultural Imprint Engine score and source status.",
        ),
        "pentarelease/data.mdx": docs_page(
            "Release Data",
            f"# Data Availability — {record['tag']}\n\n```json\n{json.dumps(record['data_availability'], indent=2)}\n```\n",
            "Path-level and provider release-asset data availability.",
        ),
        "pentarelease/evidence.mdx": docs_page(
            "Release Evidence",
            f"# Evidence — {record['tag']}\n\n```json\n{json.dumps(record['evidence'] | record['provenance'], indent=2)}\n```\n",
            "Release readback, evidence, provenance, and truthfulness status.",
        ),
    }
    previous = state.get("pentadocs_pages") or {}
    for path, content in pages.items():
        target = repo_root / path
        existed = target.exists()
        old = previous.get(path) or {}
        target.parent.mkdir(parents=True, exist_ok=True)
        if existed and not old:
            previous[path] = {
                "created_by_pentarelease": False,
                "last_release": None,
                "status": "collision_preserved",
            }
            continue
        if existed and old and not old.get("created_by_pentarelease"):
            previous[path]["status"] = "collision_preserved"
            continue
        target.write_text(content, encoding="utf-8")
        previous[path] = {
            "created_by_pentarelease": bool(old.get("created_by_pentarelease")) if old else not existed,
            "last_release": record["tag"],
            "status": "managed",
        }
    state["pentadocs_pages"] = previous
    return state


def sync_pentadocs_nav(repo_root: Path, policy: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    cfg = (policy.get("release_surface") or {}).get("pentadocs") or {}
    if not cfg.get("enabled", True):
        return state

    docs_path = repo_root / str(cfg.get("config") or "docs.json")
    docs = read_json(docs_path, {})
    nav = docs.setdefault("navigation", {})
    tabs = nav.setdefault("tabs", [])
    max_tabs = int((policy.get("release_surface") or {}).get("max_pentadocs_tabs", 7))
    tab_name = str(cfg.get("tab") or "Releases & Evidence")
    pages = list(cfg.get("pages") or [])
    expected = {
        "tab": tab_name,
        "groups": [{
            "group": "PentaRelease",
            "icon": "box-archive",
            "pages": pages,
        }],
    }
    matches = [i for i, t in enumerate(tabs) if isinstance(t, dict) and t.get("tab") == tab_name]
    prior = state.get("pentadocs_nav") or {}

    if matches:
        idx = matches[0]
        if prior.get("created_by_pentarelease"):
            tabs[idx] = expected
        else:
            state["pentadocs_nav"] = {
                "tab": tab_name,
                "created_by_pentarelease": False,
                "status": "collision_preserved",
            }
    else:
        if len(tabs) + 1 > max_tabs:
            raise RuntimeError(
                f"adding PentaRelease PentaDocs tab would create {len(tabs)+1} tabs; maximum is {max_tabs}"
            )
        tabs.append(expected)
        state["pentadocs_nav"] = {
            "tab": tab_name,
            "created_by_pentarelease": True,
            "status": "managed",
        }

    if len(tabs) > max_tabs:
        raise RuntimeError(f"PentaDocs contains {len(tabs)} tabs; maximum configured is {max_tabs}")

    write_json(docs_path, docs)
    return state


def build_assets(
    outdir: Path,
    record: dict[str, Any],
    original_body: str,
) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}

    full = render_full_release(original_body, record)
    faq = render_faq(record)
    changelog = render_changelog(record)
    costs = copy.deepcopy(record["payload_costs"])
    cie = copy.deepcopy(record["cie_score"])
    data = copy.deepcopy(record["data_availability"])
    evidence = {
        **record["evidence"],
        **record["provenance"],
        "official_release_url": record["official_release_url"],
        "release_id": record["release_id"],
        "tag": record["tag"],
    }

    content_map: dict[str, str] = {
        "PENTARELEASE_COMPREHENSIVE_RELEASE.md": full,
        "PENTARELEASE_RELEASE_RECORD.json": json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        "PENTARELEASE_COSTS.json": json.dumps(costs, indent=2, ensure_ascii=False) + "\n",
        "PENTARELEASE_CIE_SCORE.json": json.dumps(cie, indent=2, ensure_ascii=False) + "\n",
        "PENTARELEASE_DATA_CATALOG.json": json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        "PENTARELEASE_EVIDENCE.json": json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        "PENTARELEASE_FAQ.md": faq,
        "PENTARELEASE_CHANGELOG.md": changelog,
    }
    for name, content in content_map.items():
        p = outdir / name
        p.write_text(content, encoding="utf-8")
        files[name] = p

    generated_bytes = sum(p.stat().st_size for p in files.values())
    costs["generated_release_surface_bytes"] = generated_bytes
    costs["generated_release_surface_asset_count"] = len(files)
    costs["measurement_note"] = "Byte counts are payload measurements, not monetary costs."
    write_json(files["PENTARELEASE_COSTS.json"], costs)

    data["generated_assets"] = [
        {"name": name, "bytes": p.stat().st_size, "sha256": sha256_file(p)}
        for name, p in sorted(files.items())
    ]
    write_json(files["PENTARELEASE_DATA_CATALOG.json"], data)

    evidence["generated_assets"] = [
        {"name": name, "sha256": sha256_file(p)}
        for name, p in sorted(files.items())
    ]
    write_json(files["PENTARELEASE_EVIDENCE.json"], evidence)
    return files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repository", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--policy", default=".pentarelease/policy.json")
    ap.add_argument("--source-dir", default="/tmp/pentarelease-source")
    ap.add_argument("--outdir", default="dist/pentarelease-surface")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--no-sync-repository", action="store_true")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    policy = read_json(repo_root / args.policy, {})
    cfg = policy.get("release_surface") or {}
    if not cfg.get("enabled", True):
        raise SystemExit("PentaRelease release surface is disabled by policy.")

    source_dir = Path(args.source_dir)
    manifest_path = source_dir / "MANIFEST.json"
    manifest = read_json(manifest_path, {})
    release = release_view(args.repository, args.tag)
    cie = discover_cie(repo_root, manifest)
    cost = discover_direct_cost(manifest, source_dir)
    changed = changed_files_from_manifest(manifest)
    inventory = file_inventory(repo_root, changed)
    record = release_record(args.repository, args.tag, release, manifest, cie, cost, inventory)
    if manifest_path.exists():
        record["evidence"]["source_manifest_sha256"] = sha256_file(manifest_path)

    outdir = Path(args.outdir)
    assets = build_assets(outdir, record, release.get("body") or "")

    if not args.no_sync_repository:
        state_path = repo_root / str(cfg.get("state_file") or ".pentarelease/state/release-surface.json")
        state = read_json(state_path, {"schema": "ct.pentarelease.release-surface-state.v1"})
        state["last_release"] = args.tag
        state["updated_at"] = now_utc()
        state = sync_repository_surfaces(repo_root, policy, record, state)
        state = write_pentadocs_pages(repo_root, record, state)
        state = sync_pentadocs_nav(repo_root, policy, state)
        write_json(state_path, state)

    result = {
        "status": "materialized",
        "tag": args.tag,
        "official_release_url": record["official_release_url"],
        "asset_count": len(assets),
        "assets": [str(p) for p in assets.values()],
        "repository_surfaces": len((policy.get("release_surface") or {}).get("repository_surfaces") or []),
        "cie_status": cie.get("status"),
        "cost_status": cost.get("status"),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
