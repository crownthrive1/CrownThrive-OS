"""Deterministic multi-registry adapter factory."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, Mapping

from scripts.commercialization.adapter_core import (
    AdapterError, canonical_json, component_metadata, normalized_versions, safe_slug, sha256_bytes, write_json,
)
from scripts.commercialization.adapter_languages_a import (
    generate_cargo, generate_composer, generate_go, generate_maven, generate_npm,
    generate_nuget, generate_pypi,
)
from scripts.commercialization.adapter_languages_b import (
    generate_dart, generate_oci, generate_rubygems, generate_swift,
)

GENERATORS = {
    "npm": generate_npm,
    "pypi": generate_pypi,
    "maven": generate_maven,
    "nuget": generate_nuget,
    "cargo": generate_cargo,
    "go": generate_go,
    "composer": generate_composer,
    "rubygems": generate_rubygems,
    "swift": generate_swift,
    "dart": generate_dart,
    "oci": generate_oci,
}

def generate_adapters(catalog: Mapping[str, Any], output: Path) -> dict[str, Any]:
    source_sha = str(catalog.get("source_sha") or "").strip()
    if not source_sha:
        raise AdapterError("catalog requires exact source_sha")
    components = catalog.get("components")
    if not isinstance(components, list):
        raise AdapterError("catalog components must be a list")
    resolved = output.resolve()
    if resolved == Path(resolved.anchor):
        raise AdapterError("refusing to replace filesystem root")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    for component in sorted(components, key=lambda row: (str(row.get("component_id")), str(row.get("version")))):
        if not isinstance(component, Mapping):
            raise AdapterError("catalog component must be an object")
        component_id = str(component.get("component_id") or "").strip()
        version = str(component.get("version") or "").strip()
        fingerprint = str(component.get("source_fingerprint") or "").strip()
        if not component_id or not version or not fingerprint:
            raise AdapterError("eligible component missing id, version, or source fingerprint")
        slug = safe_slug(component_id)
        if slug in seen_slugs:
            slug = f"{slug}-{hashlib.sha256((component_id + version).encode()).hexdigest()[:8]}"
        seen_slugs.add(slug)
        metadata = component_metadata(component, source_sha)
        versions = normalized_versions(version, fingerprint)
        component_root = output / slug
        descriptor_records: list[dict[str, Any]] = []
        for ecosystem, generator in GENERATORS.items():
            files = generator(component_root, slug, metadata, versions)
            descriptor_records.append(
                {
                    "ecosystem": ecosystem,
                    "path": f"{slug}/{ecosystem}",
                    "file_count": len(files),
                    "files": [
                        {
                            "path": path.relative_to(output).as_posix(),
                            "sha256": sha256_bytes(path.read_bytes()),
                            "size": path.stat().st_size,
                        }
                        for path in files
                    ],
                    "publication_state": "BUILT_UNPUBLISHED_PROVIDER_VALIDATION_REQUIRED",
                }
            )
        entries.append(
            {
                "component_id": component_id,
                "component_version": version,
                "source_sha": source_sha,
                "slug": slug,
                "registry_versions": versions,
                "descriptors": descriptor_records,
            }
        )

    index = {
        "schema_version": "1.0.0",
        "index_id": "ct.registry-adapter-index.cos-commercialization.v1",
        "source_sha": source_sha,
        "component_count": len(entries),
        "ecosystems": list(GENERATORS),
        "publication_authorized": False,
        "provider_validation_required": True,
        "rights_notice": "Generated descriptors are public-safe metadata adapters; installation or provider publication does not create rights or certification.",
        "components": entries,
    }
    index["index_fingerprint"] = sha256_bytes(canonical_json(index))
    write_json(output / "adapter-index.json", index)
    return index


