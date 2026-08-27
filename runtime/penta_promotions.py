"""Fail-closed evidence bindings for explicit Penta maturity promotions.

The Penta Family does not infer or manufacture child maturity. This module
applies a separately governed promotion registry only when the source maturity,
exact evidence digests, runtime paths, authority reference, and non-provider
boundaries all validate. Provider state is never changed here.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping


PROMOTION_PATH = Path("data/penta/production-promotions.v1.json")
SCHEMA_ID = "ct.penta.production-promotions.v1"
SCHEMA_VERSION = "1.1.0"
EXECUTION_ELIGIBLE = {"certified", "production"}
ALLOWED_MATURITY = {"specified", "implemented", "certified", "production", "hold", "retired"}
PROVIDER_STATE_DISPOSITION = "UNCHANGED_SEPARATELY_GATED"


class PentaPromotionError(ValueError):
    """Raised when a promotion record cannot prove its bounded claim."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PentaPromotionError(f"cannot load promotion JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PentaPromotionError(f"promotion JSON root must be an object: {path}")
    return value


def _repo_file(root: Path, value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise PentaPromotionError(f"{field} must be a non-empty repository-relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise PentaPromotionError(f"unsafe repository-relative path in {field}: {value!r}")
    root_resolved = root.resolve()
    candidate = (root_resolved / relative).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise PentaPromotionError(f"{field} escapes the repository: {value!r}") from exc
    if not candidate.is_file():
        raise PentaPromotionError(f"promotion evidence/runtime missing: {value}")
    return candidate


def _timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise PentaPromotionError(f"{field} must be exact UTC YYYY-MM-DDTHH:MM:SSZ")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise PentaPromotionError(f"{field} is not a real UTC timestamp") from exc
    return value


def _strings(value: Any, field: str, *, nonempty: bool = True) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise PentaPromotionError(f"{field} must be a non-empty string array")
    return list(value)


def load_promotion_manifest(root: Path, *, required: bool = False) -> dict[str, Any] | None:
    """Load and cryptographically validate the canonical promotion registry."""
    root = Path(root).resolve()
    path = root / PROMOTION_PATH
    if not path.exists():
        if required:
            raise PentaPromotionError(f"required promotion registry missing: {PROMOTION_PATH}")
        return None
    manifest = _load_json(path)
    if manifest.get("schema") != SCHEMA_ID or manifest.get("version") != SCHEMA_VERSION:
        raise PentaPromotionError("unexpected production promotion registry schema/version")
    if manifest.get("fail_closed") is not True:
        raise PentaPromotionError("production promotion registry must fail closed")
    if manifest.get("self_promotion_prohibited") is not True:
        raise PentaPromotionError("production promotion registry must prohibit self-promotion")
    if manifest.get("provider_state_policy") != "never_promoted_by_this_registry":
        raise PentaPromotionError("production promotion registry may not promote provider state")

    promotions = manifest.get("promotions")
    if not isinstance(promotions, list):
        raise PentaPromotionError("production promotions must be an array")
    seen_ids: set[str] = set()
    seen_members: set[str] = set()
    for index, item in enumerate(promotions):
        if not isinstance(item, dict):
            raise PentaPromotionError(f"promotion {index} must be an object")
        required_fields = {
            "promotion_id", "machine_key", "from_maturity", "to_maturity",
            "effective_at", "authority_ref", "evidence_status", "evidence_bindings",
            "runtime_refs", "proof", "scope", "provider_state_disposition",
            "provider_effect_authorized", "self_certification_authorized",
        }
        missing = required_fields - set(item)
        if missing:
            raise PentaPromotionError(
                f"promotion {index} missing fields: {', '.join(sorted(missing))}"
            )
        promotion_id = item["promotion_id"]
        machine_key = item["machine_key"]
        if not isinstance(promotion_id, str) or not re.fullmatch(r"promo-[a-z0-9.-]+", promotion_id):
            raise PentaPromotionError(f"invalid promotion_id: {promotion_id!r}")
        if promotion_id in seen_ids:
            raise PentaPromotionError(f"duplicate promotion_id: {promotion_id}")
        seen_ids.add(promotion_id)
        if not isinstance(machine_key, str) or not re.fullmatch(r"penta\.[a-z0-9.-]+", machine_key):
            raise PentaPromotionError(f"invalid promotion machine_key: {machine_key!r}")
        if machine_key in seen_members:
            raise PentaPromotionError(f"duplicate promotion for {machine_key}")
        seen_members.add(machine_key)
        if item["from_maturity"] not in ALLOWED_MATURITY:
            raise PentaPromotionError(f"invalid prior maturity for {machine_key}")
        if item["to_maturity"] not in EXECUTION_ELIGIBLE or item["to_maturity"] == item["from_maturity"]:
            raise PentaPromotionError(f"invalid promotion target maturity for {machine_key}")
        _timestamp(item["effective_at"], f"{machine_key}.effective_at")
        if not isinstance(item["authority_ref"], str) or not item["authority_ref"].strip():
            raise PentaPromotionError(f"promotion authority_ref missing for {machine_key}")
        if item["evidence_status"] != "PASS":
            raise PentaPromotionError(f"promotion evidence is not PASS for {machine_key}")
        if item["provider_state_disposition"] != PROVIDER_STATE_DISPOSITION:
            raise PentaPromotionError(f"provider state must remain separately gated for {machine_key}")
        if item["provider_effect_authorized"] is not False:
            raise PentaPromotionError(f"promotion may not authorize provider effects for {machine_key}")
        if item["self_certification_authorized"] is not False:
            raise PentaPromotionError(f"promotion may not authorize self-certification for {machine_key}")
        if not isinstance(item["scope"], str) or not item["scope"].strip():
            raise PentaPromotionError(f"promotion scope missing for {machine_key}")
        _strings(item["proof"], f"{machine_key}.proof")

        bindings = item["evidence_bindings"]
        if not isinstance(bindings, list) or not bindings:
            raise PentaPromotionError(f"evidence bindings missing for {machine_key}")
        bound_paths: set[str] = set()
        for binding in bindings:
            if not isinstance(binding, dict) or set(binding) != {"path", "sha256", "claim"}:
                raise PentaPromotionError(f"invalid evidence binding for {machine_key}")
            evidence_path = binding["path"]
            expected_digest = binding["sha256"]
            if evidence_path in bound_paths:
                raise PentaPromotionError(f"duplicate evidence binding for {machine_key}: {evidence_path}")
            bound_paths.add(evidence_path)
            if not isinstance(expected_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
                raise PentaPromotionError(f"invalid evidence digest for {machine_key}: {evidence_path}")
            if not isinstance(binding["claim"], str) or not binding["claim"].strip():
                raise PentaPromotionError(f"evidence claim missing for {machine_key}: {evidence_path}")
            actual_digest = sha256(_repo_file(root, evidence_path, "evidence path").read_bytes()).hexdigest()
            if actual_digest != expected_digest:
                raise PentaPromotionError(
                    f"promotion evidence digest mismatch for {machine_key}: {evidence_path}"
                )

        runtime_refs = _strings(item["runtime_refs"], f"{machine_key}.runtime_refs")
        if len(runtime_refs) != len(set(runtime_refs)):
            raise PentaPromotionError(f"duplicate runtime reference for {machine_key}")
        for runtime_ref in runtime_refs:
            _repo_file(root, runtime_ref, "runtime reference")
    return manifest


def apply_promotions(
    root: Path,
    members: Mapping[str, Mapping[str, Any]],
    *,
    required: bool = False,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return a promoted copy and its evidence lineage; never mutate inputs."""
    promoted = {key: deepcopy(dict(value)) for key, value in members.items()}
    manifest = load_promotion_manifest(root, required=required)
    if manifest is None:
        return promoted, {}
    applied: dict[str, dict[str, Any]] = {}
    for item in manifest["promotions"]:
        machine_key = item["machine_key"]
        if machine_key not in promoted:
            raise PentaPromotionError(f"promotion targets unknown member: {machine_key}")
        current = promoted[machine_key].get("maturity")
        if current != item["from_maturity"]:
            raise PentaPromotionError(
                f"promotion prior maturity mismatch for {machine_key}: expected {current!r}, "
                f"record declares {item['from_maturity']!r}"
            )
        lineage = {
            "promotion_id": item["promotion_id"],
            "from_maturity": current,
            "to_maturity": item["to_maturity"],
            "effective_at": item["effective_at"],
            "authority_ref": item["authority_ref"],
            "evidence_bindings": deepcopy(item["evidence_bindings"]),
            "runtime_refs": list(item["runtime_refs"]),
            "scope": item["scope"],
            "provider_state_disposition": PROVIDER_STATE_DISPOSITION,
            "provider_effect_authorized": False,
            "self_certification_authorized": False,
            "promotion_registry": str(PROMOTION_PATH),
        }
        promoted[machine_key]["catalog_maturity"] = current
        promoted[machine_key]["maturity"] = item["to_maturity"]
        promoted[machine_key]["maturity_promotion"] = lineage
        applied[machine_key] = lineage
    return promoted, applied
