#!/usr/bin/env python3
"""Penta proprietary-software assurance gate.

This is an operational repository control, not a legal-rights generator. It
validates CrownThrive's existing root rights notice, detects explicit
incompatible SPDX declarations in first-party protected source, and prevents
secret/vault/private-key material from entering a release package.

The gate is dependency-free and emits a deterministic SHA-256 receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


class GateError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot load JSON policy {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError("policy root must be an object")
    return value


def under_any(path: str, roots: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return any(normalized == root.rstrip("/") or normalized.startswith(root) for root in roots)


def iter_source_files(root: Path, policy: dict[str, Any]) -> Iterable[Path]:
    extensions = set(policy.get("source_extensions", []))
    allowlist = policy.get("third_party_allowlist_roots", [])
    seen: set[Path] = set()
    for rel_root in policy.get("protected_roots", []):
        base = root / rel_root
        if not base.exists():
            continue
        if base.is_file():
            candidates = [base]
        else:
            candidates = base.rglob("*")
        for path in candidates:
            if not path.is_file() or path.is_symlink() or path in seen:
                continue
            rel = path.relative_to(root).as_posix()
            if under_any(rel, allowlist):
                continue
            if path.suffix.lower() not in extensions:
                continue
            seen.add(path)
            yield path


def check_license(root: Path, policy: dict[str, Any]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    license_path = root / policy.get("license_file", "LICENSE")
    try:
        text = license_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [{"code": "LICENSE_MISSING", "path": str(license_path), "detail": str(exc)}]
    for required in policy.get("required_license_strings", []):
        if required not in text:
            violations.append(
                {
                    "code": "LICENSE_REQUIRED_STRING_MISSING",
                    "path": license_path.relative_to(root).as_posix(),
                    "detail": required,
                }
            )
    return violations


def check_first_party_spdx(root: Path, policy: dict[str, Any]) -> tuple[list[dict[str, str]], int]:
    prohibited = set(policy.get("incompatible_first_party_spdx_identifiers", []))
    pattern = re.compile(r"SPDX-License-Identifier:\s*([^\s*]+)", re.IGNORECASE)
    violations: list[dict[str, str]] = []
    scanned = 0
    for path in iter_source_files(root, policy):
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:65536]
        except OSError as exc:
            violations.append(
                {
                    "code": "SOURCE_UNREADABLE",
                    "path": path.relative_to(root).as_posix(),
                    "detail": str(exc),
                }
            )
            continue
        for match in pattern.finditer(text):
            identifier = match.group(1).strip()
            if identifier in prohibited:
                violations.append(
                    {
                        "code": "INCOMPATIBLE_FIRST_PARTY_SPDX",
                        "path": path.relative_to(root).as_posix(),
                        "detail": identifier,
                    }
                )
    return violations, scanned


def check_release(root: Path, release_root: Path, policy: dict[str, Any]) -> tuple[list[dict[str, str]], int, str]:
    violations: list[dict[str, str]] = []
    if not release_root.exists() or not release_root.is_dir():
        return ([{"code": "RELEASE_ROOT_MISSING", "path": str(release_root), "detail": "release root must exist"}], 0, "")

    path_patterns = [re.compile(p, re.IGNORECASE) for p in policy.get("release_prohibited_path_patterns", [])]
    content_patterns = [re.compile(p) for p in policy.get("release_prohibited_content_patterns", [])]
    entries: list[tuple[str, str]] = []
    scanned = 0

    for path in sorted(release_root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        scanned += 1
        rel = path.relative_to(release_root).as_posix()
        for pattern in path_patterns:
            if pattern.search(rel):
                violations.append({"code": "PROHIBITED_RELEASE_PATH", "path": rel, "detail": pattern.pattern})
        try:
            data = path.read_bytes()
        except OSError as exc:
            violations.append({"code": "RELEASE_FILE_UNREADABLE", "path": rel, "detail": str(exc)})
            continue
        digest = hashlib.sha256(data).hexdigest()
        entries.append((rel, digest))
        if len(data) <= 2_000_000:
            text = data.decode("utf-8", errors="ignore")
            for pattern in content_patterns:
                if pattern.search(text):
                    violations.append({"code": "PROHIBITED_RELEASE_CONTENT", "path": rel, "detail": pattern.pattern})

    manifest_material = "\n".join(f"{path}\t{digest}" for path, digest in entries).encode("utf-8")
    release_tree_sha256 = hashlib.sha256(manifest_material).hexdigest()
    return violations, scanned, release_tree_sha256


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def run(root: Path, policy_path: Path, release_root: Path | None = None) -> dict[str, Any]:
    policy = load_json(policy_path)
    if policy.get("mode") != "fail_closed":
        raise GateError("proprietary policy mode must be fail_closed")

    violations = check_license(root, policy)
    spdx_violations, source_count = check_first_party_spdx(root, policy)
    violations.extend(spdx_violations)

    release_count = 0
    release_tree_sha256 = None
    if release_root is not None:
        release_violations, release_count, release_tree_sha256 = check_release(root, release_root, policy)
        violations.extend(release_violations)

    violations = sorted(violations, key=lambda x: (x["code"], x["path"], x["detail"]))
    status = "PASS" if not violations else "HOLD"
    receipt: dict[str, Any] = {
        "schema": "crownthrive.penta.proprietary-assurance-receipt/v1",
        "policy_id": policy.get("policy_id"),
        "policy_schema_version": policy.get("schema_version"),
        "owner": policy.get("owner"),
        "status": status,
        "checks": {
            "root_license": "PASS" if not any(v["code"].startswith("LICENSE_") for v in violations) else "HOLD",
            "first_party_spdx": "PASS" if not any(v["code"] in {"INCOMPATIBLE_FIRST_PARTY_SPDX", "SOURCE_UNREADABLE"} for v in violations) else "HOLD",
            "release_package": None if release_root is None else ("PASS" if not any(v["code"].startswith("PROHIBITED_RELEASE_") or v["code"].startswith("RELEASE_") for v in violations) else "HOLD"),
        },
        "counts": {
            "first_party_source_files_scanned": source_count,
            "release_files_scanned": release_count,
            "violations": len(violations),
        },
        "release_tree_sha256": release_tree_sha256,
        "violations": violations,
        "authority_invariant": "Repository/software controls may enforce declared policy but do not manufacture intellectual-property rights, legal conclusions, provider authority, or third-party license rights.",
    }
    receipt["receipt_sha256"] = hashlib.sha256(canonical_bytes(receipt)).hexdigest()
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="data/penta/proprietary-software-policy.json")
    parser.add_argument("--release-root")
    parser.add_argument("--receipt")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    release_root = Path(args.release_root).resolve() if args.release_root else None

    try:
        receipt = run(root, policy_path, release_root)
    except GateError as exc:
        print(f"PentaProprietary HOLD: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.receipt:
        output = Path(args.receipt)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
