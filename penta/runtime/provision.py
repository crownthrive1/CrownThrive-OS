#!/usr/bin/env python3
"""PentaProvision: fail-closed on-demand artifact/evidence provisioner.

Restores only artifacts explicitly declared in a signed/committed source manifest.
It never fabricates evidence, guesses source refs, overwrites mismatched files, or
promotes a governance HOLD by itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "crownthrive.penta.provision.request/v1"
RECEIPT_SCHEMA = "crownthrive.penta.provision.receipt/v1"

class ProvisionError(RuntimeError):
    pass


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and proc.returncode != 0:
        raise ProvisionError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def load_request(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ProvisionError("unsupported PentaProvision request schema")
    if not data.get("request_id") or not isinstance(data.get("artifacts"), list):
        raise ProvisionError("request_id and artifacts are required")
    return data


def _source_bytes(repo: Path, source_ref: str, source_path: str, allow_fetch: bool) -> bytes:
    spec = f"{source_ref}:{source_path}"
    if git(repo, "cat-file", "-e", spec, check=False) == "":
        probe = subprocess.run(["git", "cat-file", "-e", spec], cwd=repo)
        if probe.returncode != 0 and allow_fetch:
            git(repo, "fetch", "--no-tags", "--depth=1", "origin", source_ref)
    proc = subprocess.run(["git", "show", spec], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise ProvisionError(f"authoritative source unavailable: {spec}")
    return proc.stdout


def provision(repo: Path, request: dict[str, Any], *, apply: bool, allow_fetch: bool = False) -> dict[str, Any]:
    outcomes: list[dict[str, Any]] = []
    changed = 0
    for item in request["artifacts"]:
        dest = repo / item["destination_path"]
        expected = item["expected_blob_sha"]
        if len(expected) != 40:
            raise ProvisionError(f"invalid expected blob SHA for {dest}")
        if dest.exists():
            existing = git_blob_sha(dest.read_bytes())
            if existing != expected:
                raise ProvisionError(f"destination mismatch; refusing overwrite: {item['destination_path']}")
            outcomes.append({"path": item["destination_path"], "state": "ALREADY_PRESENT", "blob_sha": existing})
            continue
        payload = _source_bytes(repo, item["source_ref"], item["source_path"], allow_fetch)
        actual = git_blob_sha(payload)
        if actual != expected:
            raise ProvisionError(f"source blob mismatch for {item['source_path']}: expected {expected}, got {actual}")
        if apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".penta-provision.tmp")
            tmp.write_bytes(payload)
            os.replace(tmp, dest)
            changed += 1
            state = "PROVISIONED"
        else:
            state = "READY_TO_PROVISION"
        outcomes.append({"path": item["destination_path"], "state": state, "blob_sha": actual, "source_ref": item["source_ref"]})
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "request_id": request["request_id"],
        "contract": "ct.penta.provision.v1",
        "status": "PASS",
        "apply": apply,
        "changed": changed,
        "artifacts": outcomes,
        "authority_effect": False,
        "hold_promotion": False,
    }
    return receipt


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="penta-provision")
    p.add_argument("request")
    p.add_argument("--repo", default=".")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--allow-fetch", action="store_true")
    p.add_argument("--receipt")
    args = p.parse_args(argv)
    try:
        repo = Path(args.repo).resolve()
        receipt = provision(repo, load_request(Path(args.request)), apply=args.apply, allow_fetch=args.allow_fetch)
        rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        if args.receipt:
            Path(args.receipt).parent.mkdir(parents=True, exist_ok=True)
            Path(args.receipt).write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0
    except (ProvisionError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": RECEIPT_SCHEMA, "status": "HOLD", "error": str(exc)}, sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
