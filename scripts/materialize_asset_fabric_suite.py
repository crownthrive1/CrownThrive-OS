#!/usr/bin/env python3
"""Safely materialize the signed CrownThrive Asset Fabric source bundle."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import pathlib
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "data/asset-fabric/source-bundle-chunks"
MANIFEST = ROOT / "data/asset-fabric/source-bundle-manifest.v1.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    encoded = b"".join((CHUNKS / name).read_bytes() for name in manifest["chunks"])
    if hashlib.sha256(encoded).hexdigest() != manifest["base64_sha256"]:
        raise SystemExit("bundle base64 digest mismatch")
    compressed = base64.b64decode(encoded)
    if hashlib.sha256(compressed).hexdigest() != manifest["tar_gzip_sha256"]:
        raise SystemExit("bundle tar.gz digest mismatch")
    with tarfile.open(fileobj=io.BytesIO(compressed), mode="r:gz") as archive:
        for member in archive.getmembers():
            target = (ROOT / member.name).resolve()
            if ROOT != target and ROOT not in target.parents:
                raise SystemExit(f"unsafe archive path: {member.name}")
        archive.extractall(ROOT)
    marker = ROOT / "data/asset-fabric/materialization-receipt.v1.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        "state": "materialized",
        "bundle_version": manifest["bundle_version"],
        "tar_gzip_sha256": manifest["tar_gzip_sha256"],
        "base64_sha256": manifest["base64_sha256"],
        "file_count": manifest["file_count"],
        "authoritative_asset_count_delta": 0,
        "checkout_enabled": False,
        "D3_auto": False,
        "history_policy": "append_or_supersede_never_silent_delete"
    }, indent=2) + "\n", encoding="utf-8")
    print(marker)


if __name__ == "__main__":
    main()
