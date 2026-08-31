#!/usr/bin/env python3
"""Generate deterministic, language-specific registry adapter packages.

The generated packages expose public-safe component metadata and immutable source
coordinates. They do not copy restricted implementations, grant a license, or
publish to a provider. Provider publication remains separately authorized.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


class AdapterError(RuntimeError):
    """Raised when an adapter cannot be generated safely."""


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def write_text(path: Path, value: str) -> None:
    write_bytes(path, value.encode("utf-8"))


def write_json(path: Path, value: Any) -> None:
    write_bytes(path, canonical_json(value))


def safe_slug(component_id: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", component_id.lower()).strip("-") or "component"
    if len(base) > 32:
        digest = hashlib.sha256(component_id.encode("utf-8")).hexdigest()[:10]
        base = f"{base[:21].rstrip('-')}-{digest}"
    return base


def safe_identifier(slug: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_]", "_", slug.replace("-", "_")).strip("_") or "component"
    if value[0].isdigit():
        value = f"ct_{value}"
    return value


def pascal_identifier(slug: str) -> str:
    parts = [part for part in re.split(r"[^a-zA-Z0-9]+", slug) if part]
    value = "".join(part[:1].upper() + part[1:] for part in parts) or "CrownThriveComponent"
    if value[0].isdigit():
        value = f"CT{value}"
    return value


def normalized_versions(source_version: str, fingerprint: str) -> dict[str, str]:
    value = source_version.strip()
    semver = re.fullmatch(
        r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
        r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+(?P<build>[0-9A-Za-z.-]+))?",
        value,
    )
    four = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value)
    if semver:
        major, minor, patch = semver.group("major", "minor", "patch")
        pre = semver.group("pre")
        base = f"{major}.{minor}.{patch}"
        registry = f"{base}-{pre}" if pre else base
        if not pre:
            pep440 = base
        elif re.fullmatch(r"rc(?:\.|-)?\d+", pre, flags=re.IGNORECASE):
            pep440 = base + "rc" + re.sub(r"\D", "", pre)
        elif re.fullmatch(r"(?:alpha|a)(?:\.|-)?\d+", pre, flags=re.IGNORECASE):
            pep440 = base + "a" + re.sub(r"\D", "", pre)
        elif re.fullmatch(r"(?:beta|b)(?:\.|-)?\d+", pre, flags=re.IGNORECASE):
            pep440 = base + "b" + re.sub(r"\D", "", pre)
        else:
            local = re.sub(r"[^0-9A-Za-z.]+", ".", pre).strip(".").lower() or "candidate"
            pep440 = f"{base}.dev0+{local}"
        ruby = registry.replace("-", ".pre.")
    elif four:
        major, minor, patch, evidence = four.groups()
        base = f"{major}.{minor}.{patch}"
        registry = f"{base}-ct.{evidence}"
        pep440 = f"{base}.post{evidence}"
        ruby = f"{base}.pre.ct.{evidence}"
    else:
        suffix = fingerprint[:10]
        registry = f"0.0.0-ct.{suffix}"
        pep440 = f"0.0.0.dev0+ct.{suffix}"
        ruby = f"0.0.0.pre.ct.{suffix}"
    return {
        "source": value,
        "semver": registry,
        "pypi": pep440,
        "maven": registry.replace(".", "."),
        "nuget": registry,
        "ruby": ruby,
    }


def component_metadata(component: Mapping[str, Any], source_sha: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "component_id": component["component_id"],
        "canonical_name": component.get("canonical_name", component["component_id"]),
        "component_type": component.get("component_type", "component"),
        "source_version": component["version"],
        "source_sha": source_sha,
        "source_path": component.get("source_path"),
        "source_fingerprint": component.get("source_fingerprint"),
        "catalog_state": component.get("catalog_state"),
        "offer_ids": component.get("offer_ids", []),
        "license_resolution": "resolve exact offer/license through CHLOM before non-evaluation use",
        "publication_state": "BUILT_UNPUBLISHED_PROVIDER_VALIDATION_REQUIRED",
        "rights_notice": "Registry installation does not independently grant commercial, production, trademark, certification, data/model, or provider rights.",
    }


def common_notice(metadata: Mapping[str, Any]) -> str:
    return (
        f"# {metadata['canonical_name']} Registry Adapter\n\n"
        f"Component ID: `{metadata['component_id']}`  \n"
        f"Source version: `{metadata['source_version']}`  \n"
        f"Source SHA: `{metadata['source_sha']}`\n\n"
        "This is a public-safe interoperability and registry metadata adapter. It does not include "
        "restricted CrownThrive implementation material and does not create a license, entitlement, "
        "provider authority, settlement, or CrownThrive/CHLOM/CIE certification. Resolve the exact "
        "offer and governing agreement through CHLOM before production or commercial use.\n"
    )


def write_common(directory: Path, metadata: Mapping[str, Any]) -> None:
    write_json(directory / "component.json", metadata)
    write_text(directory / "README.md", common_notice(metadata))
    write_text(
        directory / "LICENSE.md",
        "CrownThrive proprietary/public-safe adapter notice. No rights are granted by package "
        "publication or installation except under the exact package-specific or executed CrownThrive agreement.\n",
    )


