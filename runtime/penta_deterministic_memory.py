#!/usr/bin/env python3
"""Deterministic memory allocator, census projector, and replay receipt kernel.

This module is standard-library only so the deterministic survival footprint can
run in CI, recovery shells, cold routes, and operator environments without an LLM.
Memory is durable governed state, not hidden model context and not authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path("config/penta_deterministic_memory.v1.json")
OS_REGISTRY_PATH = Path("data/penta/os-v1.registry.json")
NAMESPACE_CENSUS_PATH = Path("data/penta/namespace-census.v1.json")
FAMILY_REGISTRY_PATH = Path("penta/registry/penta-families.v1.json")
DEFAULT_OUTPUT_PATH = Path("data/penta/deterministic-memory-census.v1.json")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
HOT_MATURITY = {"implemented", "production"}


class DeterministicMemoryError(ValueError):
    """Fail-closed configuration, classification, or integrity error."""


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DeterministicMemoryError(f"required source missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DeterministicMemoryError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DeterministicMemoryError(f"expected JSON object: {path}")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Canonical JSON used by the repository runtime.

    JSON object keys are sorted, separators are compact, UTF-8 is preserved, and
    all strings are NFC-normalized. Callers must sort semantically unordered lists
    before passing them here.
    """
    def normalize(item: Any) -> Any:
        if isinstance(item, str):
            return unicodedata.normalize("NFC", item)
        if isinstance(item, dict):
            return {str(key): normalize(child) for key, child in item.items()}
        if isinstance(item, list):
            return [normalize(child) for child in item]
        if item is None or isinstance(item, (bool, int, float)):
            return item
        raise DeterministicMemoryError(f"unsupported canonical JSON type: {type(item).__name__}")

    return json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def normalized_family(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


def namespace_for(machine_key: str) -> str:
    if not re.fullmatch(r"penta\.[a-z0-9]+(?:[-_.][a-z0-9]+)*", machine_key):
        raise DeterministicMemoryError(f"invalid Penta machine key: {machine_key}")
    return f"ct.memory.{machine_key}.v1"


def _family_from_census(census: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in census.get("records", []):
        if not isinstance(row, dict):
            continue
        key = row.get("canonical_machine_key")
        family = row.get("family_id") or row.get("family_slug")
        if isinstance(key, str) and key.startswith("penta.") and isinstance(family, str) and family.strip():
            current = normalized_family(family)
            previous = result.get(key)
            if previous and previous != current:
                raise DeterministicMemoryError(f"conflicting census family assignment for {key}: {previous} vs {current}")
            result[key] = current
    return result


def _family_from_explicit_members(registry: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for family in registry.get("families", []):
        if not isinstance(family, dict):
            continue
        family_key = normalized_family(str(family.get("family_id") or family.get("slug") or ""))
        for name in family.get("explicit_members", []):
            if not isinstance(name, str) or not name.strip():
                continue
            folded = re.sub(r"[^a-z0-9]", "", name.casefold())
            previous = result.get(folded)
            if previous and previous != family_key:
                raise DeterministicMemoryError(f"explicit family collision for {name}: {previous} vs {family_key}")
            result[folded] = family_key
    return result


def _canonical_members(os_registry: dict[str, Any]) -> list[dict[str, Any]]:
    systems = os_registry.get("systems")
    if not isinstance(systems, list) or not systems:
        raise DeterministicMemoryError("OS registry systems must be a non-empty list")
    members: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(systems):
        if not isinstance(row, dict):
            raise DeterministicMemoryError(f"systems[{index}] must be an object")
        key = row.get("machine_key")
        name = row.get("canonical_name")
        if not isinstance(key, str) or not key.startswith("penta."):
            raise DeterministicMemoryError(f"systems[{index}] has invalid machine_key")
        if not isinstance(name, str) or not name.strip():
            raise DeterministicMemoryError(f"{key} has invalid canonical_name")
        if key in seen:
            raise DeterministicMemoryError(f"duplicate machine_key: {key}")
        seen.add(key)
        members.append(row)
    return sorted(members, key=lambda item: item["machine_key"])


def _profile_for(
    *,
    machine_key: str,
    family_key: str,
    maturity: str,
    config: dict[str, Any],
) -> tuple[str, dict[str, Any], bool]:
    overrides = config.get("overrides", {})
    override = overrides.get(machine_key, {}) if isinstance(overrides, dict) else {}
    hot = maturity.casefold() in set(config["maturity_policy"]["hot_writable"])

    if override:
        profile_id = str(override["profile"])
    elif not hot:
        profile_id = "cold-reserved-v1"
    else:
        if family_key not in config["family_profile_map"]:
            raise DeterministicMemoryError(
                f"{machine_key} has no governed family memory profile: {family_key}"
            )
        profile_id = config["family_profile_map"][family_key]

    profiles = config.get("memory_profiles", {})
    if profile_id not in profiles:
        raise DeterministicMemoryError(f"{machine_key} resolves unknown memory profile: {profile_id}")
    profile = copy.deepcopy(profiles[profile_id])
    write_enabled = bool(profile.get("write_enabled", False)) and hot
    if "write_enabled" in override:
        write_enabled = bool(override["write_enabled"]) and hot
    return profile_id, profile, write_enabled


def build_manifest(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    config_path = root / CONFIG_PATH
    os_path = root / OS_REGISTRY_PATH
    census_path = root / NAMESPACE_CENSUS_PATH
    family_path = root / FAMILY_REGISTRY_PATH

    config = load_object(config_path)
    os_registry = load_object(os_path)
    census = load_object(census_path)
    family_registry = load_object(family_path)
    members = _canonical_members(os_registry)
    census_family = _family_from_census(census)
    explicit_family = _family_from_explicit_members(family_registry)

    source_digests = {
        CONFIG_PATH.as_posix(): sha256_hex(config_path.read_bytes()),
        OS_REGISTRY_PATH.as_posix(): sha256_hex(os_path.read_bytes()),
        NAMESPACE_CENSUS_PATH.as_posix(): sha256_hex(census_path.read_bytes()),
        FAMILY_REGISTRY_PATH.as_posix(): sha256_hex(family_path.read_bytes()),
    }
    semantic_families = {normalized_family(value) for value in config["semantic_families"]}
    support_families = {
        normalized_family(key): value
        for key, value in config["brain_mesh"]["support_families"].items()
    }
    assignments: list[dict[str, Any]] = []
    unresolved: list[str] = []

    for member in members:
        key = member["machine_key"]
        name = member["canonical_name"]
        name_norm = re.sub(r"[^a-z0-9]", "", name.casefold())
        family = normalized_family(
            member.get("family_key")
            or member.get("family_id")
            or census_family.get(key)
            or explicit_family.get(name_norm)
        )
        if not family:
            unresolved.append(key)
            continue

        maturity = str(member.get("maturity") or "unknown").casefold()
        if maturity == "unknown":
            raise DeterministicMemoryError(f"{key} has no governed maturity")
        risk = str(member.get("risk_ceiling") or "D0").upper()
        profile_id, profile, write_enabled = _profile_for(
            machine_key=key,
            family_key=family,
            maturity=maturity,
            config=config,
        )
        override = config.get("overrides", {}).get(key, {})
        semantic = family in semantic_families
        determinism_profile = str(
            override.get("semantic_determinism")
            or ("bounded-semantic-v1" if semantic else "strict-v1")
        )
        if determinism_profile not in config["determinism_profiles"]:
            raise DeterministicMemoryError(
                f"{key} resolves unknown semantic determinism profile: {determinism_profile}"
            )
        semantic = determinism_profile == "bounded-semantic-v1"
        activation_state = (
            str(override.get("activation_state"))
            if override.get("activation_state")
            else ("ACTIVE_FAIL_CLOSED" if maturity in HOT_MATURITY else "COLD_RESERVED")
        )
        model_dependency = str(
            override.get("model_dependency")
            or ("optional_replaceable" if semantic else "none")
        )
        degraded_without_model = bool(
            override.get("degraded_without_model", semantic)
        )
        warrant = str(
            override.get("determinism_warrant")
            or (
                "Identity, routing, authorization inputs, state transitions, retries, "
                "receipts, and recovery must replay exactly. Semantic model output, when "
                "used, is bounded by a pinned provider/model contract and independently "
                "verified before consequential release."
                if semantic
                else
                "Identity, inputs, state transitions, routing, retries, evidence, and "
                "recovery must replay exactly for identical canonical input and contract version."
            )
        )
        survival = {
            "contract_id": config["survival_contract"]["contract_id"],
            "persistent_identity": key,
            "persistent_state": namespace_for(key),
            "deterministic_functions": [
                "canonical_input_hash",
                "deterministic_request_key",
                "hash_bound_receipt",
                "replay_verification",
            ],
            "queues": "governed_existing_penta_queue",
            "leases": "bounded_expiring_owner_scoped",
            "recovery": "verified_checkpoint_then_exact_source_replay",
            "evidence": "hash_bound_receipt_plus_DAIL_handoff",
            "authority_enforcement": "CHLOM_provider_human_independent_certifier",
            "health_check": "quota_chain_family_provider_readback",
            "model_dependency": model_dependency,
            "degraded_without_model": degraded_without_model,
            "replaceable_model": True,
            "restart_behavior": "rebuild_from_verified_persistent_state",
        }
        assignment = {
            "machine_key": key,
            "canonical_name": name,
            "kind": member.get("kind"),
            "family_key": family,
            "maturity": maturity,
            "risk_ceiling": risk,
            "execution_eligible_by_registry": bool(member.get("execution_eligible_by_registry", False)),
            "activation_state": activation_state,
            "memory_namespace": namespace_for(key),
            "memory_profile": profile_id,
            "hard_quota_bytes": int(profile["hard_quota_bytes"]),
            "working_set_bytes": int(profile["working_set_bytes"]),
            "retention_days": int(profile["retention_days"]),
            "classification_ceiling": profile["classification_ceiling"],
            "write_enabled": write_enabled,
            "orchestration_determinism": "strict-v1",
            "semantic_determinism": determinism_profile,
            "seed": 0,
            "temperature": 0,
            "provider_version_required": True,
            "model_version_required": semantic,
            "fail_closed": True,
            "model_dependency": model_dependency,
            "degraded_without_model": degraded_without_model,
            "replaceable_model": True,
            "determinism_warrant": warrant,
            "brain_mesh_role": (
                "anchor" if key == config["brain_mesh"]["anchor"]
                else support_families.get(family)
            ),
            "survival_contract": survival,
        }
        assignments.append(assignment)

    if unresolved:
        raise DeterministicMemoryError(
            "unclassified canonical Pentas fail closed: " + ", ".join(sorted(unresolved))
        )

    assignments.sort(key=lambda item: item["machine_key"])
    expected_total = os_registry.get("counts", {}).get("total")
    if isinstance(expected_total, int) and expected_total != len(assignments):
        raise DeterministicMemoryError(
            f"registry count mismatch: declared={expected_total} allocated={len(assignments)}"
        )

    manifest: dict[str, Any] = {
        "schema": "ct.penta.deterministic-memory-census.v1",
        "version": config["version"],
        "effective_date": config["effective_date"],
        "status": "governed_production_contract",
        "authority_invariant": config["authority_invariant"],
        "source_registry_id": os_registry.get("registry_id"),
        "source_registry_version": os_registry.get("version"),
        "source_digests_sha256": dict(sorted(source_digests.items())),
        "canonicalization_profile": config["canonicalization"]["profile"],
        "production_database": config["production_database"],
        "brain_mesh": config["brain_mesh"],
        "counts": {
            "canonical_pentas": len(assignments),
            "hot_writable": sum(1 for row in assignments if row["write_enabled"]),
            "cold_reserved": sum(1 for row in assignments if not row["write_enabled"]),
            "semantic_bounded": sum(1 for row in assignments if row["semantic_determinism"] == "bounded-semantic-v1"),
            "strict_only": sum(1 for row in assignments if row["semantic_determinism"] == "strict-v1"),
            "families": len({row["family_key"] for row in assignments}),
        },
        "assignments": assignments,
    }
    manifest["manifest_sha256"] = sha256_hex(canonical_json_bytes(manifest))
    validate_manifest(manifest, config=config)
    return manifest


def validate_manifest(manifest: dict[str, Any], *, config: dict[str, Any] | None = None) -> None:
    if config is None:
        config = load_object(ROOT / CONFIG_PATH)
    errors: list[str] = []
    if manifest.get("schema") != "ct.penta.deterministic-memory-census.v1":
        errors.append("unexpected manifest schema")
    supplied_hash = manifest.get("manifest_sha256")
    unhashed = copy.deepcopy(manifest)
    unhashed.pop("manifest_sha256", None)
    expected_hash = sha256_hex(canonical_json_bytes(unhashed))
    if supplied_hash != expected_hash:
        errors.append("manifest_sha256 does not match canonical manifest")

    rows = manifest.get("assignments")
    if not isinstance(rows, list) or not rows:
        errors.append("assignments must be a non-empty list")
        rows = []
    keys: set[str] = set()
    namespaces: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append("assignment must be an object")
            continue
        key = row.get("machine_key")
        namespace = row.get("memory_namespace")
        if key in keys:
            errors.append(f"duplicate machine_key: {key}")
        keys.add(key)
        if namespace in namespaces:
            errors.append(f"duplicate memory_namespace: {namespace}")
        namespaces.add(namespace)
        if not isinstance(row.get("hard_quota_bytes"), int) or row["hard_quota_bytes"] <= 0:
            errors.append(f"{key} has invalid hard_quota_bytes")
        if not isinstance(row.get("working_set_bytes"), int) or row["working_set_bytes"] <= 0:
            errors.append(f"{key} has invalid working_set_bytes")
        if row.get("working_set_bytes", 0) > row.get("hard_quota_bytes", 0):
            errors.append(f"{key} working set exceeds hard quota")
        if row.get("orchestration_determinism") != "strict-v1":
            errors.append(f"{key} lacks strict orchestration determinism")
        if row.get("semantic_determinism") == "bounded-semantic-v1" and row.get("model_version_required") is not True:
            errors.append(f"{key} bounded semantic execution lacks model-version pinning")
        if row.get("fail_closed") is not True:
            errors.append(f"{key} is not fail closed")
        maturity = str(row.get("maturity") or "").casefold()
        if maturity in HOT_MATURITY and row.get("write_enabled") is not True:
            errors.append(f"{key} hot maturity lacks writable memory")
        if maturity not in HOT_MATURITY and row.get("write_enabled") is not False:
            errors.append(f"{key} non-hot maturity was incorrectly promoted to writable")
        survival = row.get("survival_contract", {})
        required_survival = {
            "persistent_identity", "persistent_state", "deterministic_functions",
            "queues", "leases", "recovery", "evidence", "authority_enforcement",
            "health_check", "model_dependency", "degraded_without_model",
            "replaceable_model", "restart_behavior",
        }
        if not isinstance(survival, dict) or not required_survival.issubset(survival):
            errors.append(f"{key} has incomplete survival contract")

    brain = next((row for row in rows if row.get("machine_key") == "penta.brain"), None)
    if not brain:
        errors.append("PentaBrain is absent")
    else:
        if brain.get("memory_profile") != "brain-v1":
            errors.append("PentaBrain does not have brain-v1 memory")
        if brain.get("activation_state") != "ACTIVE_FAIL_CLOSED":
            errors.append("PentaBrain is not ACTIVE_FAIL_CLOSED")
        if brain.get("brain_mesh_role") != "anchor":
            errors.append("PentaBrain is not the brain mesh anchor")
        if brain.get("semantic_determinism") != "bounded-semantic-v1":
            errors.append("PentaBrain semantic synthesis is not bounded/version-pinned")
        if brain.get("model_version_required") is not True:
            errors.append("PentaBrain model use does not require a pinned model version")
        if brain.get("execution_eligible_by_registry") is True:
            errors.append("PentaBrain memory must not manufacture PM execution eligibility")

    counts = manifest.get("counts", {})
    if counts.get("canonical_pentas") != len(rows):
        errors.append("canonical_pentas count mismatch")
    if counts.get("hot_writable", 0) + counts.get("cold_reserved", 0) != len(rows):
        errors.append("hot/cold allocation count mismatch")
    if any(key in manifest for key in ("generated_at", "updated_at", "timestamp")):
        errors.append("wall-clock fields are forbidden from deterministic manifest")

    if errors:
        raise DeterministicMemoryError("; ".join(errors))


def deterministic_receipt(
    manifest: dict[str, Any],
    *,
    machine_key: str,
    operation: str,
    input_value: Any,
    provider: str | None = None,
    provider_version: str | None = None,
    model: str | None = None,
    model_version: str | None = None,
    result_value: Any | None = None,
    previous_hash: str | None = None,
) -> dict[str, Any]:
    assignment = next(
        (row for row in manifest["assignments"] if row["machine_key"] == machine_key),
        None,
    )
    if assignment is None:
        raise DeterministicMemoryError(f"unknown Penta: {machine_key}")
    if not operation or not re.fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,127}", operation):
        raise DeterministicMemoryError("operation must be a stable lowercase operation key")
    semantic = assignment["semantic_determinism"] == "bounded-semantic-v1"
    if provider is not None and not provider_version:
        raise DeterministicMemoryError("provider execution requires a pinned provider version")
    if model is not None:
        if not provider or not provider_version or not model_version:
            raise DeterministicMemoryError(
                "model execution requires pinned provider, provider version, and model version"
            )
    if semantic and model_version is not None and model is None:
        raise DeterministicMemoryError("model_version cannot be supplied without a model")

    input_sha = sha256_hex(canonical_json_bytes(input_value))
    stable_request = {
        "schema": "ct.penta.deterministic-request.v1",
        "machine_key": machine_key,
        "operation": operation,
        "manifest_sha256": manifest["manifest_sha256"],
        "orchestration_determinism": assignment["orchestration_determinism"],
        "semantic_determinism": assignment["semantic_determinism"],
        "input_sha256": input_sha,
        "provider": provider,
        "provider_version": provider_version,
        "model": model,
        "model_version": model_version,
        "seed": assignment["seed"],
        "temperature": assignment["temperature"],
    }
    request_hash = sha256_hex(canonical_json_bytes(stable_request))
    receipt: dict[str, Any] = {
        "schema": "ct.penta.deterministic-receipt.v1",
        "machine_key": machine_key,
        "operation": operation,
        "request_hash": request_hash,
        "idempotency_key": request_hash,
        "replay_key": request_hash,
        "input_sha256": input_sha,
        "manifest_sha256": manifest["manifest_sha256"],
        "previous_hash": previous_hash,
        "provider": provider,
        "provider_version": provider_version,
        "model": model,
        "model_version": model_version,
        "seed": assignment["seed"],
        "temperature": assignment["temperature"],
        "authority_created": False,
        "fail_closed": True,
    }
    if result_value is not None:
        receipt["result_sha256"] = sha256_hex(canonical_json_bytes(result_value))
    receipt["receipt_sha256"] = sha256_hex(canonical_json_bytes(receipt))
    return receipt


def render_manifest(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_or_check(root: Path, output: Path, *, write: bool, check: bool) -> int:
    manifest = build_manifest(root)
    text = render_manifest(manifest)
    destination = output if output.is_absolute() else root / output
    if write:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        print(
            f"Penta deterministic memory census written: {destination} "
            f"pentas={manifest['counts']['canonical_pentas']} "
            f"hot={manifest['counts']['hot_writable']} "
            f"cold={manifest['counts']['cold_reserved']} "
            f"sha256={manifest['manifest_sha256']}"
        )
        return 0
    if check:
        if not destination.exists():
            print(f"deterministic memory census missing: {destination}", file=sys.stderr)
            return 2
        current = destination.read_text(encoding="utf-8")
        if current != text:
            print(
                "deterministic memory census drift detected; run "
                "python runtime/penta_deterministic_memory.py reconcile --write",
                file=sys.stderr,
            )
            return 3
        print(
            f"Penta deterministic memory census PASS: "
            f"pentas={manifest['counts']['canonical_pentas']} "
            f"sha256={manifest['manifest_sha256']}"
        )
        return 0
    print(text, end="")
    return 0


def _parse_json_argument(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise DeterministicMemoryError(f"invalid JSON argument: {exc}") from exc


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Govern deterministic Penta memory and replay receipts")
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    reconcile = sub.add_parser("reconcile", help="generate or validate the repository memory census")
    reconcile.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    mode = reconcile.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")

    validate = sub.add_parser("validate", help="validate a generated memory census")
    validate.add_argument("--manifest", type=Path, default=DEFAULT_OUTPUT_PATH)

    receipt = sub.add_parser("receipt", help="create a deterministic execution receipt")
    receipt.add_argument("--manifest", type=Path, default=DEFAULT_OUTPUT_PATH)
    receipt.add_argument("--penta", required=True)
    receipt.add_argument("--operation", required=True)
    receipt.add_argument("--input-json", required=True)
    receipt.add_argument("--result-json")
    receipt.add_argument("--provider")
    receipt.add_argument("--provider-version")
    receipt.add_argument("--model")
    receipt.add_argument("--model-version")
    receipt.add_argument("--previous-hash")

    args = parser.parse_args(list(argv) if argv is not None else None)
    root = args.root.resolve()
    try:
        if args.command == "reconcile":
            return write_or_check(root, args.output, write=args.write, check=args.check)
        if args.command == "validate":
            path = args.manifest if args.manifest.is_absolute() else root / args.manifest
            manifest = load_object(path)
            validate_manifest(manifest, config=load_object(root / CONFIG_PATH))
            print(
                f"Penta deterministic memory manifest PASS: "
                f"pentas={manifest['counts']['canonical_pentas']} "
                f"sha256={manifest['manifest_sha256']}"
            )
            return 0
        if args.command == "receipt":
            path = args.manifest if args.manifest.is_absolute() else root / args.manifest
            manifest = load_object(path)
            validate_manifest(manifest, config=load_object(root / CONFIG_PATH))
            generated = deterministic_receipt(
                manifest,
                machine_key=args.penta,
                operation=args.operation,
                input_value=_parse_json_argument(args.input_json),
                provider=args.provider,
                provider_version=args.provider_version,
                model=args.model,
                model_version=args.model_version,
                result_value=(
                    _parse_json_argument(args.result_json)
                    if args.result_json is not None
                    else None
                ),
                previous_hash=args.previous_hash,
            )
            print(json.dumps(generated, indent=2, sort_keys=True))
            return 0
    except DeterministicMemoryError as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
