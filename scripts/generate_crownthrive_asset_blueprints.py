#!/usr/bin/env python3
"""Generate governed CrownThrive Institutional Asset Fabric blueprints.

The generator creates candidate blueprint records only. It does not execute code,
install plugins, call providers, expose secrets, enable checkout, or certify the
result. Output is deterministic for an exact catalog and blueprint version.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "developers/manifests/crownthrive-asset-blueprint-catalog.v1.json"
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_catalog(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Catalog not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON catalog: {path}: {exc}") from exc

    for key in ("domains", "archetypes", "deployment_profiles"):
        if not isinstance(data.get(key), list) or not data[key]:
            raise ValueError(f"Catalog field {key!r} must be a non-empty list")
    return data


def validate_ids(items: Iterable[dict[str, Any]], label: str) -> None:
    seen: set[str] = set()
    for item in items:
        value = item.get("id")
        if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
            raise ValueError(f"Invalid {label} ID: {value!r}")
        if value in seen:
            raise ValueError(f"Duplicate {label} ID: {value}")
        seen.add(value)


def required_tests(archetype: dict[str, Any]) -> list[str]:
    asset_class = str(archetype["class"])
    if asset_class == "widget":
        return ["schema", "integrity", "security", "privacy", "accessibility"]
    if asset_class == "license_pack":
        return ["integrity", "license", "security"]
    if bool(archetype.get("executable")):
        return [
            "schema",
            "integrity",
            "dependency",
            "negative",
            "security",
            "privacy",
            "idempotency",
            "rollback",
            "readback",
        ]
    return ["schema", "integrity", "dependency", "security", "privacy"]


def classification(archetype: dict[str, Any], profile: dict[str, Any]) -> str:
    asset_class = str(archetype["class"])
    if asset_class == "kernel":
        return "PUBLIC_CONTRACT_RESTRICTED_IMPLEMENTATION"
    if bool(profile.get("public_safe")):
        return "PUBLIC_SAFE"
    if asset_class in {"script", "workflow", "adapter", "security_pack", "commerce_pack"}:
        return "RESTRICTED_INSTITUTIONAL"
    return "PUBLIC_CONTRACT_RESTRICTED_IMPLEMENTATION"


def authority(archetype: dict[str, Any], profile: dict[str, Any]) -> str:
    return "D1" if profile.get("maximum_authority") == "D1" else str(archetype["authority"])


def make_blueprint(
    catalog: dict[str, Any],
    domain: dict[str, Any],
    archetype: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    version = str(catalog.get("blueprint_version", "0.1.0"))
    generation = int(catalog.get("generation", 7))
    blueprint_id = f"ct.blueprint.{domain['id']}.{archetype['id']}.{profile['id']}.v1"
    contract_seed = f"public-contract|{domain['id']}|{archetype['id']}|{profile['id']}|{version}"
    blueprint_seed = f"blueprint|{domain['id']}|{archetype['id']}|{profile['id']}|{version}|gen{generation}"

    manifest = {
        "schema_version": "1.0.0",
        "blueprint_id": blueprint_id,
        "domain_id": domain["id"],
        "archetype_id": archetype["id"],
        "profile_id": profile["id"],
        "generation": generation,
        "state": "candidate",
        "candidate_blueprint_not_production_asset": True,
        "source_materialized": False,
        "installed": False,
        "submitted": False,
        "published": False,
        "checkout_enabled": False,
        "entitlement_active": False,
        "arbitrary_code_allowed": False,
        "opaque_native_binary_generation": False,
        "provider_write_inherited": False,
        "D3_auto": False,
        "sovereign_vote_effect": False,
        "history_policy": "append_or_supersede_never_silent_delete",
    }

    return {
        "blueprint_id": blueprint_id,
        "canonical_name": f"{domain['name']} — {archetype['class']} — {profile['class']}",
        "domain_id": domain["id"],
        "domain_name": domain["name"],
        "corridor": domain["corridor"],
        "archetype_id": archetype["id"],
        "asset_class": archetype["class"],
        "profile_id": profile["id"],
        "deployment_class": profile["class"],
        "blueprint_version": version,
        "generation": generation,
        "lifecycle_state": "candidate",
        "classification": classification(archetype, profile),
        "authority_class": authority(archetype, profile),
        "executable_class": bool(archetype.get("executable")),
        "required_tests": required_tests(archetype),
        "required_kernels": [
            "ct.kernel.asset.classification",
            "ct.kernel.asset.dependency-resolution",
            "ct.kernel.asset.version-supersession",
            "ct.kernel.asset.security-scrutiny",
        ],
        "public_contract_digest": sha256_text(contract_seed),
        "blueprint_sha256": sha256_text(blueprint_seed),
        "manifest_template": manifest,
        "rights_state": "candidate",
        "monetization_state": "research",
    }


def generate(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    validate_ids(catalog["domains"], "domain")
    validate_ids(catalog["archetypes"], "archetype")
    validate_ids(catalog["deployment_profiles"], "deployment profile")

    result = [
        make_blueprint(catalog, domain, archetype, profile)
        for domain in catalog["domains"]
        for archetype in catalog["archetypes"]
        for profile in catalog["deployment_profiles"]
    ]
    expected = int(catalog.get("expected_matrix_size", len(result)))
    if len(result) != expected:
        raise ValueError(f"Matrix-size mismatch: expected {expected}, generated {len(result)}")
    return result


def safe_output_path(output: Path) -> Path:
    resolved = output.expanduser().resolve()
    cwd = Path.cwd().resolve()
    # Refuse broad or system-level paths. Generation must remain in an explicit
    # working directory or temporary directory controlled by the caller.
    forbidden = {Path("/"), Path.home().resolve(), ROOT.resolve()}
    if resolved in forbidden:
        raise ValueError(f"Unsafe output path: {resolved}")
    if resolved.exists() and resolved.is_file():
        raise ValueError(f"Output path is a file: {resolved}")
    if os.path.commonpath([str(resolved), str(cwd)]) != str(cwd) and "/tmp/" not in f"{resolved}/":
        raise ValueError("Output must be under the current working directory or /tmp")
    return resolved


def write_index(output: Path, blueprints: list[dict[str, Any]], catalog: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    index = output / "blueprints.jsonl"
    summary = output / "generation-summary.json"
    index.write_text("".join(f"{canonical_json(item)}\n" for item in blueprints), encoding="utf-8")
    summary_body = {
        "schema_version": "1.0.0",
        "catalog_id": catalog["catalog_id"],
        "blueprint_count": len(blueprints),
        "index_ref": index.name,
        "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
        "production_assets_claimed": 0,
        "source_execution_performed": False,
        "provider_write_performed": False,
        "installed": False,
        "published": False,
        "checkout_enabled": False,
        "D3_auto": False,
        "sovereign_vote_effect": False,
    }
    summary.write_text(json.dumps(summary_body, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_files(output: Path, blueprints: list[dict[str, Any]], catalog: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for blueprint in blueprints:
        domain_dir = output / str(blueprint["domain_id"])
        domain_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{blueprint['archetype_id']}--{blueprint['profile_id']}.json"
        (domain_dir / filename).write_text(json.dumps(blueprint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_index(output, blueprints, catalog)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, help="Output directory; required unless --check is used")
    parser.add_argument("--mode", choices=("index", "files"), default="index")
    parser.add_argument("--check", action="store_true", help="Validate and print a deterministic summary without writing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        catalog = load_catalog(args.catalog)
        blueprints = generate(catalog)
        aggregate_digest = sha256_text("\n".join(item["blueprint_sha256"] for item in blueprints))
        summary = {
            "catalog_id": catalog["catalog_id"],
            "blueprints": len(blueprints),
            "aggregate_sha256": aggregate_digest,
            "production_assets_claimed": 0,
            "source_execution_performed": False,
            "provider_write_performed": False,
        }
        if args.check:
            print(json.dumps(summary, sort_keys=True))
            return 0
        if args.output is None:
            raise ValueError("--output is required unless --check is used")
        output = safe_output_path(args.output)
        if args.mode == "files":
            write_files(output, blueprints, catalog)
        else:
            write_index(output, blueprints, catalog)
        print(json.dumps({**summary, "output": str(output), "mode": args.mode}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"asset-blueprint-generation-error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
