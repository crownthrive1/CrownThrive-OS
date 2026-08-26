#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from penta_proprietary_gate import run  # noqa: E402


BASE_POLICY = {
    "schema_version": "1.0.0",
    "policy_id": "test.proprietary",
    "owner": "CrownThrive LLC",
    "mode": "fail_closed",
    "license_file": "LICENSE",
    "required_license_strings": ["All Rights Reserved", "Technical ability is not permission."],
    "protected_roots": ["src/"],
    "source_extensions": [".py"],
    "third_party_allowlist_roots": ["third_party/"],
    "incompatible_first_party_spdx_identifiers": ["MIT", "Apache-2.0"],
    "release_prohibited_path_patterns": ["(^|/)vault($|/)", "\\.pem$"],
    "release_prohibited_content_patterns": ["-----BEGIN PRIVATE KEY-----"],
}


def setup_tree(tmp: Path) -> Path:
    (tmp / "src").mkdir()
    (tmp / "src" / "runtime.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp / "LICENSE").write_text(
        "All Rights Reserved\nTechnical ability is not permission.\n", encoding="utf-8"
    )
    policy_path = tmp / "policy.json"
    policy_path.write_text(json.dumps(BASE_POLICY), encoding="utf-8")
    return policy_path


def test_clean_repository_passes_and_receipt_is_deterministic() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        policy = setup_tree(root)
        first = run(root, policy)
        second = run(root, policy)
        assert first["status"] == "PASS"
        assert first["receipt_sha256"] == second["receipt_sha256"]
        assert first["counts"]["first_party_source_files_scanned"] == 1


def test_missing_required_license_text_holds() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        policy = setup_tree(root)
        (root / "LICENSE").write_text("All Rights Reserved\n", encoding="utf-8")
        receipt = run(root, policy)
        assert receipt["status"] == "HOLD"
        assert any(v["code"] == "LICENSE_REQUIRED_STRING_MISSING" for v in receipt["violations"])


def test_incompatible_first_party_spdx_holds() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        policy = setup_tree(root)
        (root / "src" / "runtime.py").write_text(
            "# SPDX-License-Identifier: MIT\nprint('ok')\n", encoding="utf-8"
        )
        receipt = run(root, policy)
        assert receipt["status"] == "HOLD"
        assert any(v["code"] == "INCOMPATIBLE_FIRST_PARTY_SPDX" for v in receipt["violations"])


def test_release_vault_path_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        policy = setup_tree(root)
        release = root / "release"
        (release / "vault").mkdir(parents=True)
        (release / "vault" / "receipt.json").write_text("{}\n", encoding="utf-8")
        receipt = run(root, policy, release)
        assert receipt["status"] == "HOLD"
        assert any(v["code"] == "PROHIBITED_RELEASE_PATH" for v in receipt["violations"])


def test_release_private_key_content_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        policy = setup_tree(root)
        release = root / "release"
        release.mkdir()
        (release / "notes.txt").write_text(
            "-----BEGIN PRIVATE KEY-----\nnot-a-real-key\n", encoding="utf-8"
        )
        receipt = run(root, policy, release)
        assert receipt["status"] == "HOLD"
        assert any(v["code"] == "PROHIBITED_RELEASE_CONTENT" for v in receipt["violations"])


def run_tests() -> None:
    tests = [
        test_clean_repository_passes_and_receipt_is_deterministic,
        test_missing_required_license_text_holds,
        test_incompatible_first_party_spdx_holds,
        test_release_vault_path_is_blocked,
        test_release_private_key_content_is_blocked,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    run_tests()
