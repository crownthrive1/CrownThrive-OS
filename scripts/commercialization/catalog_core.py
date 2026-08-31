#!/usr/bin/env python3
"""Build an evidence-derived CrownThrive commercialization catalog.

This program is intentionally fail-closed. It never promotes a component from a
lifecycle label, version number, public visibility, or provider success alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

PASS_VALUES_DEFAULT = {"PASS", "PRODUCTION_CERTIFIED", "CERTIFIED_PRODUCTION"}
SECRET_KEY_PATTERN = re.compile(
    r"(?i)(private[_-]?key|mnemonic|wallet[_-]?password|api[_-]?secret|access[_-]?token|client[_-]?secret)"
)
SECRET_VALUE_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
]
SAFE_SECRET_REFERENCE_PATTERN = re.compile(
    r"(?i)(vault|secret[_-]?ref|reference[_-]?only|runtime[_-]?secret|os[_-]?keychain|"
    r"environment[_-]?(?:variable|secret)|env[_-]?(?:var|secret)|not[_-]?stored|"
    r"persistent[_-]?runner[_-]?only|disabled|forbidden|prohibited|redacted)"
)


class CatalogError(RuntimeError):
    """Raised for deterministic policy or validation failures."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"cannot parse JSON {path}: {exc}") from exc


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def get_path(record: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = record
    for segment in dotted_path.split("."):
        if not isinstance(current, Mapping) or segment not in current:
            return None
        current = current[segment]
    return current


def first_value(record: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        value = get_path(record, key)
        if value not in (None, "", [], {}):
            return value
    return None


def normalized_state(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip().upper().replace("-", "_").replace(" ", "_")


def iter_json_files(repo_root: Path, roots: Sequence[str], excludes: Sequence[str]) -> Iterator[Path]:
    excluded = [(repo_root / item).resolve() for item in excludes]
    seen: set[Path] = set()
    for root_name in roots:
        root = (repo_root / root_name).resolve()
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else root.rglob("*.json")
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            if any(resolved == item or item in resolved.parents for item in excluded):
                continue
            if not resolved.is_file():
                continue
            seen.add(resolved)
            yield resolved


def record_identity(record: Mapping[str, Any], policy: Mapping[str, Any]) -> str | None:
    value = first_value(record, policy["identity_keys"])
    return str(value).strip() if value not in (None, "") else None


def record_name(record: Mapping[str, Any], policy: Mapping[str, Any], component_id: str) -> str:
    value = first_value(record, policy["name_keys"])
    return str(value).strip() if value not in (None, "") else component_id


def record_type(record: Mapping[str, Any], policy: Mapping[str, Any]) -> str:
    value = first_value(record, policy["type_keys"])
    return str(value).strip() if value not in (None, "") else "component"


def record_version(record: Mapping[str, Any], policy: Mapping[str, Any]) -> str:
    value = first_value(record, policy["version_keys"])
    return str(value).strip() if value not in (None, "") else "0.0.0+unknown"


def walk_records(
    value: Any,
    collections: set[str],
    source_path: str,
    parent_path: str = "$",
) -> Iterator[tuple[Mapping[str, Any], str]]:
    if isinstance(value, Mapping):
        yield value, parent_path
        for key, child in value.items():
            if key not in collections:
                continue
            child_path = f"{parent_path}.{key}"
            if isinstance(child, list):
                for index, item in enumerate(child):
                    if isinstance(item, Mapping):
                        yield from walk_records(item, collections, source_path, f"{child_path}[{index}]")
            elif isinstance(child, Mapping):
                yield from walk_records(child, collections, source_path, child_path)


def explicit_certification(
    record: Mapping[str, Any], certification_policy: Mapping[str, Any]
) -> tuple[bool, str | None, str | None]:
    accepted = {normalized_state(item) for item in certification_policy.get("accepted_values", PASS_VALUES_DEFAULT)}
    for path in certification_policy.get("explicit_paths", []):
        value = normalized_state(get_path(record, path))
        if value in accepted:
            return True, value, path

    composite = certification_policy.get("composite_release_rule", {})
    if not composite.get("enabled", False):
        return False, None, None

    lifecycle = normalized_state(first_value(record, ["lifecycle_state", "state", "release_state"]))
    allowed_lifecycle = {normalized_state(item) for item in composite.get("lifecycle_values", [])}
    if lifecycle not in allowed_lifecycle:
        return False, None, None

    for path in composite.get("required_nonempty_paths", []):
        if get_path(record, path) in (None, "", [], {}):
            return False, None, None

    for path in composite.get("required_pass_paths", []):
        value = normalized_state(get_path(record, path))
        if value not in accepted:
            return False, None, None

    return True, "PASS_COMPOSITE_RELEASE", "composite_release_rule"


def visibility_block(record: Mapping[str, Any], visibility_policy: Mapping[str, Any]) -> str | None:
    blocked = {normalized_state(item) for item in visibility_policy.get("blocked_values", [])}
    for path in visibility_policy.get("explicit_paths", []):
        value = normalized_state(get_path(record, path))
        if value in blocked:
            return f"blocked_visibility:{path}={value}"
    if bool(record.get("no_release")) or bool(record.get("public_release_blocked")):
        return "blocked_visibility:no_release"
    return None


def is_safe_secret_reference(value: str) -> bool:
    normalized = value.strip()
    if normalized in ("", "${REDACTED}", "REDACTED", "***"):
        return True
    if normalized.startswith("${") and normalized.endswith("}"):
        return True
    return bool(SAFE_SECRET_REFERENCE_PATTERN.search(normalized))


def contains_secret_material(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if (
                SECRET_KEY_PATTERN.search(str(key))
                and isinstance(child, str)
                and not is_safe_secret_reference(child)
            ):
                findings.append(child_path)
            findings.extend(contains_secret_material(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(contains_secret_material(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append(path)
                break
    return findings


@dataclass(frozen=True)
class SourceRecord:
    component_id: str
    name: str
    component_type: str
    version: str
    source_path: str
    object_path: str
    source_fingerprint: str
    certification_state: str | None
    certification_source: str | None
    record: Mapping[str, Any] = field(compare=False, repr=False)


def source_rank(source_path: str, policy: Mapping[str, Any]) -> tuple[int, str]:
    for index, root in enumerate(policy.get("source_roots", [])):
        normalized_root = str(root).rstrip("/")
        if source_path == normalized_root or source_path.startswith(normalized_root + "/"):
            return index, source_path
    return len(policy.get("source_roots", [])), source_path


def commercial_safety_signature(
    source: SourceRecord,
    policy: Mapping[str, Any],
) -> tuple[Any, ...]:
    block = source.record.get("commercialization")
    block_fingerprint = sha256_json(block) if isinstance(block, Mapping) else None
    free_paths = policy.get("commercialization", {}).get(
        "free_evaluation_authorization_paths", []
    )
    free_authorizations = tuple(get_path(source.record, path) for path in free_paths)
    return (
        source.certification_state is not None,
        visibility_block(source.record, policy["visibility"]),
        block_fingerprint,
        free_authorizations,
    )


def source_record_evidence(source: SourceRecord, policy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_path": source.source_path,
        "object_path": source.object_path,
        "source_fingerprint": source.source_fingerprint,
        "certification_state": source.certification_state,
        "certification_source": source.certification_source,
        "visibility_block": visibility_block(source.record, policy["visibility"]),
    }


def normalize_source_record(
    record: Mapping[str, Any],
    source_path: str,
    object_path: str,
    policy: Mapping[str, Any],
) -> SourceRecord | None:
    component_id = record_identity(record, policy)
    if not component_id:
        return None
    certified, cert_state, cert_source = explicit_certification(record, policy["certification"])
    return SourceRecord(
        component_id=component_id,
        name=record_name(record, policy, component_id),
        component_type=record_type(record, policy),
        version=record_version(record, policy),
        source_path=source_path,
        object_path=object_path,
        source_fingerprint=sha256_json(record),
        certification_state=cert_state if certified else None,
        certification_source=cert_source if certified else None,
        record=record,
    )


