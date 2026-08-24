#!/usr/bin/env python3
"""Validate and materialize the CHLOM public commercial overlay.

The parent is authoritative for the managed overlay. The builder is intentionally
non-destructive: it writes only manifest-managed files and never deletes child paths.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "developers/manifests/chlom-protocol-commercial-projection.v1.json"
CONTRACT_PATH = ROOT / "developers/contracts/chlom-commercial-projection.contract.v1.json"

SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sb_secret_[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
]

FORBIDDEN_CURRENT_CANON = (
    "DAL = Decentralized Attestation Ledger",
    "DAL = Decentralized Adjudication Layer",
    "DLA = Decentralized Licensing Authority",
)

GENERATED_PATHS = {".crownthrive/upstream.json"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def exact_parent_sha() -> str:
    env_sha = os.environ.get("GITHUB_SHA", "").strip()
    if re.fullmatch(r"[0-9a-f]{40}", env_sha):
        return env_sha
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def validate_manifest(manifest: dict, contract: dict) -> None:
    assert manifest["canonical_parent_repository"] == "crownthrive1/CrownThrive-Support"
    assert manifest["public_commercial_repository"] == "crownthrive/chlom-protocol"
    assert manifest["public_repository_role"] == "commercial_public_projection"
    assert manifest["os_identity"] == "CrownThrive OS"
    assert manifest["canonical_ledger"] == {
        "name": "DAIL",
        "expanded_name": "Decentralized Autonomous Information Ledger",
        "legacy_dal_is_canonical": False,
    }
    assert manifest["licensing_identity"]["DLA"] == "Dynamic Licensing Asset"
    assert manifest["authority"]["direct_main_write"] is False
    assert manifest["authority"]["force_push"] is False
    assert manifest["authority"]["self_merge"] is False
    assert manifest["authority"]["security_bypass"] is False
    assert manifest["security"]["allowlist_only"] is True
    assert manifest["security"]["raw_secret_export"] is False
    assert manifest["projection"]["delete_unmanaged_child_paths"] is False
    assert manifest["projection"]["child_changes_require_pull_request"] is True
    assert contract["parent_repository"] == manifest["canonical_parent_repository"]
    assert contract["child_repository"] == manifest["public_commercial_repository"]
    assert contract["source_authority"] == "parent"
    assert contract["rules"]["child_direct_main_write"] is False
    assert contract["rules"]["child_force_push"] is False
    assert contract["rules"]["secret_scan_required"] is True


def source_files(manifest: dict) -> list[tuple[str, Path]]:
    source_root = ROOT / manifest["projection"]["source_root"]
    managed = manifest["projection"]["managed_paths"]
    assert managed == list(dict.fromkeys(managed)), "managed paths must be unique"
    files: list[tuple[str, Path]] = []
    for rel in managed:
        if rel in GENERATED_PATHS:
            continue
        candidate = (source_root / rel).resolve()
        assert source_root.resolve() in candidate.parents, f"managed path escapes source root: {rel}"
        assert candidate.is_file(), f"missing public-safe source: {rel}"
        files.append((rel, candidate))
    return files


def validate_public_text(files: list[tuple[str, Path]]) -> None:
    for rel, path in files:
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            assert not pattern.search(text), f"credential-shaped material in {rel}"
        for phrase in FORBIDDEN_CURRENT_CANON:
            assert phrase not in text, f"legacy term asserted as current canon in {rel}: {phrase}"
        assert "CONFIDENTIAL_INTERNAL" not in text, f"internal marker in {rel}"
        assert "TRADE_SECRET_BODY" not in text, f"trade-secret marker in {rel}"


def write_dist(manifest: dict, files: list[tuple[str, Path]]) -> Path:
    dist_root = ROOT / manifest["projection"]["dist_root"]
    if dist_root.exists():
        shutil.rmtree(dist_root)
    dist_root.mkdir(parents=True, exist_ok=True)
    for rel, src in files:
        dst = dist_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    provenance = {
        "schema_version": manifest["schema_version"],
        "product_id": manifest["product_id"],
        "canonical_parent_repository": manifest["canonical_parent_repository"],
        "upstream_parent_sha": exact_parent_sha(),
        "public_commercial_repository": manifest["public_commercial_repository"],
        "repository_role": manifest["public_repository_role"],
        "os_identity": manifest["os_identity"],
        "canonical_ledger": manifest["canonical_ledger"],
        "DLA": manifest["licensing_identity"]["DLA"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authority_mode": manifest["authority"]["recorded_mode"],
        "founder": manifest["authority"]["founder"],
        "receipt_is_certification": False,
    }
    receipt = dist_root / ".crownthrive/upstream.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return dist_root


def check_dist(manifest: dict, dist_root: Path) -> None:
    expected = set(manifest["projection"]["managed_paths"])
    actual = {
        path.relative_to(dist_root).as_posix()
        for path in dist_root.rglob("*")
        if path.is_file()
    }
    assert actual == expected, f"dist path mismatch: expected={sorted(expected)} actual={sorted(actual)}"
    receipt = load_json(dist_root / ".crownthrive/upstream.json")
    assert re.fullmatch(r"[0-9a-f]{40}", receipt["upstream_parent_sha"])
    assert receipt["canonical_ledger"]["name"] == "DAIL"
    assert receipt["DLA"] == "Dynamic Licensing Asset"
    assert receipt["receipt_is_certification"] is False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="materialize dist/chlom-protocol")
    parser.add_argument("--check-dist", action="store_true", help="validate materialized output")
    args = parser.parse_args()

    manifest = load_json(MANIFEST_PATH)
    contract = load_json(CONTRACT_PATH)
    validate_manifest(manifest, contract)
    files = source_files(manifest)
    validate_public_text(files)

    dist_root = ROOT / manifest["projection"]["dist_root"]
    if args.write:
        dist_root = write_dist(manifest, files)
    if args.check_dist:
        assert dist_root.is_dir(), "dist root not materialized"
        check_dist(manifest, dist_root)

    print("PASS_CHLOM_COMMERCIAL_PROJECTION")


if __name__ == "__main__":
    main()
