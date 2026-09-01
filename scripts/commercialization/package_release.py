#!/usr/bin/env python3
"""Create deterministic COS commercialization release artifacts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import stat
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Iterable, Sequence

ALLOWED_PREFIXES = (
    "commercialization/",
    "scripts/commercialization/",
    "tests/test_cos_commercialization_",
    "developers/manifests/cos-v1-commercialization-fabric.v1.json",
    "penta/continuity/receipts/20260830-cos-v1-commercialization-fabric-candidate-v1.json",
    ".github/workflows/cos-v1-commercialization-fabric.yml",
    ".github/release-requests/cos-commercialization-fabric-v1.0.0-rc.1.json",
    "releases/cos-commercialization-fabric-v1.0.0-rc.1/",
)
BLOCKED_PARTS = {".git", ".env", "node_modules", "__pycache__", "dist"}
SECRET_PATTERNS = (
    re.compile("-----BEGIN " + r"(?:(?:RSA|EC|OPENSSH) )?PRIVATE KEY-----"),
    re.compile("sk" + r"_live_[A-Za-z0-9]{16,}"),
    re.compile("gh" + r"p_[A-Za-z0-9]{20,}"),
)
CATALOG_ATTACHMENTS = {
    "catalog.json": "CATALOG.json",
    "offers.json": "OFFERS.json",
    "install-index.json": "INSTALL_INDEX.json",
    "mesh-routing.json": "MESH_ROUTING.json",
    "readiness.json": "READINESS.json",
}
DEFAULT_RELEASE_NOTES = Path("releases/cos-commercialization-fabric-v1.0.0-rc.1/RELEASE_NOTES.md")


class PackageError(RuntimeError):
    """Raised when a package violates release controls."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def allowed(relative: str) -> bool:
    return any(relative == prefix or relative.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def collect_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(repo_root).as_posix()
        if any(part in BLOCKED_PARTS for part in path.parts):
            continue
        if allowed(relative):
            files.append(path)
    if not files:
        raise PackageError("no allowlisted commercialization files found")
    return sorted(files, key=lambda item: item.relative_to(repo_root).as_posix())


def collect_directory_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if not files:
        raise PackageError(f"directory contains no files: {root}")
    return files


def scan_text_secret(path: Path, content: bytes) -> None:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise PackageError(f"secret-like material matched {pattern.pattern!r} in {path}")


def normalized_mode(path: Path) -> int:
    current = path.stat().st_mode
    return 0o755 if current & stat.S_IXUSR else 0o644


def build_zip(repo_root: Path, files: Sequence[Path]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(repo_root).as_posix()
            content = path.read_bytes()
            scan_text_secret(path, content)
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = normalized_mode(path) << 16
            archive.writestr(info, content)
    return buffer.getvalue()


def build_tar_gz(repo_root: Path, files: Sequence[Path]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in files:
            relative = path.relative_to(repo_root).as_posix()
            content = path.read_bytes()
            scan_text_secret(path, content)
            info = tarfile.TarInfo(relative)
            info.size = len(content)
            info.mode = normalized_mode(path)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            archive.addfile(info, io.BytesIO(content))
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0, compresslevel=9) as gz:
        gz.write(raw.getvalue())
    return compressed.getvalue()


def dump_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def create_release(
    repo_root: Path,
    output: Path,
    version: str,
    source_sha: str,
    catalog_dir: Path | None = None,
    release_notes: Path | None = None,
) -> dict[str, Any]:
    if not source_sha or source_sha == "UNKNOWN":
        raise PackageError("exact source SHA is required for a release package")
    files = collect_files(repo_root)
    output.mkdir(parents=True, exist_ok=True)
    stem = f"CrownThrive-COS-Commercialization-v{version}"
    zip_path = output / f"{stem}.zip"
    tar_path = output / f"{stem}.tar.gz"
    zip_bytes = build_zip(repo_root, files)
    tar_bytes = build_tar_gz(repo_root, files)
    zip_path.write_bytes(zip_bytes)
    tar_path.write_bytes(tar_bytes)

    attachment_paths: list[Path] = []
    notes_source = release_notes or (repo_root / DEFAULT_RELEASE_NOTES)
    if notes_source.exists():
        notes_content = notes_source.read_bytes()
        scan_text_secret(notes_source, notes_content)
        notes_target = output / "RELEASE_NOTES.md"
        notes_target.write_bytes(notes_content)
        attachment_paths.append(notes_target)
    elif release_notes is not None:
        raise PackageError(f"release notes not found: {notes_source}")

    if catalog_dir is not None:
        if not catalog_dir.is_dir():
            raise PackageError(f"catalog directory not found: {catalog_dir}")
        for source_name, target_name in CATALOG_ATTACHMENTS.items():
            source = catalog_dir / source_name
            if not source.is_file():
                raise PackageError(f"required catalog attachment not found: {source}")
            content = source.read_bytes()
            scan_text_secret(source, content)
            target = output / target_name
            target.write_bytes(content)
            attachment_paths.append(target)

        adapter_root = catalog_dir / "registry-adapters"
        if adapter_root.exists():
            adapter_files = collect_directory_files(adapter_root)
            adapter_zip = output / "REGISTRY_ADAPTERS.zip"
            adapter_tar = output / "REGISTRY_ADAPTERS.tar.gz"
            adapter_zip.write_bytes(build_zip(adapter_root, adapter_files))
            adapter_tar.write_bytes(build_tar_gz(adapter_root, adapter_files))
            attachment_paths.extend([adapter_zip, adapter_tar])

    file_records = []
    for path in files:
        relative = path.relative_to(repo_root).as_posix()
        file_records.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
                "mode": oct(normalized_mode(path)),
            }
        )

    manifest = {
        "schema_version": "1.0.0",
        "release_id": f"ct.cos.commercialization-fabric.v{version}",
        "component_id": "ct.cos.commercialization-fabric",
        "version": version,
        "source_sha": source_sha,
        "release_state": "BUILT_UNPUBLISHED",
        "publication_authorized": False,
        "files": file_records,
        "artifacts": [
            {
                "name": path.name,
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
                "artifact_class": (
                    "source_archive"
                    if path in {zip_path, tar_path}
                    else "release_evidence_or_catalog"
                ),
            }
            for path in [zip_path, tar_path, *attachment_paths]
        ],
        "required_remaining_gates": [
            "independent exact-source verification",
            "PentaRelease publication",
            "provider asset readback",
            "registry-specific credentials and protected environments",
        ],
    }
    manifest_path = output / "MANIFEST.json"
    dump_json(manifest_path, manifest)

    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": stem,
        "documentNamespace": f"https://crownthrive.com/spdx/{source_sha}/{version}",
        "creationInfo": {
            "creators": ["Organization: CrownThrive, LLC", "Tool: package_release.py"],
            "created": "1970-01-01T00:00:00Z",
        },
        "packages": [
            {
                "name": "CrownThrive COS Commercialization Fabric",
                "SPDXID": "SPDXRef-Package",
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": True,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "LicenseRef-CrownThrive-Reserved",
                "copyrightText": "Copyright CrownThrive, LLC",
            }
        ],
        "files": [
            {
                "fileName": item["path"],
                "SPDXID": f"SPDXRef-File-{index}",
                "checksums": [{"algorithm": "SHA256", "checksumValue": item["sha256"]}],
                "licenseConcluded": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
            for index, item in enumerate(file_records, start=1)
        ],
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": "SPDXRef-Package",
            }
        ],
    }
    dump_json(output / "SBOM.spdx.json", sbom)

    provenance = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": path.name, "digest": {"sha256": sha256_file(path)}}
            for path in [zip_path, tar_path, *attachment_paths]
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://crownthrive.com/build-types/cos-commercialization/v1",
                "externalParameters": {"version": version, "source_sha": source_sha},
                "resolvedDependencies": [
                    {"uri": "git+https://github.com/crownthrive1/CrownThrive-OS", "digest": {"gitCommit": source_sha}}
                ],
            },
            "runDetails": {
                "builder": {"id": "ct.pentarelease.commercialization-builder.v1"},
                "metadata": {"invocationId": source_sha, "startedOn": None, "finishedOn": None},
            },
        },
    }
    dump_json(output / "PROVENANCE.intoto.json", provenance)

    checksum_paths = [
        zip_path,
        tar_path,
        *attachment_paths,
        manifest_path,
        output / "SBOM.spdx.json",
        output / "PROVENANCE.intoto.json",
    ]
    checksum_lines = [f"{sha256_file(path)}  {path.name}" for path in checksum_paths]
    (output / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return manifest


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-sha", default=os.environ.get("GITHUB_SHA", "UNKNOWN"))
    parser.add_argument("--catalog-dir", type=Path)
    parser.add_argument("--release-notes", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        manifest = create_release(
            args.repo_root.resolve(),
            args.output.resolve(),
            args.version,
            args.source_sha,
            args.catalog_dir.resolve() if args.catalog_dir else None,
            args.release_notes.resolve() if args.release_notes else None,
        )
    except PackageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"release_id": manifest["release_id"], "artifacts": len(manifest["artifacts"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
