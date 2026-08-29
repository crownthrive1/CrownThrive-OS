#!/usr/bin/env python3
"""Build a release-specific Cultural Imprint Engine subject from governed evidence.

This adapter does not calculate a CIE score. It materializes objective, release-linked
evidence for each governed CIE dimension and leaves scoring to public.ct_cie_score.
It never invents findings, claims, costs, or authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DIMENSIONS = (
    "identity_fit",
    "community_value",
    "story_alignment",
    "brand_safety",
    "legacy_impact",
)


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def changed_files(manifest: dict[str, Any]) -> list[str]:
    decision = manifest.get("decision") if isinstance(manifest.get("decision"), dict) else {}
    values = decision.get("changed_files") or manifest.get("changed_files") or []
    return [str(value) for value in values if isinstance(value, str)]


def rationale(manifest: dict[str, Any], release_notes: str) -> str:
    decision = manifest.get("decision") if isinstance(manifest.get("decision"), dict) else {}
    value = decision.get("why") or manifest.get("why") or manifest.get("reason")
    if value:
        return str(value).strip()
    for line in release_notes.splitlines():
        text = line.strip()
        if text and not text.startswith("#"):
            return text[:500]
    return "Release-specific rationale is represented by the governed release notes artifact."


def release_target(manifest: dict[str, Any], provider: dict[str, Any]) -> str | None:
    decision = manifest.get("decision") if isinstance(manifest.get("decision"), dict) else {}
    for value in (
        manifest.get("target_ref"),
        manifest.get("target"),
        decision.get("target"),
        provider.get("target_commitish"),
    ):
        if value:
            return str(value)
    return None


def build(
    repository: str,
    tag: str,
    version: str,
    manifest_path: Path,
    notes_path: Path,
    provider_path: Path,
    sums_path: Path,
) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    provider = read_json(provider_path)
    notes = read_text(notes_path)
    paths = changed_files(manifest)
    why = rationale(manifest, notes)
    target = release_target(manifest, provider)
    assets = provider.get("assets") if isinstance(provider.get("assets"), list) else []
    asset_names = [str(a.get("name")) for a in assets if isinstance(a, dict) and a.get("name")]

    manifest_sha = sha256(manifest_path)
    notes_sha = sha256(notes_path)
    provider_sha = sha256(provider_path)
    sums_sha = sha256(sums_path)

    common = {
        "repository": repository,
        "release_tag": tag,
        "release_version": version,
        "target_ref": target,
        "manifest_sha256": manifest_sha,
        "provider_release_sha256": provider_sha,
    }

    dimension_evidence: dict[str, list[dict[str, Any]]] = {
        "identity_fit": [{
            **common,
            "evidence_type": "release_identity_and_provenance",
            "source": "MANIFEST.json + provider release readback",
            "publisher": manifest.get("publisher") or "PentaRelease",
            "provider_actor": ((provider.get("author") or {}).get("login") if isinstance(provider.get("author"), dict) else None),
        }],
        "community_value": [{
            **common,
            "evidence_type": "release_scope_and_rationale",
            "source": "MANIFEST.json + RELEASE_NOTES.md",
            "release_rationale": why,
            "changed_path_count": len(paths),
            "changed_paths": paths[:100],
            "interpretation_boundary": "Evidence records release scope and rationale; it does not manufacture a claim of positive community impact.",
        }],
        "story_alignment": [{
            **common,
            "evidence_type": "governed_release_narrative",
            "source": "RELEASE_NOTES.md",
            "release_notes_sha256": notes_sha,
            "release_rationale": why,
            "interpretation_boundary": "The CIE algorithm, not this adapter, determines the dimension score.",
        }],
        "brand_safety": [{
            **common,
            "evidence_type": "provider_readback_and_integrity",
            "source": "provider release readback + MANIFEST.json + SHA256SUMS when present",
            "provider_draft": bool(provider.get("draft")),
            "provider_prerelease": bool(provider.get("prerelease")),
            "provider_asset_names": asset_names,
            "sha256sums_sha256": sums_sha,
            "integrity_artifact_present": bool(sums_sha or manifest_sha),
            "interpretation_boundary": "This is integrity/readback evidence only; no absence-of-risk claim is manufactured.",
        }],
        "legacy_impact": [{
            **common,
            "evidence_type": "versioned_release_continuity",
            "source": "versioned release provenance + provider readback",
            "published_at": provider.get("published_at"),
            "created_at": provider.get("created_at"),
            "release_notes_sha256": notes_sha,
            "changed_path_count": len(paths),
            "interpretation_boundary": "Evidence records durable versioned continuity; it does not manufacture long-term impact claims.",
        }],
    }

    missing = [name for name in DIMENSIONS if not dimension_evidence.get(name)]
    if missing:
        raise RuntimeError(f"missing CIE dimension evidence: {', '.join(missing)}")
    if not manifest_sha or not provider_sha:
        raise RuntimeError("governed manifest and provider release readback are required for CIE subject materialization")

    return {
        "schema": "ct.pentarelease.cie-subject.v1",
        "subject_id": version,
        "subject_type": "release",
        "dimension_evidence": dimension_evidence,
        "findings": [],
        "finding_policy": "No findings are synthesized by the release adapter. Governed findings, if any, must arrive from an evidence-producing control.",
        "evidence_summary": {
            "dimension_count": len(DIMENSIONS),
            "dimension_evidence_counts": {name: len(dimension_evidence[name]) for name in DIMENSIONS},
            "manifest_sha256": manifest_sha,
            "release_notes_sha256": notes_sha,
            "provider_release_sha256": provider_sha,
            "sha256sums_sha256": sums_sha,
        },
        "provenance": {
            "repository": repository,
            "release_tag": tag,
            "release_version": version,
            "target_ref": target,
            "provider_release_url": provider.get("html_url"),
            "adapter": "scripts/pentarelease/build_cie_subject.py",
            "score_calculated_here": False,
            "authority_manufactured": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--release-notes", required=True)
    parser.add_argument("--provider-release", required=True)
    parser.add_argument("--sha256sums", required=False, default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    subject = build(
        args.repository,
        args.tag,
        args.version,
        Path(args.manifest),
        Path(args.release_notes),
        Path(args.provider_release),
        Path(args.sha256sums) if args.sha256sums else Path("/__pentarelease_missing_sha256sums__"),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(subject, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "materialized",
        "subject_id": subject["subject_id"],
        "dimensions": list(subject["dimension_evidence"].keys()),
        "findings": 0,
        "output": str(output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
