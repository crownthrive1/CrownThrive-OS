#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

TAG_RE = re.compile(r"^v\d+(?:\.\d+){2,3}$")


def run(*args, check=True):
    p = subprocess.run(args, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(args)}\n{p.stderr}")
    return p


def run_bytes(*args):
    p = subprocess.run(args, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(args)}\n{p.stderr.decode(errors='replace')}")
    return p


def gh_json(*args):
    p = run("gh", *args)
    return json.loads(p.stdout)


def git_has(ref, path):
    return run("git", "cat-file", "-e", f"{ref}:{path}", check=False).returncode == 0


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def locate_package(tag):
    version = tag[1:]
    candidates = [f"releases/{tag}", f"releases/{version}"]
    for path in candidates:
        if git_has(tag, f"{path}/MANIFEST.json") and git_has(tag, f"{path}/RELEASE_NOTES.md"):
            return path
    return None


def build_artifacts(tag, package_path, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    src = outdir / "src"
    src.mkdir(parents=True, exist_ok=True)

    archive = run_bytes("git", "archive", "--format=tar", tag, package_path).stdout
    tar_path = outdir / "source.tar"
    tar_path.write_bytes(archive)
    with tarfile.open(tar_path, "r:") as tf:
        tf.extractall(src)

    package_dir = src / package_path
    if not package_dir.exists():
        raise RuntimeError(f"package extraction failed: {package_path}")

    safe = tag.replace("/", "-")
    zip_path = outdir / f"CrownThrive-OS-{safe}-package.zip"
    tgz_path = outdir / f"CrownThrive-OS-{safe}-package.tar.gz"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(package_dir.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(package_dir))

    with tarfile.open(tgz_path, "w:gz") as tf:
        for p in sorted(package_dir.rglob("*")):
            if p.is_file():
                tf.add(p, arcname=p.relative_to(package_dir))

    manifest = outdir / "MANIFEST.json"
    notes = outdir / "RELEASE_NOTES.md"
    shutil.copy2(package_dir / "MANIFEST.json", manifest)
    shutil.copy2(package_dir / "RELEASE_NOTES.md", notes)

    checksums = outdir / "SHA256SUMS"
    checksum_targets = [zip_path, tgz_path, manifest, notes]
    checksums.write_text(
        "".join(f"{sha256(p)}  {p.name}\n" for p in checksum_targets),
        encoding="utf-8",
    )

    return [zip_path, tgz_path, checksums, manifest, notes]


def release_view(tag):
    return gh_json(
        "release", "view", tag,
        "--json", "tagName,name,url,isDraft,isPrerelease,targetCommitish,assets",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repository", required=True)
    ap.add_argument("--policy", default=".pentarelease/policy.json")
    ap.add_argument("--output", required=True)
    ap.add_argument("--max-releases", type=int, default=20)
    ap.add_argument("--repair", action="store_true")
    args = ap.parse_args()

    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    cfg = policy.get("published_release_reconciliation", {})
    max_releases = int(cfg.get("max_releases", args.max_releases))
    required = cfg.get("required_assets") or [
        "CrownThrive-OS-{tag}-package.zip",
        "CrownThrive-OS-{tag}-package.tar.gz",
        "SHA256SUMS",
        "MANIFEST.json",
        "RELEASE_NOTES.md",
    ]

    releases = gh_json("api", f"/repos/{args.repository}/releases?per_page={max_releases}")
    governed = [
        r for r in releases
        if not r.get("draft") and TAG_RE.fullmatch(r.get("tag_name", ""))
    ]
    results = []

    for idx, release in enumerate(governed):
        tag = release["tag_name"]
        expected = [name.format(tag=tag.replace("/", "-")) for name in required]
        before_assets = {a["name"] for a in release.get("assets", [])}
        missing = [x for x in expected if x not in before_assets]
        package_path = locate_package(tag)
        repaired = []
        status = "verified" if not missing else "missing_assets"

        if missing and args.repair and cfg.get("repair_missing_assets", True) and package_path:
            with tempfile.TemporaryDirectory(prefix=f"pentarelease-{tag}-") as td:
                files = build_artifacts(tag, package_path, td)
                by_name = {p.name: p for p in files}
                upload = [str(by_name[n]) for n in missing if n in by_name]
                if upload:
                    run("gh", "release", "upload", tag, *upload)
                    repaired = [Path(x).name for x in upload]

            after = release_view(tag)
            after_assets = {a["name"] for a in after.get("assets", [])}
            still_missing = [x for x in expected if x not in after_assets]
            if still_missing:
                status = "repair_incomplete"
                missing = still_missing
            else:
                status = "verified"
                missing = []
        elif missing and not package_path:
            status = "hold_missing_source_package"

        results.append({
            "tag": tag,
            "latest": idx == 0,
            "target": release.get("target_commitish"),
            "package_path": package_path,
            "status": status,
            "repaired_assets": repaired,
            "missing_assets": missing,
            "preserved_existing_notes": True,
            "preserved_existing_target": True,
        })

    latest = results[0] if results else None
    latest_verified = bool(latest and latest["status"] == "verified")
    out = {
        "component": "ct.pentarelease",
        "engine_version": policy.get("version"),
        "repository": args.repository,
        "repair_enabled": bool(args.repair),
        "release_count_examined": len(results),
        "latest_verified": latest_verified,
        "latest": latest,
        "results": results,
    }
    Path(args.output).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))

    if cfg.get("latest_release_required", True) and governed and not latest_verified:
        raise SystemExit(42)


if __name__ == "__main__":
    main()
