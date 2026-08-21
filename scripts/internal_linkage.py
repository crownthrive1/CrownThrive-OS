#!/usr/bin/env python3
"""Candidate-first internal-link scanner and additive approved-link applicator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
TITLE_RE = re.compile(r"(?m)^title:\s*[\"']?(.+?)[\"']?\s*$")


def inside(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes documentation root: {candidate}") from exc
    return resolved


def doc_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.suffix.lower() in {".md", ".mdx"} and path.is_file())


def resolve_link(source: Path, target: str, root: Path) -> Path | None:
    if target.startswith(("http://", "https://", "mailto:", "#")):
        return None
    plain = target.split("#", 1)[0].split("?", 1)[0]
    if not plain:
        return None
    base = root if plain.startswith("/") else source.parent
    candidate = inside(root, base / plain.lstrip("/"))
    possibilities = [candidate]
    if not candidate.suffix:
        possibilities.extend([candidate.with_suffix(".mdx"), candidate.with_suffix(".md"), candidate / "index.mdx", candidate / "index.md"])
    return next((path for path in possibilities if path.is_file()), candidate)


def scan(root: Path) -> dict[str, Any]:
    broken: list[dict[str, str]] = []
    titles: list[dict[str, str]] = []
    files = doc_files(root)
    for path in files:
        text = path.read_text(encoding="utf-8")
        title_match = TITLE_RE.search(text)
        titles.append({"path": path.relative_to(root).as_posix(), "title": title_match.group(1).strip() if title_match else path.stem})
        for target in LINK_RE.findall(text):
            resolved = resolve_link(path, target, root)
            if resolved is not None and not resolved.is_file():
                broken.append({"source": path.relative_to(root).as_posix(), "target": target})
    digest = hashlib.sha256(json.dumps(titles, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"status": "PASS" if not broken else "NEED_TO_DO", "document_count": len(files), "title_index_sha256": digest, "broken_links": broken}


def apply_approved(root: Path, manifest: Path) -> dict[str, Any]:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    applied: list[str] = []
    skipped: list[dict[str, str]] = []
    for edge in data.get("edges", []):
        edge_id = edge.get("edge_id", "<missing>")
        if edge.get("status") != "APPROVED" or not edge.get("approval_receipt"):
            skipped.append({"edge_id": edge_id, "reason": "approval receipt absent"})
            continue
        source = inside(root, root / edge["source"])
        target = inside(root, root / edge["target"])
        if not source.is_file() or not target.is_file():
            skipped.append({"edge_id": edge_id, "reason": "source or target missing"})
            continue
        relative = os.path.relpath(target, source.parent).replace(os.sep, "/")
        current = source.read_text(encoding="utf-8")
        marker = f"<!-- CT-MANAGED-LINK:{edge_id} -->"
        if marker in current or f"]({relative})" in current:
            skipped.append({"edge_id": edge_id, "reason": "already present"})
            continue
        label = target.stem.replace("-", " ").title()
        block = f"\n\n{marker}\n- [{label}]({relative})\n"
        source.write_text(current.rstrip() + block, encoding="utf-8")
        applied.append(edge_id)
    return {"status": "APPLIED" if applied else "NO_CHANGE", "applied": applied, "skipped": skipped, "delete_count": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan", action="store_true")
    group.add_argument("--apply-approved", type=Path)
    args = parser.parse_args()
    try:
        result = scan(args.root) if args.scan else apply_approved(args.root, args.apply_approved)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
