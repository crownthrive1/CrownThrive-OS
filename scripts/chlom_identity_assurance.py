#!/usr/bin/env python3
"""Validate CrownThrive CHLOM agent identity assurance and emit a bounded parent heartbeat.

Public verification includes DID, agent UUID, repository identity, commit SHA,
heartbeat metadata and a SHA-256 public digest. CHLOM Fingerprint identifiers,
salts, commitments, key material and credentials are private and must never be
returned by the public directory or committed to docs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "developers/manifests/chlom-agent-identity-assurance.v1.json"
FLEET_PATH = ROOT / "developers/manifests/framework-child-fleet.v1.json"
PUBLIC_DIRECTORY_URL = "https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/public-agent-identity-directory"
FEDERATION_URL = "https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/repository-federation-bus"
OIDC_AUDIENCE = "crownthrive-repository-federation"
MAX_RESPONSE_BYTES = 512 * 1024
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_PUBLIC_KEYS = {
    "fingerprint_record_uuid",
    "fingerprint_salt",
    "fingerprint_commitment_sha256",
    "key_ref",
    "private_key",
    "secret",
    "seed",
    "mnemonic",
    "credential",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: root must be an object")
    return value


def read_http_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "CrownThrive-Identity-Assurance/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("identity_directory_response_too_large")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("identity_directory_invalid")
    return value


def oidc_token() -> str:
    request_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "").strip()
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "").strip()
    if not request_url or not request_token:
        raise RuntimeError("github_actions_oidc_environment_missing")
    parsed = urllib.parse.urlsplit(request_url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("audience", OIDC_AUDIENCE))
    url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment))
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {request_token}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    body = json.loads(raw.decode("utf-8"))
    token = str(body.get("value", "")).strip() if isinstance(body, dict) else ""
    if token.count(".") != 2:
        raise RuntimeError("github_actions_oidc_token_missing")
    return token


def heartbeat_parent(agent_id: str) -> None:
    contract_digest = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    payload = json.dumps(
        {"action": "heartbeat", "input": {"agent_id": agent_id, "contract_digest": contract_digest}},
        separators=(",", ":"),
    ).encode("utf-8")
    req = urllib.request.Request(
        FEDERATION_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {oidc_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CrownThrive-Identity-Assurance/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    body = json.loads(raw.decode("utf-8"))
    if not isinstance(body, dict) or body.get("ok") is not True:
        raise RuntimeError("parent_identity_heartbeat_failed")


def assert_public_record(record: dict[str, Any]) -> None:
    leaked = FORBIDDEN_PUBLIC_KEYS.intersection(record)
    if leaked:
        raise RuntimeError(f"private_identity_field_public:{sorted(leaked)}")
    uuid.UUID(str(record.get("agent_uuid", "")))
    did_uri = str(record.get("did_uri", ""))
    if not did_uri.startswith("did:"):
        raise RuntimeError(f"did_missing:{record.get('agent_id')}")
    digest = str(record.get("public_identity_digest_sha256", ""))
    if not SHA64.fullmatch(digest):
        raise RuntimeError(f"public_digest_invalid:{record.get('agent_id')}")
    if record.get("vote_eligible") is True and str(record.get("agent_id", "")).startswith("ct.framework-agent."):
        raise RuntimeError("framework_transport_identity_must_not_create_vote")


def validate(require_fresh: bool = False) -> dict[str, int]:
    manifest = load_json(MANIFEST_PATH)
    fleet = load_json(FLEET_PATH)
    source_contract = manifest.get("source_contract", {})
    if source_contract.get("public_did") is not True:
        raise RuntimeError("public_did_contract_missing")
    if source_contract.get("fingerprint_id_public") is not False:
        raise RuntimeError("fingerprint_id_must_remain_private")
    if source_contract.get("fingerprint_commitment_public") is not False:
        raise RuntimeError("fingerprint_commitment_must_remain_private")
    if manifest.get("documentation_review", {}).get("hard_gate") is not True:
        raise RuntimeError("documentation_identity_hard_gate_missing")

    directory = read_http_json(str(manifest.get("public_directory_url") or PUBLIC_DIRECTORY_URL))
    privacy = directory.get("privacy_contract", {})
    if privacy.get("did_public") is not True or privacy.get("fingerprint_id_public") is not False:
        raise RuntimeError("runtime_privacy_contract_mismatch")
    records = directory.get("records")
    if not isinstance(records, list) or not records:
        raise RuntimeError("public_identity_directory_empty")
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in records:
        if not isinstance(raw, dict):
            raise RuntimeError("public_identity_record_invalid")
        assert_public_record(raw)
        by_key[(str(raw.get("repo_id", "")), str(raw.get("agent_id", "")))] = raw

    parent_rows = [r for r in records if isinstance(r, dict) and r.get("repo_id") == "ct.repo.crownthrive-support" and r.get("binding_state") == "active"]
    if not parent_rows:
        raise RuntimeError("canonical_parent_identity_rows_missing")
    for record in parent_rows:
        if int(record.get("github_repository_id") or 0) != 1336348391:
            raise RuntimeError(f"canonical_repository_id_invalid:{record.get('agent_id')}")
        if not SHA40.fullmatch(str(record.get("head_sha", ""))):
            raise RuntimeError(f"active_agent_sha_missing:{record.get('agent_id')}")
        if not record.get("heartbeat_at"):
            raise RuntimeError(f"active_agent_heartbeat_missing:{record.get('agent_id')}")
        if require_fresh and record.get("heartbeat_fresh") is not True:
            raise RuntimeError(f"active_agent_heartbeat_stale:{record.get('agent_id')}")

    children = fleet.get("framework_children", [])
    if not isinstance(children, list) or len(children) != 8:
        raise RuntimeError("framework_fleet_sequence_invalid")
    for child in children:
        if not isinstance(child, dict):
            raise RuntimeError("framework_child_invalid")
        key = (str(child.get("repo_id", "")), str(child.get("framework_agent_id", "")))
        record = by_key.get(key)
        if record is None:
            raise RuntimeError(f"framework_agent_identity_missing:{key}")
        if child.get("physical_repository_id") is None:
            if record.get("github_repository_id") is not None:
                raise RuntimeError(f"planned_repo_identity_mismatch:{key}")
            if record.get("operationally_enabled") is True:
                raise RuntimeError(f"unprovisioned_child_claimed_operational:{key}")
        else:
            if int(record.get("github_repository_id") or 0) != int(child["physical_repository_id"]):
                raise RuntimeError(f"physical_repository_id_mismatch:{key}")
            if not SHA40.fullmatch(str(record.get("head_sha", ""))):
                raise RuntimeError(f"provisioned_child_sha_missing:{key}")
            if not record.get("heartbeat_at"):
                raise RuntimeError(f"provisioned_child_heartbeat_missing:{key}")

    return {
        "records": len(records),
        "active_parent_records": len(parent_rows),
        "framework_children": len(children),
        "fresh_parent_records": sum(1 for r in parent_rows if r.get("heartbeat_fresh") is True),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heartbeat-parent", action="store_true")
    parser.add_argument("--agent-id", default="ct.agent.framework-factory")
    parser.add_argument("--require-fresh", action="store_true")
    args = parser.parse_args()
    if args.heartbeat_parent:
        heartbeat_parent(args.agent_id)
    summary = validate(require_fresh=args.require_fresh)
    print(json.dumps({"ok": True, **summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # fail closed; emit no secrets
        print(f"HOLD: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
