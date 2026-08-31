"""Registry adapter generators for RubyGems, SwiftPM, Dart, and OCI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from scripts.commercialization.adapter_core import (
    canonical_json, pascal_identifier, safe_identifier, sha256_bytes,
    write_bytes, write_common, write_json, write_text,
)

def generate_rubygems(root: Path, slug: str, metadata: Mapping[str, Any], versions: Mapping[str, str]) -> list[Path]:
    directory = root / "rubygems"
    module = pascal_identifier(slug)
    gem_name = f"crownthrive-{slug}"
    write_common(directory, metadata)
    gemspec = f'''Gem::Specification.new do |spec|\n  spec.name = "{gem_name}"\n  spec.version = "{versions['ruby']}"\n  spec.authors = ["CrownThrive, LLC"]\n  spec.email = ["contact@crownthrive.com"]\n  spec.summary = "CrownThrive metadata adapter for {metadata['component_id']}"\n  spec.homepage = "https://github.com/crownthrive1/CrownThrive-OS"\n  spec.license = "Nonstandard"\n  spec.files = ["lib/{safe_identifier(slug).lower()}.rb", "component.json", "README.md", "LICENSE.md"]\n  spec.require_paths = ["lib"]\nend\n'''
    write_text(directory / f"{gem_name}.gemspec", gemspec)
    ruby = (
        f"module {module}\n"
        f'  COMPONENT_ID = "{metadata["component_id"]}"\n'
        f'  SOURCE_VERSION = "{metadata["source_version"]}"\n'
        f'  SOURCE_SHA = "{metadata["source_sha"]}"\n'
        "  PUBLICATION_AUTHORIZED = false\n"
        "end\n"
    )
    write_text(directory / "lib" / f"{safe_identifier(slug).lower()}.rb", ruby)
    return sorted(path for path in directory.rglob("*") if path.is_file())


def generate_swift(root: Path, slug: str, metadata: Mapping[str, Any], versions: Mapping[str, str]) -> list[Path]:
    del versions
    directory = root / "swift"
    module = pascal_identifier(slug)
    write_common(directory, metadata)
    package = f'''// swift-tools-version: 5.9\nimport PackageDescription\n\nlet package = Package(\n    name: "{module}",\n    products: [.library(name: "{module}", targets: ["{module}"])],\n    targets: [.target(name: "{module}")]\n)\n'''
    write_text(directory / "Package.swift", package)
    source = f'''public enum CrownThriveMetadata {{\n    public static let componentID = "{metadata['component_id']}"\n    public static let sourceVersion = "{metadata['source_version']}"\n    public static let sourceSHA = "{metadata['source_sha']}"\n    public static let publicationAuthorized = false\n}}\n'''
    write_text(directory / "Sources" / module / "Metadata.swift", source)
    return sorted(path for path in directory.rglob("*") if path.is_file())


def generate_dart(root: Path, slug: str, metadata: Mapping[str, Any], versions: Mapping[str, str]) -> list[Path]:
    directory = root / "dart"
    package = safe_identifier(slug).lower()
    write_common(directory, metadata)
    pubspec = f'''name: crownthrive_{package}\nversion: {versions['semver']}\ndescription: CrownThrive metadata adapter for {metadata['component_id']}\nrepository: https://github.com/crownthrive1/CrownThrive-OS\nenvironment:\n  sdk: ">=3.0.0 <4.0.0"\n'''
    write_text(directory / "pubspec.yaml", pubspec)
    source = (
        f"const String componentId = '{metadata['component_id']}';\n"
        f"const String sourceVersion = '{metadata['source_version']}';\n"
        f"const String sourceSha = '{metadata['source_sha']}';\n"
        "const bool publicationAuthorized = false;\n"
    )
    write_text(directory / "lib" / f"{package}.dart", source)
    return sorted(path for path in directory.rglob("*") if path.is_file())


def generate_oci(root: Path, slug: str, metadata: Mapping[str, Any], versions: Mapping[str, str]) -> list[Path]:
    directory = root / "oci"
    write_common(directory, metadata)
    write_json(directory / "oci-layout", {"imageLayoutVersion": "1.0.0"})
    layer = canonical_json(metadata)
    config = canonical_json(
        {
            "created": "1970-01-01T00:00:00Z",
            "architecture": "unknown",
            "os": "unknown",
            "config": {"Labels": {"org.opencontainers.image.version": versions["semver"], "io.crownthrive.component.id": metadata["component_id"]}},
        }
    )
    layer_digest = sha256_bytes(layer)
    config_digest = sha256_bytes(config)
    write_bytes(directory / "blobs/sha256" / layer_digest, layer)
    write_bytes(directory / "blobs/sha256" / config_digest, config)
    manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "artifactType": "application/vnd.crownthrive.component-metadata.v1+json",
        "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "digest": f"sha256:{config_digest}",
            "size": len(config),
        },
        "layers": [
            {
                "mediaType": "application/vnd.crownthrive.component-metadata.v1+json",
                "digest": f"sha256:{layer_digest}",
                "size": len(layer),
                "annotations": {"org.opencontainers.image.title": "component.json"},
            }
        ],
        "annotations": {
            "org.opencontainers.image.title": str(metadata["canonical_name"]),
            "org.opencontainers.image.version": versions["semver"],
            "org.opencontainers.image.revision": str(metadata["source_sha"]),
        },
    }
    manifest_bytes = canonical_json(manifest)
    manifest_digest = sha256_bytes(manifest_bytes)
    write_bytes(directory / "blobs/sha256" / manifest_digest, manifest_bytes)
    index = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "manifests": [
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "artifactType": "application/vnd.crownthrive.component-metadata.v1+json",
                "digest": f"sha256:{manifest_digest}",
                "size": len(manifest_bytes),
                "annotations": {
                    "org.opencontainers.image.ref.name": versions["semver"],
                    "io.crownthrive.component.id": str(metadata["component_id"]),
                },
            }
        ],
    }
    write_json(directory / "index.json", index)
    return sorted(path for path in directory.rglob("*") if path.is_file())
