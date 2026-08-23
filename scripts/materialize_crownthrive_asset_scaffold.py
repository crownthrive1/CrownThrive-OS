#!/usr/bin/env python3
"""Materialize one public-safe CrownThrive asset scaffold from a blueprint.

This command creates a source-controlled scaffold only. It does not execute the
asset, install a plugin, call providers, read secrets, enable commerce, or claim
independent certification.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts/generate_crownthrive_asset_blueprints.py"
DEFAULT_CATALOG = ROOT / "developers/manifests/crownthrive-asset-blueprint-catalog.v1.json"
SAFE_COMPONENT = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


def load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("asset_blueprint_generator", GENERATOR)
    if spec is None or spec.loader is None:
        raise ValueError("Unable to load blueprint generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_output_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    cwd = Path.cwd().resolve()
    if resolved in {Path("/"), Path.home().resolve(), ROOT.resolve()}:
        raise ValueError(f"Unsafe output directory: {resolved}")
    if resolved.exists() and resolved.is_file():
        raise ValueError(f"Output path is a file: {resolved}")
    if os.path.commonpath([str(resolved), str(cwd)]) != str(cwd) and "/tmp/" not in f"{resolved}/":
        raise ValueError("Output must be under the current working directory or /tmp")
    return resolved


def choose_blueprint(blueprints: list[dict[str, Any]], blueprint_id: str) -> dict[str, Any]:
    if not SAFE_COMPONENT.fullmatch(blueprint_id.replace(":", "-")):
        raise ValueError("Blueprint ID contains unsafe characters")
    matches = [item for item in blueprints if item["blueprint_id"] == blueprint_id]
    if not matches:
        raise ValueError(f"Blueprint not found: {blueprint_id}")
    return matches[0]


def source_stub(blueprint: dict[str, Any]) -> tuple[str, str]:
    asset_class = str(blueprint["asset_class"])
    asset_id = str(blueprint["blueprint_id"])
    if asset_class == "script":
        return (
            "src/main.py",
            """#!/usr/bin/env python3
\"\"\"Controlled-test CrownThrive asset scaffold.

This module performs no provider call, filesystem mutation, secret retrieval,
or arbitrary command execution. Replace the describe-only contract through a
reviewed successor version and independent verification.
\"\"\"

from __future__ import annotations

import json


def describe() -> dict[str, object]:
    return {
        \"asset_state\": \"scaffold_only\",
        \"provider_write_performed\": False,
        \"secret_accessed\": False,
        \"D3_auto\": False,
        \"sovereign_vote_effect\": False,
    }


if __name__ == \"__main__\":
    print(json.dumps(describe(), sort_keys=True))
""",
        )
    if asset_class == "workflow":
        return (
            "workflow.candidate.yml",
            """name: CrownThrive Asset Scaffold Candidate

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  describe-only:
    runs-on: ubuntu-latest
    steps:
      - name: Refuse execution until a successor workflow is independently verified
        run: |
          echo \"scaffold_only=true\"
          echo \"provider_write_performed=false\"
          echo \"D3_auto=false\"
""",
        )
    if asset_class == "widget":
        return (
            "widget/index.html",
            """<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>CrownThrive Asset Scaffold</title></head>
<body><main><h1>CrownThrive asset scaffold</h1><p role=\"status\" aria-live=\"polite\">Candidate only. No protected data, direct network call, installation or publication.</p></main></body></html>
""",
        )
    if asset_class in {"plugin", "adapter", "commerce_pack", "security_pack", "observability_pack", "continuity_pack"}:
        return (
            "src/contract.json",
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "source_blueprint_id": asset_id,
                    "state": "scaffold_only",
                    "provider_write_enabled": False,
                    "arbitrary_command_execution": False,
                    "secret_export": False,
                    "private_identity_export": False,
                    "D3_auto": False,
                    "sovereign_vote_effect": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
    return (
        "src/README.md",
        f"""# {blueprint['canonical_name']}

This source directory is a controlled-test scaffold generated from `{asset_id}`.
It contains no operative implementation, credential, protected kernel body,
provider write, installation, publication, checkout, entitlement or D3 authority.
""",
    )


def build_package(blueprint: dict[str, Any], package_id: str) -> dict[str, str]:
    if not SAFE_COMPONENT.fullmatch(package_id):
        raise ValueError("Package ID must use lowercase letters, digits, dots, dashes or underscores")

    source_path, source_text = source_stub(blueprint)
    source_digest = sha256_bytes(source_text.encode("utf-8"))
    manifest = {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "package_version": "0.1.0",
        "source_blueprint_id": blueprint["blueprint_id"],
        "blueprint_sha256": blueprint["blueprint_sha256"],
        "public_contract_digest": blueprint["public_contract_digest"],
        "asset_class": blueprint["asset_class"],
        "domain_id": blueprint["domain_id"],
        "profile_id": blueprint["profile_id"],
        "state": "scaffold_only",
        "source_materialized": True,
        "source_ref": source_path,
        "source_sha256": source_digest,
        "independently_verified": False,
        "installed": False,
        "submitted": False,
        "published": False,
        "checkout_enabled": False,
        "entitlement_active": False,
        "provider_write_enabled": False,
        "arbitrary_command_execution": False,
        "opaque_native_binary_generation": False,
        "D3_auto": False,
        "sovereign_vote_effect": False,
        "required_tests": blueprint["required_tests"],
        "required_kernels": blueprint["required_kernels"],
        "history_policy": "append_or_supersede_never_silent_delete",
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json(manifest).encode("utf-8"))

    readme = f"""# {blueprint['canonical_name']}

**Package ID:** `{package_id}`  
**Version:** `0.1.0`  
**State:** scaffold only / not independently verified

Generated from `{blueprint['blueprint_id']}`.

This package is source materialization evidence only. It is not installed,
submitted, published or production certified. Provider writes, secret access,
checkout, entitlements, D3 automation and sovereign-vote effects are disabled.

## Required tests

{chr(10).join(f'- `{test}`' for test in blueprint['required_tests'])}

## Required kernels

{chr(10).join(f'- `{kernel}`' for kernel in blueprint['required_kernels'])}
"""

    verification = {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "package_version": "0.1.0",
        "verification_state": "pending",
        "owner_agent_id": "ct.asset.agent-compiler",
        "verifier_agent_id": "ct.asset.agent-independent-certifier",
        "owner_can_self_verify": False,
        "required_tests": blueprint["required_tests"],
        "test_receipts": [],
        "blockers": ["independent_test_receipts_missing", "package_certification_missing"],
    }

    return {
        "asset.manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        "README.md": readme,
        source_path: source_text,
        "verification.candidate.json": json.dumps(verification, indent=2, sort_keys=True) + "\n",
    }


def write_package(output: Path, files: dict[str, str]) -> dict[str, str]:
    digests: dict[str, str] = {}
    for relative, text in files.items():
        target = (output / relative).resolve()
        if os.path.commonpath([str(target), str(output)]) != str(output):
            raise ValueError(f"Package path escaped output directory: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        digests[relative] = sha256_bytes(target.read_bytes())
    return digests


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--blueprint-id", required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        generator = load_generator()
        catalog = generator.load_catalog(args.catalog)
        blueprint = choose_blueprint(generator.generate(catalog), args.blueprint_id)
        output = safe_output_path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        files = build_package(blueprint, args.package_id)
        digests = write_package(output, files)
        summary = {
            "package_id": args.package_id,
            "source_blueprint_id": args.blueprint_id,
            "output": str(output),
            "file_count": len(files),
            "file_digests": digests,
            "execution_performed": False,
            "provider_write_performed": False,
            "independently_verified": False,
            "installed": False,
            "published": False,
            "checkout_enabled": False,
        }
        (output / "materialization-receipt.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"asset-scaffold-materialization-error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
