#!/usr/bin/env python3
"""Build a deterministic public-safe source ZIP for the convergence skill suite."""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = [
    ".github/workflows/convergence-gap-closure-skills.yml",
    "contracts/skills/convergence-gap-closure-suite.v2.json",
    "docs/skills-fleet-gap-closure-2026-09-02.md",
    "evidence/skills-fleet-gap-closure/README.md",
    "registry/skills-fleet-gap-closure-v2.json",
    "runbooks/skills-fleet-gap-closure.md",
    "runtime/skills_fleet_gap_closure.py",
    "schemas/skill-gap-receipt.schema.json",
    "schemas/skill-gap-task.schema.json",
    "skills/convergence-gap-closure-v2",
    "tests/test_skills_fleet_gap_closure.py",
]
FIXED_DOS_DATE = (1980, 1, 1, 0, 0, 0)


def expand(paths: Iterable[str]) -> List[Path]:
    found: List[Path] = []
    for item in paths:
        path = ROOT / item
        if path.is_dir():
            found.extend(p for p in path.rglob("*") if p.is_file())
        elif path.is_file():
            found.append(path)
        else:
            raise FileNotFoundError(item)
    return sorted(set(found), key=lambda p: p.relative_to(ROOT).as_posix())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(output: Path, manifest_path: Path) -> dict:
    files = expand(INCLUDE)
    records = []
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            info = zipfile.ZipInfo(rel, FIXED_DOS_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, data)
            records.append({"path": rel, "size_bytes": len(data), "sha256": sha256_bytes(data)})
    manifest = {
        "manifest_id": "ct.manifest.skills-gap-closure-source.v2",
        "suite_id": "ct.skill-suite.convergence-gap-closure.v2",
        "file_count": len(records),
        "files": records,
        "zip_sha256": sha256_bytes(output.read_bytes()),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.manifest), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
