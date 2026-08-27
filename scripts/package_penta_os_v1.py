#!/usr/bin/env python3
"""Build and verify reproducible Penta OS V1.5 distribution artifacts.

The deterministic archives contain the complete public-safe source closure
needed to regenerate and validate the Penta registry. Runtime/build receipts
that contain workflow timestamps or provider observations remain separate from
the archives so they cannot make an otherwise identical build nondeterministic.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import mimetypes
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Mapping
import zipfile


COMPONENT_ID = "ct.penta.os-v1"
REGISTRY_ID = "crownthrive.penta.os-v1"
VERSION = "1.5.0"
PACKAGE_NAME = f"penta-os-v1-{VERSION}"
LOCAL_SOURCE_REVISION = "UNBOUND_LOCAL_BUILD"
LICENSE_ID = "LicenseRef-CrownThrive-All-Rights-Reserved"
BASE_SOURCE_FILES = (
    ".github/workflows/penta-os-v1.yml",
    "LICENSE",
    "PENTA-FAMILY-REGISTRY.md",
    "automation/penta-os-v1.mdx",
    "changelog/penta-os-v1-5-0-production-build-2026-08-26.md",
    "data/penta/family.registry.json",
    "data/penta/os-v1.discoveries.json",
    "data/penta/os-v1.registry.json",
    "developers/manifests/penta-os-v1.v1.json",
    "developers/manifests/penta-runtime-suite.v1.json",
    "docs/versioning/VERSION_REGISTRY.json",
    "releases/penta-os-v1.5.0/MANIFEST.json",
    "releases/penta-os-v1.5.0/RELEASE_NOTES.md",
    "runtime/penta_os_v1.py",
    "schemas/penta/os-v1-registry.schema.json",
    "scripts/build_penta_os_v1.py",
    "scripts/package_penta_os_v1.py",
    "tests/test_penta_os_v1.py",
)
REQUIRED_DECLARED_ASSETS = {
    ".github/workflows/penta-os-v1.yml",
    "automation/penta-os-v1.mdx",
    "data/penta/os-v1.discoveries.json",
    "data/penta/os-v1.operation-policies.json",
    "data/penta/os-v1.registry.json",
    "runtime/penta_os_v1.py",
    "schemas/penta/os-v1-batch-plan.schema.json",
    "schemas/penta/os-v1-plan.schema.json",
    "schemas/penta/os-v1-registry.schema.json",
    "schemas/penta/os-v1-verification-receipt.schema.json",
    "scripts/build_penta_os_v1.py",
    "scripts/package_penta_os_v1.py",
    "tests/test_penta_os_v1.py",
}
EXPECTED_ADDRESSABLE_OPERATIONS = [
    "describe",
    "status",
    "readiness",
    "validate",
    "verify",
    "plan",
    "dispatch",
]
EXPECTED_RELEASE_IDENTITY = {
    "schema": "crownthrive.penta.os-v1.release-manifest.v1",
    "release_id": "ct.penta.os-v1.release.1.5.0",
    "component_id": COMPONENT_ID,
    "canonical_name": "Penta OS V1.5",
    "version": VERSION,
    "version_scheme": "semver",
    "compatibility_line": "1.x",
    "supersedes": "1.0.0",
    "tag": "penta-os-v1.5.0",
    "release_state": "built_unreleased",
    "certification_state": "HOLD",
    "lifecycle_intent": "publish_only_after_all_exact_head_and_provider_readback_gates_pass",
}
EXPECTED_RELEASE_SOURCE = {
    "repository": "crownthrive1/CrownThrive-OS",
    "exact_commit_sha_required": True,
    "registry_ref": "data/penta/os-v1.registry.json",
    "software_manifest_ref": "developers/manifests/penta-os-v1.v1.json",
    "package_builder_ref": "scripts/package_penta_os_v1.py",
}
EXPECTED_RELEASE_ARTIFACTS = [
    f"{PACKAGE_NAME}.zip",
    f"{PACKAGE_NAME}.tar.gz",
    f"{PACKAGE_NAME}.sha256",
    f"{PACKAGE_NAME}.build.json",
    f"{PACKAGE_NAME}.verification.json",
]
MEDIA_TYPES = {
    ".json": "application/json",
    ".md": "text/markdown",
    ".mdx": "text/markdown",
    ".py": "text/x-python",
    ".yml": "application/yaml",
    ".yaml": "application/yaml",
}


class PackageError(ValueError):
    """Raised when package inputs or generated artifacts fail closed."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha1_digest(data: bytes) -> str:
    # SPDX 2.3 defines its package verification code in terms of SHA-1 file
    # digests. Release integrity continues to use SHA-256 everywhere else.
    return hashlib.sha1(data, usedforsecurity=False).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PackageError(f"JSON root must be an object: {path}")
    return value


def safe_relative_path(value: str) -> str:
    if not value or "\\" in value or "\x00" in value:
        raise PackageError(f"unsafe package path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PackageError(f"unsafe package path: {value!r}")
    normalized = path.as_posix()
    if normalized != value:
        raise PackageError(f"non-canonical package path: {value!r}")
    return normalized


def source_path(root: Path, relative: str) -> Path:
    relative = safe_relative_path(relative)
    root = root.resolve()
    path = root.joinpath(*PurePosixPath(relative).parts)
    if path.is_symlink():
        raise PackageError(f"symlink package input is prohibited: {relative}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise PackageError(f"required package source missing: {relative}") from exc
    if resolved != root and root not in resolved.parents:
        raise PackageError(f"package input escapes repository root: {relative}")
    if not resolved.is_file():
        raise PackageError(f"package input is not a regular file: {relative}")
    return resolved


def require_nonempty_unique_strings(value: Any, field: str) -> None:
    if (
        not isinstance(value, list)
        or not value
        or any(type(item) is not str or not item.strip() for item in value)
        or len(value) != len(set(value))
    ):
        raise PackageError(f"release manifest {field} must be a nonempty unique string list")


def validate_release_manifest(release: Mapping[str, Any]) -> None:
    """Validate the immutable V1.5 release boundary before packaging."""
    for field, expected in EXPECTED_RELEASE_IDENTITY.items():
        observed = release.get(field)
        if type(observed) is not type(expected) or observed != expected:
            raise PackageError(
                f"release manifest {field} drift: expected {expected!r}, got {observed!r}"
            )

    if "target_ref" not in release or release["target_ref"] is not None:
        raise PackageError("release manifest target_ref must remain null before exact provider readback")

    source = release.get("source")
    if not isinstance(source, dict) or canonical_json(source) != canonical_json(EXPECTED_RELEASE_SOURCE):
        raise PackageError("release manifest source repository/ref contract drift")

    artifacts = release.get("expected_artifacts")
    if not isinstance(artifacts, list) or artifacts != EXPECTED_RELEASE_ARTIFACTS:
        raise PackageError(
            "release manifest expected_artifacts must be the exact five governed artifact names"
        )

    provider_readback = release.get("provider_readback")
    if not isinstance(provider_readback, dict):
        raise PackageError("release manifest provider_readback must be an object")
    if provider_readback.get("state") != "HOLD":
        raise PackageError("release manifest provider_readback.state must remain HOLD")
    require_nonempty_unique_strings(
        provider_readback.get("required"), "provider_readback.required"
    )

    certification_receipt = release.get("certification_receipt")
    if not isinstance(certification_receipt, dict):
        raise PackageError("release manifest certification_receipt must be an object")
    if certification_receipt.get("state") != "NOT_PRODUCED":
        raise PackageError("release manifest certification_receipt.state must remain NOT_PRODUCED")
    if certification_receipt.get("separate_from_deterministic_archives") is not True:
        raise PackageError(
            "release manifest certification receipt must remain separate from deterministic archives"
        )
    require_nonempty_unique_strings(
        certification_receipt.get("required_bindings"),
        "certification_receipt.required_bindings",
    )
    require_nonempty_unique_strings(release.get("release_blockers"), "release_blockers")


def component_metadata(root: Path) -> dict[str, Any]:
    registry = read_json(root / "data/penta/os-v1.registry.json")
    software = read_json(root / "developers/manifests/penta-os-v1.v1.json")
    versions = read_json(root / "docs/versioning/VERSION_REGISTRY.json")
    release = read_json(root / "releases/penta-os-v1.5.0/MANIFEST.json")
    validate_release_manifest(release)
    components = {
        item.get("component_id"): item
        for item in versions.get("components", [])
        if isinstance(item, dict)
    }
    version_entry = components.get(COMPONENT_ID)
    if not isinstance(version_entry, dict):
        raise PackageError(f"version registry lacks {COMPONENT_ID}")

    observed = {
        "registry_id": registry.get("registry_id"),
        "registry_version": registry.get("version"),
        "software_component_id": software.get("component_id"),
        "software_version": software.get("version"),
        "version_registry_component_version": version_entry.get("version"),
    }
    required = {
        "registry_id": REGISTRY_ID,
        "registry_version": VERSION,
        "software_component_id": COMPONENT_ID,
        "software_version": VERSION,
        "version_registry_component_version": VERSION,
    }
    if observed != required:
        raise PackageError(f"Penta OS V1.5 version identity drift: {observed!r}")
    if registry.get("release_state") != "built_unreleased":
        raise PackageError("source registry must remain built_unreleased until provider release readback")
    if software.get("build_state") != "built_unreleased" or software.get("certification_state") != "HOLD":
        raise PackageError("software manifest must remain built_unreleased / HOLD")
    declared_assets = software.get("assets")
    if not isinstance(declared_assets, list) or any(not isinstance(item, str) for item in declared_assets):
        raise PackageError("software manifest assets must be a string list")
    duplicate_assets = sorted({item for item in declared_assets if declared_assets.count(item) > 1})
    if duplicate_assets:
        raise PackageError(f"software manifest contains duplicate assets: {duplicate_assets}")
    missing_declared_assets = sorted(REQUIRED_DECLARED_ASSETS - set(declared_assets))
    if missing_declared_assets:
        raise PackageError(f"software manifest omits required component assets: {missing_declared_assets}")
    if "scripts/validate_docs.py" in declared_assets:
        raise PackageError("repository-context docs validator must not be declared as a distributable component asset")
    completeness = software.get("completeness", {})
    if completeness.get("universal_addressable_operations") != EXPECTED_ADDRESSABLE_OPERATIONS:
        raise PackageError("software manifest universal operation declaration drift")
    systems_sha256 = registry.get("systems_sha256")
    if not isinstance(systems_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", systems_sha256):
        raise PackageError("registry systems_sha256 is missing or malformed")
    source_digests = registry.get("source_digests_sha256")
    if not isinstance(source_digests, dict) or not source_digests:
        raise PackageError("registry source digest closure is missing")
    return {
        "registry": registry,
        "software": software,
        "declared_software_assets": sorted(declared_assets),
        "version_entry": version_entry,
        "release": release,
        "systems_sha256": systems_sha256,
        "source_digests_sha256": source_digests,
        "effective_date": registry.get("effective_date"),
    }


def resolve_source_files(root: Path, metadata: Mapping[str, Any]) -> tuple[str, ...]:
    paths = {safe_relative_path(path) for path in BASE_SOURCE_FILES}
    registry = metadata["registry"]
    software = metadata["software"]

    for relative in metadata["source_digests_sha256"]:
        paths.add(safe_relative_path(str(relative)))
    for relative in software.get("assets", []):
        if not isinstance(relative, str):
            raise PackageError("software manifest assets must be string paths")
        paths.add(safe_relative_path(relative))

    family_relative = "data/penta/family.registry.json"
    family = read_json(source_path(root, family_relative))
    for item in family.get("catalogs", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise PackageError("Penta Family catalog references must contain string paths")
        paths.add(safe_relative_path(item["path"]))

    schema_ref = registry.get("$schema")
    if isinstance(schema_ref, str):
        schema_path = (PurePosixPath("data/penta") / PurePosixPath(schema_ref)).as_posix()
        collapsed: list[str] = []
        for part in PurePosixPath(schema_path).parts:
            if part == "..":
                if not collapsed:
                    raise PackageError("registry schema reference escapes repository root")
                collapsed.pop()
            elif part != ".":
                collapsed.append(part)
        paths.add(safe_relative_path("/".join(collapsed)))

    # Read back every resolved input and verify the exact source-digest claims
    # embedded in the generated registry before packaging it.
    for relative in sorted(paths):
        source_path(root, relative)
    for relative, expected in sorted(metadata["source_digests_sha256"].items()):
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise PackageError(f"malformed source digest for {relative}")
        actual = digest(source_path(root, relative).read_bytes())
        if actual != expected:
            raise PackageError(f"registry source drift: {relative}; expected {expected}, got {actual}")
    return tuple(sorted(paths))


def collect(root: Path, metadata: Mapping[str, Any] | None = None) -> dict[str, bytes]:
    root = root.resolve()
    metadata = dict(metadata or component_metadata(root))
    return {
        relative: source_path(root, relative).read_bytes()
        for relative in resolve_source_files(root, metadata)
    }


def media_type(path: str) -> str:
    suffix = PurePosixPath(path).suffix.casefold()
    return MEDIA_TYPES.get(suffix) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def file_records(files: Mapping[str, bytes]) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "media_type": media_type(path),
            "classification": "PUBLIC_SAFE",
            "rights_state": "ALL_RIGHTS_RESERVED",
            "sha256": digest(data),
            "bytes": len(data),
        }
        for path, data in sorted(files.items())
    ]


def payload_digest(files: Mapping[str, bytes]) -> str:
    return digest(canonical_json(file_records(files)))


def package_verification_code(files: Mapping[str, bytes]) -> str:
    file_sha1_values = sorted(sha1_digest(data) for data in files.values())
    return hashlib.sha1("".join(file_sha1_values).encode("ascii"), usedforsecurity=False).hexdigest()


def normalize_source_revision(value: str | None) -> str:
    revision = value or LOCAL_SOURCE_REVISION
    if revision != LOCAL_SOURCE_REVISION and not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise PackageError("source revision must be an exact 40-character lowercase Git commit SHA")
    return revision


def manifest(files: Mapping[str, bytes], metadata: Mapping[str, Any], source_revision: str) -> dict[str, Any]:
    return {
        "schema": "crownthrive.penta.os-v1.package-manifest.v1",
        "component_id": COMPONENT_ID,
        "name": "Penta OS V1.5",
        "version": VERSION,
        "source_revision": source_revision,
        "registry_id": REGISTRY_ID,
        "registry_systems_sha256": metadata["systems_sha256"],
        "source_digests_sha256": metadata["source_digests_sha256"],
        "declared_software_assets": metadata["declared_software_assets"],
        "payload_sha256": payload_digest(files),
        "release_state": "built_unreleased",
        "production_certification": "HOLD",
        "classification": "PUBLIC_SAFE",
        "rights_state": "ALL_RIGHTS_RESERVED",
        "distribution_policy": "Publicly viewable governed reference package; no general license is granted.",
        "scope": "Registry, dependency closure, deterministic verification receipts, batch planning, documentation projection, fail-closed dispatch handoff, and reproducible public-safe source distribution.",
        "authority_invariant": "This package does not grant provider credentials, provider-write authority, D3 approval, member maturity promotion, release state, or production certification.",
        "generated_files_excluded_from_payload_digest": ["MANIFEST.json", "SBOM.spdx.json"],
        "repository_prepackage_gates": ["scripts/validate_docs.py"],
        "distributable_replay_scope": "Penta OS registry generation, runtime validation, schemas, and focused component tests; full repository documentation-governance replay remains a repository-context gate.",
        "files": file_records(files),
    }


def spdx(files: Mapping[str, bytes], metadata: Mapping[str, Any], source_revision: str) -> dict[str, Any]:
    namespace_digest = digest(canonical_json({
        "source_revision": source_revision,
        "payload_sha256": payload_digest(files),
    }))
    package_id = "SPDXRef-Package-PentaOSV1"
    document_id = "SPDXRef-DOCUMENT"
    package_verification = {
        "packageVerificationCodeValue": package_verification_code(files),
        "packageVerificationCodeExcludedFiles": ["./MANIFEST.json", "./SBOM.spdx.json"],
    }
    file_entries = []
    contains = []
    for path, data in sorted(files.items()):
        file_id = "SPDXRef-File-" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
        file_entries.append({
            "fileName": f"./{path}",
            "SPDXID": file_id,
            "checksums": [
                {"algorithm": "SHA1", "checksumValue": sha1_digest(data)},
                {"algorithm": "SHA256", "checksumValue": digest(data)},
            ],
            "licenseConcluded": LICENSE_ID,
            "licenseInfoInFiles": [LICENSE_ID],
            "copyrightText": "Copyright © 2026 CrownThrive, LLC",
        })
        contains.append({
            "spdxElementId": package_id,
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": file_id,
        })
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": document_id,
        "name": PACKAGE_NAME,
        "documentNamespace": f"https://crownthrive.com/spdx/{PACKAGE_NAME}/{namespace_digest}",
        "documentDescribes": [package_id],
        "creationInfo": {
            "created": f"{metadata['effective_date']}T00:00:00Z",
            "creators": ["Organization: CrownThrive, LLC", "Tool: package_penta_os_v1.py/1.5.0"],
        },
        "hasExtractedLicensingInfos": [{
            "licenseId": LICENSE_ID,
            "name": "CrownThrive All Rights Reserved",
            "extractedText": "All Rights Reserved. Public visibility and package access grant no general copyright, patent, trademark, machine-use, redistribution, derivative-work, or commercial-use license. See ./LICENSE for the complete controlling notice.",
        }],
        "packages": [{
            "name": "Penta OS V1.5",
            "SPDXID": package_id,
            "versionInfo": VERSION,
            "downloadLocation": "NOASSERTION",
            "sourceInfo": f"Exact repository source revision: {source_revision}",
            "filesAnalyzed": True,
            "packageVerificationCode": package_verification,
            "licenseConcluded": LICENSE_ID,
            "licenseDeclared": LICENSE_ID,
            "copyrightText": "Copyright © 2026 CrownThrive, LLC",
        }],
        "files": file_entries,
        "relationships": [{
            "spdxElementId": document_id,
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": package_id,
        }, *contains],
    }


def archive_files(root: Path, source_revision: str = LOCAL_SOURCE_REVISION) -> dict[str, bytes]:
    root = root.resolve()
    source_revision = normalize_source_revision(source_revision)
    metadata = component_metadata(root)
    files = collect(root, metadata)
    package_manifest = manifest(files, metadata, source_revision)
    package_sbom = spdx(files, metadata, source_revision)
    return {
        **files,
        "MANIFEST.json": (json.dumps(package_manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "SBOM.spdx.json": (json.dumps(package_sbom, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }


def write_zip(path: Path, files: Mapping[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, data in sorted(files.items()):
            relative = safe_relative_path(relative)
            info = zipfile.ZipInfo(f"{PACKAGE_NAME}/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if relative.endswith(".py") else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def write_tar_gz(path: Path, files: Mapping[str, bytes]) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for relative, data in sorted(files.items()):
            relative = safe_relative_path(relative)
            info = tarfile.TarInfo(f"{PACKAGE_NAME}/{relative}")
            info.size = len(data)
            info.mode = 0o755 if relative.endswith(".py") else 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.pax_headers = {}
            archive.addfile(info, io.BytesIO(data))
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as compressed:
            compressed.write(buffer.getvalue())


def artifact_paths(output: Path) -> dict[str, Path]:
    return {
        "zip": output / f"{PACKAGE_NAME}.zip",
        "tar_gz": output / f"{PACKAGE_NAME}.tar.gz",
        "checksums": output / f"{PACKAGE_NAME}.sha256",
        "build": output / f"{PACKAGE_NAME}.build.json",
    }


def build(root: Path, output: Path, source_revision: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    source_revision = normalize_source_revision(source_revision)
    output.mkdir(parents=True, exist_ok=True)
    files = archive_files(root, source_revision)
    paths = artifact_paths(output)
    write_zip(paths["zip"], files)
    write_tar_gz(paths["tar_gz"], files)
    archive_artifacts = [paths["zip"], paths["tar_gz"]]
    checksums = "".join(f"{digest(path.read_bytes())}  {path.name}\n" for path in archive_artifacts)
    paths["checksums"].write_text(checksums, encoding="utf-8")
    result = {
        "schema": "crownthrive.penta.os-v1.build-result.v1",
        "component_id": COMPONENT_ID,
        "version": VERSION,
        "source_revision": source_revision,
        "registry_systems_sha256": component_metadata(root)["systems_sha256"],
        "payload_sha256": json.loads(files["MANIFEST.json"])["payload_sha256"],
        "release_state": "built_unreleased",
        "production_certification": "HOLD",
        "artifacts": [
            {"path": path.name, "sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}
            for path in (*archive_artifacts, paths["checksums"])
        ],
    }
    paths["build"].write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def archive_relative(member_name: str) -> str:
    prefix = f"{PACKAGE_NAME}/"
    if not member_name.startswith(prefix):
        raise PackageError(f"archive member is outside package root: {member_name}")
    return safe_relative_path(member_name[len(prefix):])


def read_zip_files(path: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    raise PackageError(f"unexpected ZIP directory entry: {info.filename}")
                if info.flag_bits & 0x1:
                    raise PackageError(f"encrypted ZIP entry is prohibited: {info.filename}")
                relative = archive_relative(info.filename)
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode) or (mode and not stat.S_ISREG(mode)):
                    raise PackageError(f"non-regular ZIP entry is prohibited: {info.filename}")
                if relative in result:
                    raise PackageError(f"duplicate ZIP member: {relative}")
                result[relative] = archive.read(info)
    except (OSError, zipfile.BadZipFile) as exc:
        raise PackageError(f"invalid ZIP artifact {path}: {exc}") from exc
    return result


def read_tar_files(path: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    try:
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile() or member.issym() or member.islnk():
                    raise PackageError(f"non-regular TAR entry is prohibited: {member.name}")
                relative = archive_relative(member.name)
                if relative in result:
                    raise PackageError(f"duplicate TAR member: {relative}")
                stream = archive.extractfile(member)
                if stream is None:
                    raise PackageError(f"cannot read TAR member: {member.name}")
                result[relative] = stream.read()
    except (OSError, tarfile.TarError) as exc:
        raise PackageError(f"invalid TAR.GZ artifact {path}: {exc}") from exc
    return result


def parse_checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PackageError(f"cannot read checksum file {path}: {exc}") from exc
    for line in lines:
        match = re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9._-]+)", line)
        if not match or match.group(2) in checksums:
            raise PackageError(f"invalid checksum line: {line!r}")
        checksums[match.group(2)] = match.group(1)
    return checksums


def validate_embedded_metadata(files: Mapping[str, bytes], source_revision: str) -> None:
    try:
        package_manifest = json.loads(files["MANIFEST.json"])
        package_sbom = json.loads(files["SBOM.spdx.json"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise PackageError(f"archive metadata is missing or malformed: {exc}") from exc
    payload = {path: data for path, data in files.items() if path not in {"MANIFEST.json", "SBOM.spdx.json"}}
    if package_manifest.get("version") != VERSION or package_manifest.get("source_revision") != source_revision:
        raise PackageError("embedded package manifest version/source binding drift")
    if package_manifest.get("payload_sha256") != payload_digest(payload):
        raise PackageError("embedded package payload digest mismatch")
    if package_manifest.get("files") != file_records(payload):
        raise PackageError("embedded package file manifest mismatch")
    try:
        software_manifest = json.loads(payload["developers/manifests/penta-os-v1.v1.json"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise PackageError(f"embedded software manifest is missing or malformed: {exc}") from exc
    declared_assets = software_manifest.get("assets")
    if not isinstance(declared_assets, list) or any(asset not in payload for asset in declared_assets):
        raise PackageError("declared software assets are not closed by the package payload")
    if package_manifest.get("declared_software_assets") != sorted(declared_assets):
        raise PackageError("package/software declared asset closure mismatch")
    if "scripts/validate_docs.py" in payload:
        raise PackageError("repository-context docs validator must not ship as a self-contained package asset")
    packages = package_sbom.get("packages", [])
    if len(packages) != 1 or packages[0].get("licenseDeclared") != LICENSE_ID:
        raise PackageError("SPDX package license is not the governed all-rights-reserved LicenseRef")
    verification = packages[0].get("packageVerificationCode", {})
    if verification.get("packageVerificationCodeValue") != package_verification_code(payload):
        raise PackageError("SPDX package verification code mismatch")
    extracted = package_sbom.get("hasExtractedLicensingInfos", [])
    if not any(item.get("licenseId") == LICENSE_ID for item in extracted if isinstance(item, dict)):
        raise PackageError("SPDX extracted all-rights-reserved license definition is missing")


def materialize_safely(files: Mapping[str, bytes], destination: Path) -> Path:
    package_root = destination / PACKAGE_NAME
    for relative, data in sorted(files.items()):
        relative = safe_relative_path(relative)
        target = package_root.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return package_root


def smoke_validate(files: Mapping[str, bytes], label: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"penta-os-v1-{label}-") as temporary:
        package_root = materialize_safely(files, Path(temporary))
        builder_command = [sys.executable, str(package_root / "scripts/build_penta_os_v1.py"), "--root", str(package_root), "--check"]
        builder = subprocess.run(builder_command, text=True, capture_output=True, check=False, timeout=60)
        if builder.returncode != 0:
            detail = (builder.stderr or builder.stdout).strip()
            raise PackageError(f"{label} extracted registry generation check failed: {detail}")

        command = [sys.executable, str(package_root / "runtime/penta_os_v1.py"), "--root", str(package_root), "validate"]
        completed = subprocess.run(command, text=True, capture_output=True, check=False, timeout=60)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise PackageError(f"{label} extracted runtime validation failed: {detail}")
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise PackageError(f"{label} runtime validation did not emit JSON") from exc
        if result.get("valid") is not True or result.get("version") != VERSION:
            raise PackageError(f"{label} extracted runtime validation returned unexpected state")

        tests_command = [sys.executable, "-m", "unittest", "tests.test_penta_os_v1", "-v"]
        tests = subprocess.run(tests_command, cwd=package_root, text=True, capture_output=True, check=False, timeout=120)
        test_output = "\n".join(part for part in (tests.stdout, tests.stderr) if part)
        if tests.returncode != 0:
            raise PackageError(f"{label} extracted focused tests failed: {test_output.strip()}")
        match = re.search(r"Ran (\d+) tests?", test_output)
        skipped_match = re.search(r"skipped=(\d+)", test_output)
        if not match:
            raise PackageError(f"{label} extracted focused test count is unavailable")
        tests_run = int(match.group(1))
        tests_skipped = int(skipped_match.group(1)) if skipped_match else 0
        if tests_skipped:
            raise PackageError(f"{label} extracted focused tests skipped {tests_skipped} test(s)")
        return {
            "archive": label,
            "status": "PASS",
            "registry_generation_check": "PASS",
            "member_count": result.get("member_count"),
            "systems_sha256": result.get("systems_sha256"),
            "focused_tests_run": tests_run,
            "focused_tests_passed": tests_run,
            "focused_tests_skipped": tests_skipped,
        }


def verify_output(root: Path, output: Path, compare_output: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    paths = artifact_paths(output)
    for path in paths.values():
        if not path.is_file():
            raise PackageError(f"required build artifact missing: {path}")
    build_result = read_json(paths["build"])
    source_revision = normalize_source_revision(build_result.get("source_revision"))
    if build_result.get("version") != VERSION or build_result.get("release_state") != "built_unreleased":
        raise PackageError("build result version or release state drift")

    checksum_claims = parse_checksums(paths["checksums"])
    expected_checksum_names = {paths["zip"].name, paths["tar_gz"].name}
    if set(checksum_claims) != expected_checksum_names:
        raise PackageError("checksum file must cover exactly the ZIP and TAR.GZ artifacts")
    for key in ("zip", "tar_gz"):
        path = paths[key]
        if checksum_claims[path.name] != digest(path.read_bytes()):
            raise PackageError(f"checksum verification failed: {path.name}")

    artifact_records = {
        item.get("path"): item
        for item in build_result.get("artifacts", [])
        if isinstance(item, dict)
    }
    for key in ("zip", "tar_gz", "checksums"):
        path = paths[key]
        record = artifact_records.get(path.name)
        if not record or record.get("sha256") != digest(path.read_bytes()) or record.get("bytes") != path.stat().st_size:
            raise PackageError(f"build-result artifact binding mismatch: {path.name}")

    zip_files = read_zip_files(paths["zip"])
    tar_files = read_tar_files(paths["tar_gz"])
    if zip_files != tar_files:
        raise PackageError("ZIP and TAR.GZ payloads are not content-equivalent")
    expected_files = archive_files(root, source_revision)
    if zip_files != expected_files:
        raise PackageError("archive payload does not match the exact current source closure")
    validate_embedded_metadata(zip_files, source_revision)

    compared = False
    if compare_output is not None:
        other_paths = artifact_paths(compare_output)
        for key in ("zip", "tar_gz", "checksums", "build"):
            other = other_paths[key]
            if not other.is_file() or paths[key].read_bytes() != other.read_bytes():
                raise PackageError(f"independent builds are not byte-identical: {paths[key].name}")
        compared = True

    smoke = [smoke_validate(zip_files, "zip"), smoke_validate(tar_files, "tar-gz")]
    return {
        "schema": "crownthrive.penta.os-v1.package-verification.v1",
        "component_id": COMPONENT_ID,
        "version": VERSION,
        "source_revision": source_revision,
        "status": "PASS",
        "release_state": "built_unreleased",
        "production_certification": "HOLD",
        "source_file_count": len(zip_files) - 2,
        "archive_file_count": len(zip_files),
        "checksums_verified": True,
        "safe_regular_files_only": True,
        "zip_tar_content_equivalent": True,
        "independent_builds_byte_identical": compared,
        "spdx_package_verification_code_verified": True,
        "declared_asset_closure_verified": True,
        "extracted_package_validation": smoke,
        "artifacts": build_result["artifacts"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision")
    parser.add_argument("--verify", action="store_true", help="verify an existing output directory instead of rebuilding it")
    parser.add_argument("--compare-output", type=Path, help="second independently built output directory for byte comparison")
    args = parser.parse_args()
    if args.verify:
        if args.source_revision:
            parser.error("--source-revision is read from the build result during --verify")
        result = verify_output(args.root, args.output, args.compare_output)
    else:
        if args.compare_output:
            parser.error("--compare-output requires --verify")
        result = build(args.root, args.output, args.source_revision)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
