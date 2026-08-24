#!/usr/bin/env python3
"""CrownThrive repository-federation API client.

GitHub Actions OIDC proves repository identity. The federation runtime then
requires a governed repository<->agent binding for every agent-scoped action.
No long-lived federation or Supabase credential is accepted by this client.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FEDERATION_MANIFEST = ROOT / "developers/manifests/repository-federation.v1.json"
AGENT_BINDINGS = ROOT / "developers/manifests/agent-federation-bindings.v1.json"
DEFAULT_FEDERATION_URL = "https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/repository-federation-bus"
OIDC_AUDIENCE = "crownthrive-repository-federation"
MAX_RESPONSE_BYTES = 256 * 1024


def manifest_digest(path: Path = FEDERATION_MANIFEST) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("json_root_must_be_object")
    return value


def request_oidc_token() -> str:
    request_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "").strip()
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "").strip()
    if not request_url or not request_token:
        raise RuntimeError("github_actions_oidc_environment_missing")
    parsed = urllib.parse.urlsplit(request_url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("audience", OIDC_AUDIENCE))
    url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment))
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {request_token}", "Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("oidc_response_too_large")
    body = json.loads(raw.decode("utf-8"))
    token = str(body.get("value", "")).strip() if isinstance(body, dict) else ""
    if not token or token.count(".") != 2:
        raise RuntimeError("github_actions_oidc_token_missing")
    return token


def federation_call(action: str, payload: dict[str, Any], *, federation_url: str | None = None) -> dict[str, Any]:
    token = request_oidc_token()
    url = federation_url or os.environ.get("CT_FEDERATION_URL", DEFAULT_FEDERATION_URL)
    if not url.startswith("https://"):
        raise ValueError("federation_url_must_be_https")
    data = json.dumps({"action": action, "input": payload}, separators=(",", ":")).encode("utf-8")
    if len(data) > 64 * 1024:
        raise ValueError("federation_request_too_large")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "CrownThrive-Repository-Federation/1.2"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raw = exc.read(MAX_RESPONSE_BYTES + 1)
        detail = raw.decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"federation_http_error:{exc.code}:{detail}") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("federation_response_too_large")
    body = json.loads(raw.decode("utf-8"))
    if not isinstance(body, dict) or body.get("ok") is not True:
        raise RuntimeError("federation_response_not_ok")
    return body


def redact_for_ci(value: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(value))
    payload = result.get("result")
    if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        result["result"] = {
            "repo_id": payload.get("repo_id"),
            "agent_id": payload.get("agent_id"),
            "message_count": len(payload["messages"]),
            "messages_redacted": True,
        }
    return result


def default_sync_bindings() -> list[dict[str, Any]]:
    inventory = json_load(AGENT_BINDINGS)
    rows = inventory.get("parent_non_voting_transport_bindings", [])
    if not isinstance(rows, list):
        raise ValueError("agent_binding_inventory_invalid")
    output: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("agent_binding_row_invalid")
        output.append({
            "agent_id": str(row.get("agent_id", "")),
            "agent_role": str(row.get("role", "")),
            "source_ref": str(row.get("source_ref", "")),
            "authority_ceiling": str(row.get("authority_ceiling", "D2")),
            "metadata": ({"legacy_role_label": row["legacy_role_label"]} if row.get("legacy_role_label") else {}),
        })
    return output


def self_test() -> None:
    manifest = json_load(FEDERATION_MANIFEST)
    inventory = json_load(AGENT_BINDINGS)
    auth = manifest["runtime"]["auth"]
    assert auth["scheme"] == "github_actions_oidc"
    assert auth["audience"] == OIDC_AUDIENCE
    assert auth["long_lived_shared_secret_required"] is False
    child = next(item for item in manifest["repositories"] if item["repo_id"] == "ct.repo.cie")
    assert child["role"] == "framework_child"
    assert child["github_repository_id"] == 1341314455
    assert child["governance_state"] == "provisioned_unlinked"
    assert child["operationally_enabled"] is False
    assert child["can_vote"] is False
    assert child["precert_transport_enabled"] is True
    assert manifest["authority"]["linked_governed_physical_child_repository_required"] is True
    assert manifest["framework_child_policy"]["linked_governed_requires_physical_repository"] is True
    assert manifest["framework_child_policy"]["transport_messages_create_votes"] is False
    assert manifest["framework_child_policy"]["framework_subagents_create_votes"] is False
    assert inventory["rules"]["agent_repository_binding_required"] is True
    assert inventory["rules"]["non_voting_sync_may_not_create_vote"] is True
    assert inventory["rules"]["child_certification_agent"] == "ct.relay.agent-d"
    assert all(item.get("vote_eligible") is not True for item in inventory["parent_non_voting_transport_bindings"])
    prospective = inventory["prospective_cie_child_bindings"]
    assert prospective[0]["agent_id"] == "ct.framework-agent.cie"
    assert all(item["vote_eligible"] is False for item in prospective)
    forbidden_static = "SUPABASE_" + "SERVICE_ROLE_KEY"
    assert forbidden_static not in Path(__file__).read_text(encoding="utf-8")
    print(
        "Repository federation client self-test PASS: OIDC + repository-agent bindings; "
        f"contract_sha256={manifest_digest()}; physical CIE child=1341314455 provisioned_unlinked; "
        "pre-cert transport bounded; non-voting sync bounded; linked_governed still requires Agent D."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=(
        "state", "bootstrap", "heartbeat", "publish", "pull", "ack", "reference",
        "authority", "cie-score", "certify-child", "sync-agents",
    ))
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--agent-id")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--receiver-repo-id")
    parser.add_argument("--message-type")
    parser.add_argument("--severity", default="info")
    parser.add_argument("--requires-ack", action="store_true")
    parser.add_argument("--message-id")
    parser.add_argument("--ack-state", choices=("received", "accepted", "rejected", "completed", "escalated"))
    parser.add_argument("--reason")
    parser.add_argument("--authority-key")
    parser.add_argument("--target-repo-id")
    parser.add_argument("--reference-type")
    parser.add_argument("--source-ref")
    parser.add_argument("--target-ref")
    parser.add_argument("--source-sha")
    parser.add_argument("--target-sha")
    parser.add_argument("--contract-version", default="1.0.0")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--child-repo-id")
    parser.add_argument("--child-sha")
    parser.add_argument("--child-contract-digest")
    parser.add_argument("--parent-contract-digest")
    parser.add_argument("--json", action="store_true", help="Print full safe response. Pull message bodies remain redacted.")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if not args.command:
        parser.error("command required unless --self-test")

    agent_id = args.agent_id or "ct.relay.agent-a"
    payload: dict[str, Any]
    action = args.command
    if action == "state":
        payload = {}
    elif action == "bootstrap":
        payload = {"agent_id": agent_id, "contract_digest": manifest_digest()}
    elif action == "heartbeat":
        payload = {"agent_id": agent_id, "contract_digest": manifest_digest()}
    elif action == "publish":
        if not args.message_type:
            parser.error("--message-type required")
        payload = {
            "agent_id": agent_id,
            "receiver_repo_id": args.receiver_repo_id,
            "message_type": args.message_type,
            "severity": args.severity,
            "payload": json_load(args.input) if args.input else {},
            "requires_ack": args.requires_ack,
        }
    elif action == "pull":
        payload = {"agent_id": agent_id, "limit": max(1, min(args.limit, 200))}
    elif action == "ack":
        if not args.message_id or not args.ack_state:
            parser.error("--message-id and --ack-state required")
        payload = {"agent_id": agent_id, "message_id": args.message_id, "ack_state": args.ack_state, "reason": args.reason}
    elif action == "reference":
        for name, value in (("target-repo-id", args.target_repo_id), ("reference-type", args.reference_type), ("source-ref", args.source_ref), ("target-ref", args.target_ref)):
            if not value:
                parser.error(f"--{name} required")
        payload = {
            "agent_id": agent_id,
            "target_repo_id": args.target_repo_id,
            "reference_type": args.reference_type,
            "source_ref": args.source_ref,
            "target_ref": args.target_ref,
            "source_sha": args.source_sha,
            "target_sha": args.target_sha,
            "contract_version": args.contract_version,
        }
    elif action == "authority":
        if not args.authority_key:
            parser.error("--authority-key required")
        payload = {"authority_key": args.authority_key}
    elif action == "cie-score":
        if not args.input:
            parser.error("--input required")
        payload = {"agent_id": agent_id, "subject": json_load(args.input)}
        action = "algorithm.cie.score"
    elif action == "certify-child":
        required = (args.child_repo_id, args.child_sha, args.child_contract_digest, args.parent_contract_digest)
        if not all(required):
            parser.error("--child-repo-id, --child-sha, --child-contract-digest and --parent-contract-digest required")
        payload = {
            "agent_id": agent_id,
            "child_repo_id": args.child_repo_id,
            "child_sha": args.child_sha,
            "child_contract_digest": args.child_contract_digest,
            "parent_contract_digest": args.parent_contract_digest,
        }
        action = "certify_child"
    elif action == "sync-agents":
        target = args.target_repo_id or "ct.repo.crownthrive-support"
        if args.input:
            source = json_load(args.input)
            bindings = source.get("bindings")
            if not isinstance(bindings, list):
                parser.error("--input for sync-agents must contain a bindings array")
        else:
            bindings = default_sync_bindings()
        payload = {"agent_id": agent_id, "target_repo_id": target, "bindings": bindings}
        action = "sync_agents"
    else:
        raise AssertionError("unreachable")

    result = redact_for_ci(federation_call(action, payload))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps({"ok": True, "action": result.get("action"), "repository": result.get("repository"), "result": result.get("result", {})}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
