#!/usr/bin/env python3
"""Fail-closed ZIP and file-integrity verifier; it never extracts archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


DEFAULT_MAX_MEMBERS = 20_000
DEFAULT_MAX_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
DEFAULT_MAX_MEMBER = 512 * 1024 * 1024
DEFAULT_MAX_RATIO = 200.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_member_name(name: str) -> tuple[bool, str | None]:
    if "\x00" in name:
        return False, "NUL byte"
    if "\\" in name:
        return False, "backslash path separator"
    path = PurePosixPath(name)
    if path.is_absolute() or name.startswith("/"):
        return False, "absolute path"
    if any(part in {"..", ""} for part in path.parts if part != "."):
        return False, "empty or traversal path component"
    if len(name) >= 2 and name[1] == ":":
        return False, "drive-qualified path"
    return True, None


def inspect_zip(
    path: Path,
    *,
    strict_names: bool = False,
    max_members: int = DEFAULT_MAX_MEMBERS,
    max_uncompressed: int = DEFAULT_MAX_UNCOMPRESSED,
    max_member: int = DEFAULT_MAX_MEMBER,
    max_ratio: float = DEFAULT_MAX_RATIO,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    members: list[dict[str, Any]] = []
    seen_exact: set[str] = set()
    seen_portable: dict[str, str] = {}
    total_uncompressed = 0

    try:
        archive = zipfile.ZipFile(path, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        return {"path": str(path), "status": "FAIL", "errors": [str(exc)], "warnings": []}

    with archive:
        infos = archive.infolist()
        if len(infos) > max_members:
            errors.append(f"member count {len(infos)} exceeds limit {max_members}")
        for info in infos:
            name = info.filename
            normalized = unicodedata.normalize("NFC", name)
            portable = normalized.casefold()
            safe, reason = safe_member_name(name)
            if not safe:
                errors.append(f"unsafe member {name!r}: {reason}")
            if name in seen_exact:
                errors.append(f"duplicate member name: {name!r}")
            seen_exact.add(name)
            if portable in seen_portable and seen_portable[portable] != name:
                errors.append(f"portable-name collision: {seen_portable[portable]!r} and {name!r}")
            seen_portable[portable] = name
            if normalized != name:
                warnings.append(f"non-NFC member name: {name!r}")
            if any(ord(char) > 127 for char in name) and not (info.flag_bits & 0x800):
                message = f"non-ASCII member lacks UTF-8 flag: {name!r}"
                (errors if strict_names else warnings).append(message)
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                errors.append(f"symbolic-link member forbidden: {name!r}")
            if info.flag_bits & 0x1:
                errors.append(f"encrypted member unsupported: {name!r}")
            if info.file_size > max_member:
                errors.append(f"member {name!r} exceeds per-member limit")
            total_uncompressed += info.file_size
            if total_uncompressed > max_uncompressed:
                errors.append("total uncompressed size exceeds limit")
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > max_ratio and info.file_size > 1024 * 1024:
                errors.append(f"member {name!r} compression ratio {ratio:.1f} exceeds limit")
            members.append(
                {
                    "name": name,
                    "crc32": f"{info.CRC:08x}",
                    "compressed_size": info.compress_size,
                    "uncompressed_size": info.file_size,
                }
            )
        bad_crc = archive.testzip()
        if bad_crc:
            errors.append(f"CRC failure: {bad_crc!r}")

    return {
        "path": str(path),
        "status": "FAIL" if errors else ("PASS_WITH_WARNINGS" if warnings else "PASS"),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "member_count": len(members),
        "total_uncompressed_bytes": total_uncompressed,
        "members_digest_sha256": hashlib.sha256(
            json.dumps(members, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        "errors": errors,
        "warnings": warnings,
    }


def parse_sha256sums(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise ValueError(f"{path}:{number}: invalid SHA256SUMS record")
        relative = parts[1].lstrip("* ")
        if relative in entries:
            raise ValueError(f"{path}:{number}: duplicate manifest path {relative}")
        entries[relative] = parts[0].lower()
    return entries


def verify_manifest(manifest: Path, base: Path) -> dict[str, Any]:
    errors: list[str] = []
    checked = 0
    try:
        entries = parse_sha256sums(manifest)
    except (OSError, ValueError) as exc:
        return {"status": "FAIL", "errors": [str(exc)], "checked": 0}
    base_resolved = base.resolve()
    for relative, expected in entries.items():
        candidate = (base / relative).resolve()
        try:
            candidate.relative_to(base_resolved)
        except ValueError:
            errors.append(f"manifest path escapes base: {relative}")
            continue
        if not candidate.is_file():
            errors.append(f"missing: {relative}")
            continue
        actual = sha256_file(candidate)
        checked += 1
        if actual != expected:
            errors.append(f"checksum mismatch: {relative}")
    return {"status": "FAIL" if errors else "PASS", "checked": checked, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--strict-names", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--base", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results: dict[str, Any] = {"archives": []}
    for path in args.paths:
        if not path.is_file():
            results["archives"].append({"path": str(path), "status": "FAIL", "errors": ["file not found"]})
        elif not zipfile.is_zipfile(path):
            results["archives"].append(
                {"path": str(path), "status": "PASS", "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
            )
        else:
            results["archives"].append(inspect_zip(path, strict_names=args.strict_names))
    if args.manifest:
        results["manifest"] = verify_manifest(args.manifest, args.base)
    results["status"] = "PASS"
    for row in results["archives"]:
        if row.get("status") == "FAIL":
            results["status"] = "FAIL"
    if results.get("manifest", {}).get("status") == "FAIL":
        results["status"] = "FAIL"
    payload = json.dumps(results, indent=2, sort_keys=True)
    if args.output:
        if args.output.exists():
            raise SystemExit(f"refusing to overwrite existing evidence: {args.output}")
        args.output.write_text(payload + os.linesep, encoding="utf-8")
    print(payload)
    return 0 if results["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
