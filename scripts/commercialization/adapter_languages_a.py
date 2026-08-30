"""Registry adapter generators for npm, PyPI, Maven, NuGet, Cargo, Go, and Composer."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Mapping

from scripts.commercialization.adapter_core import safe_identifier, write_common, write_json, write_text

def generate_npm(root: Path, slug: str, metadata: Mapping[str, Any], versions: Mapping[str, str]) -> list[Path]:
    directory = root / "npm"
    write_common(directory, metadata)
    package = {
        "name": f"@crownthrive/{slug}",
        "version": versions["semver"],
        "description": f"CrownThrive metadata adapter for {metadata['component_id']}",
        "license": "SEE LICENSE IN LICENSE.md",
        "type": "module",
        "exports": {".": "./component.json"},
        "files": ["component.json", "README.md", "LICENSE.md"],
        "sideEffects": False,
        "repository": {
            "type": "git",
            "url": "git+https://github.com/crownthrive1/CrownThrive-OS.git",
        },
        "publishConfig": {"access": "public", "provenance": True},
        "crownthrive": {
            "sourceSha": metadata["source_sha"],
            "sourceVersion": metadata["source_version"],
            "publicationAuthorized": False,
        },
    }
    write_json(directory / "package.json", package)
    return sorted(path for path in directory.rglob("*") if path.is_file())


def generate_pypi(root: Path, slug: str, metadata: Mapping[str, Any], versions: Mapping[str, str]) -> list[Path]:
    directory = root / "pypi"
    module = safe_identifier(slug)
    write_common(directory, metadata)
    pyproject = f'''[build-system]\nrequires = ["setuptools>=69"]\nbuild-backend = "setuptools.build_meta"\n\n[project]\nname = "crownthrive-{slug}"\nversion = "{versions['pypi']}"\ndescription = "CrownThrive metadata adapter for {metadata['component_id']}"\nreadme = "README.md"\nrequires-python = ">=3.9"\nlicense = {{text = "Proprietary - see LICENSE.md"}}\nauthors = [{{name = "CrownThrive, LLC", email = "contact@crownthrive.com"}}]\nclassifiers = ["Private :: Do Not Upload"]\n\n[project.urls]\nRepository = "https://github.com/crownthrive1/CrownThrive-OS"\n\n[tool.setuptools]\npackage-dir = {{"" = "src"}}\ninclude-package-data = true\n\n[tool.setuptools.packages.find]\nwhere = ["src"]\n'''
    write_text(directory / "pyproject.toml", pyproject)
    init = (
        f'COMPONENT_ID = {metadata["component_id"]!r}\n'
        f'SOURCE_VERSION = {metadata["source_version"]!r}\n'
        f'SOURCE_SHA = {metadata["source_sha"]!r}\n'
        'PUBLICATION_AUTHORIZED = False\n'
    )
    module_root = directory / "src" / module
    write_text(module_root / "__init__.py", init)
    write_json(module_root / "component.json", metadata)
    return sorted(path for path in directory.rglob("*") if path.is_file())


def generate_maven(root: Path, slug: str, metadata: Mapping[str, Any], versions: Mapping[str, str]) -> list[Path]:
    directory = root / "maven"
    write_common(directory, metadata)
    pom = f'''<?xml version="1.0" encoding="UTF-8"?>\n<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">\n  <modelVersion>4.0.0</modelVersion>\n  <groupId>com.crownthrive</groupId>\n  <artifactId>{html.escape(slug)}</artifactId>\n  <version>{html.escape(versions['maven'])}</version>\n  <packaging>pom</packaging>\n  <name>{html.escape(str(metadata['canonical_name']))}</name>\n  <description>CrownThrive public-safe metadata adapter for {html.escape(str(metadata['component_id']))}</description>\n  <url>https://github.com/crownthrive1/CrownThrive-OS</url>\n  <licenses><license><name>Proprietary - exact CHLOM/CrownThrive agreement required</name></license></licenses>\n  <properties><crownthrive.source.sha>{metadata['source_sha']}</crownthrive.source.sha><crownthrive.publication.authorized>false</crownthrive.publication.authorized></properties>\n</project>\n'''
    write_text(directory / "pom.xml", pom)
    return sorted(path for path in directory.rglob("*") if path.is_file())


def generate_nuget(root: Path, slug: str, metadata: Mapping[str, Any], versions: Mapping[str, str]) -> list[Path]:
    directory = root / "nuget"
    write_common(directory, metadata)
    nuspec = f'''<?xml version="1.0"?>\n<package>\n  <metadata>\n    <id>CrownThrive.{html.escape(safe_identifier(slug))}</id>\n    <version>{html.escape(versions['nuget'])}</version>\n    <authors>CrownThrive, LLC</authors>\n    <owners>CrownThrive, LLC</owners>\n    <requireLicenseAcceptance>true</requireLicenseAcceptance>\n    <license type="file">LICENSE.md</license>\n    <readme>README.md</readme>\n    <description>CrownThrive public-safe metadata adapter for {html.escape(str(metadata['component_id']))}</description>\n    <repository type="git" url="https://github.com/crownthrive1/CrownThrive-OS" commit="{metadata['source_sha']}" />\n    <tags>CrownThrive CHLOM interoperability metadata</tags>\n  </metadata>\n  <files>\n    <file src="component.json" target="contentFiles/any/any/component.json" />\n    <file src="README.md" target="README.md" />\n    <file src="LICENSE.md" target="LICENSE.md" />\n  </files>\n</package>\n'''
    write_text(directory / f"CrownThrive.{safe_identifier(slug)}.nuspec", nuspec)
    return sorted(path for path in directory.rglob("*") if path.is_file())


def generate_cargo(root: Path, slug: str, metadata: Mapping[str, Any], versions: Mapping[str, str]) -> list[Path]:
    directory = root / "cargo"
    crate = safe_identifier(slug).lower()
    write_common(directory, metadata)
    cargo = f'''[package]\nname = "crownthrive_{crate}"\nversion = "{versions['semver']}"\nedition = "2021"\ndescription = "CrownThrive metadata adapter for {metadata['component_id']}"\nlicense-file = "LICENSE.md"\nrepository = "https://github.com/crownthrive1/CrownThrive-OS"\ninclude = ["src/**", "component.json", "README.md", "LICENSE.md"]\n\n[lib]\npath = "src/lib.rs"\n'''
    write_text(directory / "Cargo.toml", cargo)
    lib = (
        f'pub const COMPONENT_ID: &str = "{metadata["component_id"]}";\n'
        f'pub const SOURCE_VERSION: &str = "{metadata["source_version"]}";\n'
        f'pub const SOURCE_SHA: &str = "{metadata["source_sha"]}";\n'
        'pub const PUBLICATION_AUTHORIZED: bool = false;\n'
    )
    write_text(directory / "src/lib.rs", lib)
    return sorted(path for path in directory.rglob("*") if path.is_file())


def generate_go(root: Path, slug: str, metadata: Mapping[str, Any], versions: Mapping[str, str]) -> list[Path]:
    del versions
    directory = root / "go"
    package = safe_identifier(slug).lower()
    write_common(directory, metadata)
    write_text(directory / "go.mod", f"module github.com/crownthrive1/cos-adapters/{slug}\n\ngo 1.22\n")
    source = (
        f"package {package}\n\n"
        f'const ComponentID = "{metadata["component_id"]}"\n'
        f'const SourceVersion = "{metadata["source_version"]}"\n'
        f'const SourceSHA = "{metadata["source_sha"]}"\n'
        "const PublicationAuthorized = false\n"
    )
    write_text(directory / "metadata.go", source)
    return sorted(path for path in directory.rglob("*") if path.is_file())


def generate_composer(root: Path, slug: str, metadata: Mapping[str, Any], versions: Mapping[str, str]) -> list[Path]:
    del versions
    directory = root / "composer"
    write_common(directory, metadata)
    composer = {
        "name": f"crownthrive/{slug}",
        "description": f"CrownThrive metadata adapter for {metadata['component_id']}",
        "type": "metapackage",
        "license": "proprietary",
        "support": {"email": "contact@crownthrive.com", "source": "https://github.com/crownthrive1/CrownThrive-OS"},
        "extra": {
            "crownthrive-component-id": metadata["component_id"],
            "crownthrive-source-version": metadata["source_version"],
            "crownthrive-source-sha": metadata["source_sha"],
            "publication-authorized": False,
        },
    }
    write_json(directory / "composer.json", composer)
    return sorted(path for path in directory.rglob("*") if path.is_file())


