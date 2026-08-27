#!/usr/bin/env python3
"""PentaRelease comprehensive release + bounded release-surface synchronizer.

Production invariants:
- Canonical GitHub release identity always belongs to the repository being synchronized.
- PentaCosts is the sole authority for actual execution-cost evidence.
- PentaMarket and SmartTreasury may enrich economic context but may not manufacture actual cost.
- CIE evidence must be cryptographically/release bound before a score is surfaced.
- Unknown economics, cultural evidence, and certification remain explicit HOLD/not-available values.
- Managed repository/docs surfaces preserve unmanaged human content and configured ceilings.
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
SCORE_KEYS = {"cie_score", "cultural_imprint_score", "cultural_imprint_engine_score", "imprint_score", "score"}
COST_KEYS = {"direct_cost_usd", "execution_cost_usd", "cost_usd"}
PENTACOSTS_AUTHORITIES = {"pentacosts", "penta_costs", "ct.pentacosts"}
CIE_AUTHORITIES = {"cie", "cultural imprint engine", "cultural_imprint_engine", "ct.cie"}


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
    return base + ("\n\n" if base else "") + managed + "\n"


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


def canonical_release_url(repository: str, tag: str) -> str:
    return f"https://github.com/{repository}/releases/tag/{tag}"


def tag_commit_sha(repository: str, tag: str) -> str | None:
    try:
        ref = run_json("gh", "api", f"repos/{repository}/git/ref/tags/{tag}")
        obj = ref.get("object") if isinstance(ref, dict) else None
        return str(obj.get("sha")) if isinstance(obj, dict) and obj.get("sha") else None
    except Exception:
        return None


def release_identity(repository: str, tag: str, release: dict[str, Any], manifest_sha256: str | None = None) -> dict[str, Any]:
    return {
        "repository": repository,
        "tag": tag,
        "commit_sha": tag_commit_sha(repository, tag),
        "manifest_sha256": manifest_sha256,
        "official_release_url": canonical_release_url(repository, tag),
        "provider_target": release.get("targetCommitish"),
    }


def _authority(payload: dict[str, Any]) -> str:
    for key in ("authority", "producer", "provider", "engine", "asserted_by"):
        value = payload.get(key)
        if value:
            return str(value).strip().lower()
    return ""


def _binding(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("release_binding", "binding", "release_identity"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def evidence_matches_release(payload: dict[str, Any], identity: dict[str, Any]) -> tuple[bool, str]:
    binding = _binding(payload)
    expected_tag = str(identity.get("tag") or "")
    expected_repo = str(identity.get("repository") or "")
    expected_sha = str(identity.get("commit_sha") or "")
    expected_manifest = str(identity.get("manifest_sha256") or "")

    actual_tag = binding.get("tag") or binding.get("release_tag") or binding.get("external_release_tag")
    actual_repo = binding.get("repository") or binding.get("repo")
    actual_sha = binding.get("commit_sha") or binding.get("source_sha") or binding.get("git_sha")
    actual_manifest = binding.get("manifest_sha256") or binding.get("source_manifest_sha256")

    if not actual_tag or str(actual_tag) != expected_tag:
        return False, "release_tag_mismatch_or_missing"
    if actual_repo and str(actual_repo) != expected_repo:
        return False, "repository_mismatch"
    if expected_sha and (not actual_sha or str(actual_sha) != expected_sha):
        return False, "commit_sha_mismatch_or_missing"
    if expected_manifest and actual_manifest and str(actual_manifest) != expected_manifest:
        return False, "manifest_sha256_mismatch"
    evidence_hash = payload.get("evidence_hash") or binding.get("evidence_hash")
    if not evidence_hash:
        return False, "evidence_hash_missing"
    return True, "release_bound"


def _candidate_json(source_dir: Path | None, repo_root: Path, names: list[str]) -> list[Path]:
    out: list[Path] = []
    for base in [source_dir, repo_root / ".pentarelease" / "evidence"]:
        if not base:
            continue
        for name in names:
            p = Path(base) / name
            if p.is_file() and p.stat().st_size <= 1_000_000:
                out.append(p)
    return out


def discover_direct_cost(
    manifest: dict[str, Any],
    source_dir: Path,
    identity: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or Path(".")
    rejected: list[dict[str, str]] = []
    candidates = _candidate_json(source_dir, root, [
        "PENTACOSTS_EVIDENCE.json",
        "PENTARELEASE_PROVIDER_EVIDENCE.json",
        "PENTARELEASE_COSTS.json",
    ])
    for p in candidates:
        try:
            payload = read_json(p, {})
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        authority = _authority(payload)
        if authority not in PENTACOSTS_AUTHORITIES:
            rejected.append({"source": p.name, "reason": "authority_not_pentacosts"})
            continue
        if identity:
            ok, reason = evidence_matches_release(payload, identity)
            if not ok:
                rejected.append({"source": p.name, "reason": reason})
                continue
        hit = recursive_find_key(payload, COST_KEYS)
        status = str(payload.get("cost_status") or payload.get("status") or "available").lower()
        if hit and status in {"available", "certified", "settled"}:
            return {
                "status": status,
                "direct_cost_usd": normalized_numeric_or_raw(hit[1]),
                "source": f"{p.name}:{hit[0]}",
                "authority": "PentaCosts",
                "evidence_hash": payload.get("evidence_hash"),
                "release_binding": _binding(payload),
                "penta_market": payload.get("penta_market") or payload.get("market_context"),
                "smart_treasury": payload.get("smart_treasury") or payload.get("treasury_context"),
                "invented": False,
            }
    manifest_evidence = manifest.get("pentacosts") or manifest.get("penta_costs")
    if isinstance(manifest_evidence, dict) and _authority(manifest_evidence) in PENTACOSTS_AUTHORITIES:
        ok, reason = evidence_matches_release(manifest_evidence, identity) if identity else (True, "legacy")
        hit = recursive_find_key(manifest_evidence, COST_KEYS)
        if ok and hit:
            return {
                "status": str(manifest_evidence.get("status") or "available"),
                "direct_cost_usd": normalized_numeric_or_raw(hit[1]),
                "source": f"MANIFEST.json:pentacosts.{hit[0]}",
                "authority": "PentaCosts",
                "evidence_hash": manifest_evidence.get("evidence_hash"),
                "release_binding": _binding(manifest_evidence),
                "penta_market": manifest_evidence.get("penta_market"),
                "smart_treasury": manifest_evidence.get("smart_treasury"),
                "invented": False,
            }
        rejected.append({"source": "MANIFEST.json:pentacosts", "reason": reason})
    return {
        "status": "not_available",
        "direct_cost_usd": None,
        "source": None,
        "authority": "PentaCosts",
        "reason": "No authoritative release-bound PentaCosts execution-cost attestation was supplied.",
        "rejected_evidence": rejected,
        "invented": False,
    }


def discover_cie(
    repo_root: Path,
    manifest: dict[str, Any],
    identity: dict[str, Any] | None = None,
    source_dir: Path | None = None,
) -> dict[str, Any]:
    rejected: list[dict[str, str]] = []
    candidates = _candidate_json(source_dir, repo_root, ["CIE_RELEASE_EVIDENCE.json", "PENTARELEASE_CIE_SCORE.json"])
    for raw in changed_files_from_manifest(manifest):
        p = repo_root / raw
        low = raw.lower()
        if p.is_file() and p.suffix.lower() == ".json" and ("cie" in low or "cultural" in low or "imprint" in low) and p.stat().st_size <= 1_000_000:
            candidates.append(p)
    manifest_evidence = manifest.get("cie_evidence") or manifest.get("cultural_imprint_evidence")
    values: list[tuple[str, dict[str, Any]]] = []
    if isinstance(manifest_evidence, dict):
        values.append(("MANIFEST.json:cie_evidence", manifest_evidence))
    for p in candidates:
        try:
            payload = read_json(p, {})
        except Exception:
            continue
        if isinstance(payload, dict):
            values.append((str(p.relative_to(repo_root)) if p.is_relative_to(repo_root) else p.name, payload))
    for source, payload in values:
        authority = _authority(payload)
        if authority not in CIE_AUTHORITIES:
            rejected.append({"source": source, "reason": "authority_not_cie"})
            continue
        if identity:
            ok, reason = evidence_matches_release(payload, identity)
            if not ok:
                rejected.append({"source": source, "reason": reason})
                continue
        hit = recursive_find_key(payload, SCORE_KEYS)
        status = str(payload.get("status") or payload.get("cie_status") or "available").lower()
        if hit and status in {"available", "certified", "pass", "passed"}:
            return {
                "status": status,
                "score": normalized_numeric_or_raw(hit[1]),
                "source": source + f":{hit[0]}",
                "authority": "CIE",
                "engine_version": payload.get("engine_version") or payload.get("version"),
                "evidence_hash": payload.get("evidence_hash"),
                "release_binding": _binding(payload),
                "invented": False,
            }
    return {
        "status": "not_available",
        "score": None,
        "source": None,
        "authority": "CIE",
        "reason": "No authoritative release-bound CIE attestation was supplied.",
        "rejected_evidence": rejected,
        "invented": False,
    }


def release_view(repository: str, tag: str) -> dict[str, Any]:
    return run_json("gh", "release", "view", tag, "--repo", repository, "--json", "tagName,name,url,isDraft,isPrerelease,targetCommitish,assets,body,publishedAt,createdAt")


def file_inventory(repo_root: Path, paths: Iterable[str]) -> list[dict[str, Any]]:
    rows = []
    for raw in paths:
        p = repo_root / raw
        if p.is_file():
            data = p.read_bytes()
            rows.append({"path": raw, "status": "available", "bytes": len(data), "sha256": sha256_bytes(data)})
        elif p.exists():
            rows.append({"path": raw, "status": "available_non_file", "bytes": None, "sha256": None})
        else:
            rows.append({"path": raw, "status": "not_available", "bytes": None, "sha256": None})
    return rows


def sanitize_original_release_body(body: str, repository: str | None = None, tag: str | None = None) -> str:
    text = strip_managed_block(body or "", RELEASE_BLOCK_START, RELEASE_BLOCK_END)
    if repository and tag:
        canonical = canonical_release_url(repository, tag)
        text = re.sub(r"https://github\.com/[^/]+/CrownThrive-Support/releases/tag/" + re.escape(tag) + r"\b", canonical, text)
    return text


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
    decision = manifest.get("decision") if isinstance(manifest.get("decision"), dict) else {}
    for value in (manifest.get("target_ref"), manifest.get("target"), decision.get("target"), release.get("targetCommitish")):
        if value and str(value) not in out:
            out.append(str(value))
    return out or ["not_available"]


def discover_penta_components(manifest: dict[str, Any], changed: list[str]) -> list[str]:
    text = json.dumps(manifest, ensure_ascii=False) + "\n" + "\n".join(changed)
    names = {"PentaRelease", "PentaCosts", "PentaMarket", "PentaTreasury"}
    for token in re.findall(r"\bPenta[A-Z][A-Za-z0-9]+\b", text):
        names.add(token)
    return sorted(names)


def derive_ecosystem_lanes(changed: list[str]) -> list[str]:
    lanes: list[str] = []
    for path in changed:
        top = path.split("/", 1)[0]
        if top and top not in {".github", ".pentarelease"} and top not in lanes:
            lanes.append(top)
    return lanes


def derive_why(manifest: dict[str, Any]) -> str:
    decision = manifest.get("decision") if isinstance(manifest.get("decision"), dict) else {}
    return str(decision.get("why") or manifest.get("why") or "Release rationale was not separately supplied; see preserved original release notes.")


def release_record(repository: str, tag: str, release: dict[str, Any], manifest: dict[str, Any], cie: dict[str, Any], cost: dict[str, Any], inventory: list[dict[str, Any]], identity: dict[str, Any] | None = None) -> dict[str, Any]:
    changed = changed_files_from_manifest(manifest)
    changed_payload_bytes = sum(int(x.get("bytes") or 0) for x in inventory if x.get("status") == "available")
    cost = copy.deepcopy(cost)
    cost["changed_file_payload_bytes"] = changed_payload_bytes
    cost["changed_file_payload_count"] = sum(1 for x in inventory if x.get("status") == "available")
    cost["payload_measurement_note"] = "Payload bytes are operational measurements, not a substitute for authoritative execution cost."
    identity = identity or release_identity(repository, tag, release)
    economic_ok = cost.get("status") in {"available", "certified", "settled"} and cost.get("direct_cost_usd") is not None
    cultural_ok = cie.get("status") in {"available", "certified", "pass", "passed"} and cie.get("score") is not None
    decision = manifest.get("decision") if isinstance(manifest.get("decision"), dict) else {}
    governance_state = str(decision.get("certification_state") or manifest.get("certification_state") or "not_available")
    return {
        "schema": "ct.pentarelease.comprehensive-release.v2",
        "release_id": manifest.get("release_id") or f"ct.release.{tag}",
        "tag": tag,
        "title": release.get("name") or manifest.get("title") or tag,
        "official_release_url": canonical_release_url(repository, tag),
        "what_pentarelease_is": "PentaRelease is CrownThrive OS's governed release publication, evidence, provenance, economics/cultural disclosure, and release-surface synchronization layer.",
        "what_changed": changed,
        "why": derive_why(manifest),
        "penta_components": discover_penta_components(manifest, changed),
        "ecosystem_lanes": derive_ecosystem_lanes(changed),
        "targets": derive_targets(manifest, release),
        "version_scheme": manifest.get("version_scheme"),
        "publisher": manifest.get("publisher") or "PentaRelease",
        "publisher_contract": manifest.get("publisher_contract"),
        "payload_costs": cost,
        "cie_score": cie,
        "data_availability": {
            "changed_files": inventory,
            "release_asset_count": len(release.get("assets") or []),
            "release_assets": [{"name": a.get("name"), "size": a.get("size"), "url": a.get("url")} for a in (release.get("assets") or [])],
        },
        "evidence": {
            "provider_release_readback": True,
            "is_draft": bool(release.get("isDraft")),
            "is_prerelease": bool(release.get("isPrerelease")),
            "manifest_present": bool(manifest),
            "source_manifest_sha256": identity.get("manifest_sha256"),
            "release_binding": identity,
            "provenance_dimensions": {
                "technical": "verified" if identity.get("commit_sha") else "hold",
                "economic": "verified" if economic_ok else "hold",
                "cultural": "verified" if cultural_ok else "hold",
                "governance": governance_state,
            },
        },
        "provenance": {
            "repository": repository,
            "release_target": release.get("targetCommitish"),
            "release_commit_sha": identity.get("commit_sha"),
            "published_at": release.get("publishedAt"),
            "created_at": release.get("createdAt"),
            "generated_at": now_utc(),
            "unknown_values_are_explicit": True,
            "costs_invented": False,
            "cie_score_invented": False,
            "canonical_repository_identity": True,
        },
    }


def render_comprehensive_block(record: dict[str, Any]) -> str:
    cost, cie = record["payload_costs"], record["cie_score"]
    inv = record["data_availability"]["changed_files"]
    cost_value = cost.get("direct_cost_usd")
    cost_text = f"${cost_value}" if cost_value is not None else "Not available — authoritative PentaCosts evidence is absent."
    cie_text = str(cie.get("score")) if cie.get("score") is not None else "Not available — authoritative release-bound CIE evidence is absent."
    dimensions = record["evidence"].get("provenance_dimensions") or {}
    return f"""## PentaRelease Comprehensive Release Record

**Official release:** {record['official_release_url']}

### What PentaRelease is

{record['what_pentarelease_is']}

### Penta / subsystem context

- **Penta components observed:** {', '.join(f'`{x}`' for x in record.get('penta_components') or ['PentaRelease'])}
- **Ecosystem lanes:** {', '.join(f'`{x}`' for x in record.get('ecosystem_lanes') or []) or 'not available'}

### What changed

{summarize_changes(record['what_changed'])}

### Why this release exists

{record['why']}

### Targets / publication disposition

{', '.join(f'`{x}`' for x in record['targets'])}

### Payload economics

- **Direct USD execution cost:** {cost_text}
- **Cost status:** `{cost.get('status')}`
- **Cost authority:** `PentaCosts`
- **Cost source:** `{cost.get('source') or 'not_available'}`
- **Cost evidence hash:** `{cost.get('evidence_hash') or 'not_available'}`
- **Changed-file payload bytes:** {cost.get('changed_file_payload_bytes', 0)}
- PentaMarket supplies certified rate context and SmartTreasury supplies budget/settlement context; neither may invent actual cost.

### Cultural Imprint Engine (CIE)

- **CIE score:** {cie_text}
- **CIE status:** `{cie.get('status')}`
- **CIE source:** `{cie.get('source') or 'not_available'}`
- **CIE evidence hash:** `{cie.get('evidence_hash') or 'not_available'}`
- CIE scores surface only when evidence is bound to this repository/tag/commit identity.

### Provenance dimensions

- **Technical:** `{dimensions.get('technical', 'hold')}`
- **Economic:** `{dimensions.get('economic', 'hold')}`
- **Cultural:** `{dimensions.get('cultural', 'hold')}`
- **Governance:** `{dimensions.get('governance', 'not_available')}`

### Data availability

- Changed paths declared: **{len(inv)}**
- Available as files in synchronized checkout: **{sum(1 for x in inv if x['status'] == 'available')}**
- Published GitHub release assets observed: **{record['data_availability']['release_asset_count']}**

### Evidence and provenance

- Provider release readback: **verified**
- Canonical repository: `{record['provenance']['repository']}`
- Release commit SHA: `{record['provenance']['release_commit_sha'] or 'not_available'}`
- Manifest SHA-256: `{record['evidence']['source_manifest_sha256'] or 'not_available'}`
- Unknown evidence remains explicit HOLD/not-available; version numbers never promote a HOLD.
"""


def render_full_release(original_body: str, record: dict[str, Any]) -> str:
    base = sanitize_original_release_body(original_body, record["provenance"]["repository"], record["tag"])
    managed = f"{RELEASE_BLOCK_START}\n{render_comprehensive_block(record).rstrip()}\n{RELEASE_BLOCK_END}"
    return base + ("\n\n" if base else "") + managed + "\n"


def render_faq(record: dict[str, Any]) -> str:
    return f"""# Release FAQ — {record['tag']}

## Where is the official release?
{record['official_release_url']}

## What is authoritative?
The GitHub Release above is canonical publication identity. Actual execution cost is authoritative only when supplied by release-bound PentaCosts evidence; PentaMarket supplies rate context, SmartTreasury supplies budget/settlement context, and CIE scores require release-bound CIE evidence.

## What evidence is available?
See `PENTARELEASE_EVIDENCE.json`, `PENTARELEASE_DATA_CATALOG.json`, `PENTARELEASE_COSTS.json`, `PENTARELEASE_CIE_SCORE.json`, package checksums, and provider readback.
"""


def render_changelog(record: dict[str, Any]) -> str:
    return f"""# Changelog — {record['tag']}

- **Release:** [{record['tag']}]({record['official_release_url']})
- **Title:** {record['title']}
- **Why:** {record['why']}
- **Changed paths:** {len(record['what_changed'])}
- **CIE:** {record['cie_score'].get('score') if record['cie_score'].get('score') is not None else 'not available'}
- **Direct USD cost:** {record['payload_costs'].get('direct_cost_usd') if record['payload_costs'].get('direct_cost_usd') is not None else 'not available'}

## Changed paths

{summarize_changes(record['what_changed'])}
"""


def surface_block(label: str, record: dict[str, Any]) -> str:
    legal = ""
    if label.lower() == "license":
        legal = "\n**Non-normative release metadata:** this managed block does not amend, replace, or reinterpret license terms outside this block.\n"
    return f"""## Latest PentaRelease — {record['tag']}
{legal}
- **Official release:** {record['official_release_url']}
- **Release title:** {record['title']}
- **Direct USD execution cost:** {record['payload_costs'].get('direct_cost_usd') if record['payload_costs'].get('direct_cost_usd') is not None else 'not available'}
- **CIE score:** {record['cie_score'].get('score') if record['cie_score'].get('score') is not None else 'not available'}
- **Provenance:** technical + economic + cultural + governance evidence in the official release assets.

This section is maintained by PentaRelease. Content outside the managed markers remains under existing ownership and editorial authority.
"""


def safe_created_file_content(label: str, block: str, start: str, end: str) -> str:
    return f"# {label}\n\n{start}\n{block.rstrip()}\n{end}\n"


def safe_to_delete_created(text: str, label: str, start: str, end: str) -> bool:
    if start not in text or end not in text:
        return False
    return strip_managed_block(text, start, end).strip() in ("", f"# {label}")


def sync_repository_surfaces(repo_root: Path, policy: dict[str, Any], record: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
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
        if meta.get("created_by_pentarelease") and safe_to_delete_created(text, meta.get("label") or Path(path).stem, start, end):
            target.unlink()
        elif not meta.get("created_by_pentarelease"):
            cleaned = strip_managed_block(text, start, end)
            if cleaned != text.rstrip():
                target.write_text(cleaned.rstrip() + "\n", encoding="utf-8")
    for s in surfaces:
        path = str(s["path"])
        label = str(s.get("label") or Path(path).stem)
        target = repo_root / path
        existed = target.exists()
        old = previous.get(path) or {}
        created = bool(old.get("created_by_pentarelease")) if old else not existed
        block = surface_block(label, record)
        target.parent.mkdir(parents=True, exist_ok=True)
        if existed:
            target.write_text(upsert_managed_block(target.read_text(encoding="utf-8"), block, start, end), encoding="utf-8")
        else:
            target.write_text(safe_created_file_content(label, block, start, end), encoding="utf-8")
        next_state[path] = {"label": label, "created_by_pentarelease": created, "first_release": old.get("first_release") or record["tag"], "last_release": record["tag"]}
    state["repository_surfaces"] = next_state
    return state


def docs_page(title: str, body: str, description: str) -> str:
    body = body.rstrip()
    if not re.search(r"(?m)^#\s+", body):
        body = f"# {title}\n\n{body}"
    return f'---\ntitle: "{title}"\ndescription: "{description}"\n---\n\n{body}\n'


def write_pentadocs_pages(repo_root: Path, record: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    pages = {
        "pentarelease/latest.mdx": docs_page(f"Latest Release — {record['tag']}", render_comprehensive_block(record), "Canonical PentaRelease technical, economic, cultural, and governance provenance."),
        "pentarelease/faq.mdx": docs_page("Release FAQ", render_faq(record), "Current PentaRelease FAQ linked to the canonical GitHub release."),
        "pentarelease/changelog.mdx": docs_page("Release Changelog", render_changelog(record), "Current release changelog."),
        "pentarelease/costs.mdx": docs_page("Release Costs", f"# Payload Economics — {record['tag']}\n\n```json\n{json.dumps(record['payload_costs'], indent=2)}\n```", "Authoritative PentaCosts disclosure with PentaMarket and SmartTreasury context."),
        "pentarelease/cie.mdx": docs_page("CIE Release Evidence", f"# CIE — {record['tag']}\n\n```json\n{json.dumps(record['cie_score'], indent=2)}\n```", "Release-bound Cultural Imprint Engine evidence."),
        "pentarelease/data.mdx": docs_page("Release Data", f"# Data Availability — {record['tag']}\n\n```json\n{json.dumps(record['data_availability'], indent=2)}\n```", "Path-level and provider data availability."),
        "pentarelease/evidence.mdx": docs_page("Release Evidence", f"# Evidence — {record['tag']}\n\n```json\n{json.dumps(record['evidence'] | record['provenance'], indent=2)}\n```", "Release-bound provenance evidence."),
    }
    previous = state.get("pentadocs_pages") or {}
    for path, content in pages.items():
        target = repo_root / path
        existed = target.exists()
        old = previous.get(path) or {}
        target.parent.mkdir(parents=True, exist_ok=True)
        if existed and not old:
            previous[path] = {"created_by_pentarelease": False, "last_release": None, "status": "collision_preserved"}
            continue
        if existed and old and not old.get("created_by_pentarelease"):
            previous[path]["status"] = "collision_preserved"
            continue
        target.write_text(content, encoding="utf-8")
        previous[path] = {"created_by_pentarelease": bool(old.get("created_by_pentarelease")) if old else not existed, "last_release": record["tag"], "status": "managed"}
    state["pentadocs_pages"] = previous
    return state


def sync_pentadocs_nav(repo_root: Path, policy: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    cfg = (policy.get("release_surface") or {}).get("pentadocs") or {}
    if not cfg.get("enabled", True):
        return state
    docs_path = repo_root / str(cfg.get("config") or "docs.json")
    docs = read_json(docs_path, {})
    tabs = docs.setdefault("navigation", {}).setdefault("tabs", [])
    max_tabs = int((policy.get("release_surface") or {}).get("max_pentadocs_tabs", 7))
    tab_name = str(cfg.get("tab") or "Releases & Evidence")
    expected = {"tab": tab_name, "groups": [{"group": "PentaRelease", "icon": "box-archive", "pages": list(cfg.get("pages") or [])}]}
    matches = [i for i, t in enumerate(tabs) if isinstance(t, dict) and t.get("tab") == tab_name]
    prior = state.get("pentadocs_nav") or {}
    if matches:
        if prior.get("created_by_pentarelease"):
            tabs[matches[0]] = expected
        else:
            state["pentadocs_nav"] = {"tab": tab_name, "created_by_pentarelease": False, "status": "collision_preserved"}
    else:
        if len(tabs) + 1 > max_tabs:
            raise RuntimeError(f"adding PentaRelease PentaDocs tab would create {len(tabs)+1} tabs; maximum is {max_tabs}")
        tabs.append(expected)
        state["pentadocs_nav"] = {"tab": tab_name, "created_by_pentarelease": True, "status": "managed"}
    if len(tabs) > max_tabs:
        raise RuntimeError(f"PentaDocs contains {len(tabs)} tabs; maximum configured is {max_tabs}")
    write_json(docs_path, docs)
    return state


def build_assets(outdir: Path, record: dict[str, Any], original_body: str) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    evidence = {**record["evidence"], **record["provenance"], "official_release_url": record["official_release_url"], "release_id": record["release_id"], "tag": record["tag"]}
    content = {
        "PENTARELEASE_COMPREHENSIVE_RELEASE.md": render_full_release(original_body, record),
        "PENTARELEASE_RELEASE_RECORD.json": json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        "PENTARELEASE_COSTS.json": json.dumps(record["payload_costs"], indent=2, ensure_ascii=False) + "\n",
        "PENTARELEASE_CIE_SCORE.json": json.dumps(record["cie_score"], indent=2, ensure_ascii=False) + "\n",
        "PENTARELEASE_DATA_CATALOG.json": json.dumps(record["data_availability"], indent=2, ensure_ascii=False) + "\n",
        "PENTARELEASE_EVIDENCE.json": json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        "PENTARELEASE_FAQ.md": render_faq(record),
        "PENTARELEASE_CHANGELOG.md": render_changelog(record),
    }
    files: dict[str, Path] = {}
    for name, value in content.items():
        p = outdir / name
        p.write_text(value, encoding="utf-8")
        files[name] = p
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
    manifest_sha = sha256_file(manifest_path) if manifest_path.exists() else None
    release = release_view(args.repository, args.tag)
    identity = release_identity(args.repository, args.tag, release, manifest_sha)
    cost = discover_direct_cost(manifest, source_dir, identity, repo_root)
    cie = discover_cie(repo_root, manifest, identity, source_dir)
    inventory = file_inventory(repo_root, changed_files_from_manifest(manifest))
    record = release_record(args.repository, args.tag, release, manifest, cie, cost, inventory, identity)
    outdir = Path(args.outdir)
    assets = build_assets(outdir, record, release.get("body") or "")
    if not args.no_sync_repository:
        state_path = repo_root / str(cfg.get("state_file") or ".pentarelease/state/release-surface.json")
        state = read_json(state_path, {"schema": "ct.pentarelease.release-surface-state.v1"})
        state["last_release"] = args.tag
        state["last_release_commit_sha"] = identity.get("commit_sha")
        state["canonical_repository"] = args.repository
        state["updated_at"] = now_utc()
        state = sync_repository_surfaces(repo_root, policy, record, state)
        state = write_pentadocs_pages(repo_root, record, state)
        state = sync_pentadocs_nav(repo_root, policy, state)
        write_json(state_path, state)
    print(json.dumps({"status": "materialized", "tag": args.tag, "official_release_url": record["official_release_url"], "release_commit_sha": identity.get("commit_sha"), "asset_count": len(assets), "repository_surfaces": len(cfg.get("repository_surfaces") or []), "cie_status": cie.get("status"), "cost_status": cost.get("status")}, indent=2))


if __name__ == "__main__":
    main()
