#!/usr/bin/env python3
"""Parent-side receipt for CIE pre-cert transport evidence.

This helper is deliberately not a certification action. It accepts only an exact-head,
non-operational, non-voting CIE pre-cert link message, ACKs that message as Agent D,
and records the parent->child forward reference. linked_governed certification remains
separate and requires the full governed acceptance packet.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from repository_federation_sync import federation_call

PARENT_AGENT = "ct.relay.agent-d"
PARENT_REPO_ID = "ct.repo.crownthrive-support"
CHILD_REPO_ID = "ct.repo.cie"
CHILD_GITHUB_ID = 1341314455
CHILD_AGENT = "ct.framework-agent.cie"
MESSAGE_TYPE = "framework_child_pre_cert_link"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")


def exact_message(messages: list[Any], parent_sha: str) -> dict[str, Any] | None:
    for item in messages:
        if not isinstance(item, dict):
            continue
        if item.get("sender_repo_id") != CHILD_REPO_ID:
            continue
        if item.get("receiver_repo_id") != PARENT_REPO_ID:
            continue
        if item.get("sender_agent_id") != CHILD_AGENT or item.get("message_type") != MESSAGE_TYPE:
            continue
        if item.get("requires_ack") is not True:
            continue
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("receiver_agent_id") != PARENT_AGENT:
            continue
        if payload.get("child_repo_id") != CHILD_REPO_ID or payload.get("child_github_repository_id") != CHILD_GITHUB_ID:
            continue
        if payload.get("governance_state") != "provisioned_unlinked":
            continue
        if payload.get("operationally_enabled") is not False or payload.get("vote_eligible") is not False:
            continue
        child_sha = str(payload.get("child_sha", ""))
        child_digest = str(payload.get("child_contract_digest", ""))
        parent_digest = str(payload.get("parent_contract_digest", ""))
        if str(payload.get("parent_sha", "")) != parent_sha:
            continue
        if not SHA40.fullmatch(child_sha) or not SHA64.fullmatch(child_digest) or not SHA64.fullmatch(parent_digest):
            continue
        return item
    return None


def main() -> int:
    parent_sha = os.environ.get("GITHUB_SHA", "").strip()
    parent_ref = os.environ.get("GITHUB_REF", "").strip()
    if not SHA40.fullmatch(parent_sha) or not parent_ref.startswith("refs/heads/"):
        raise RuntimeError("parent_exact_branch_sha_required")

    pulled = federation_call("pull", {"agent_id": PARENT_AGENT, "limit": 100})
    result = pulled.get("result")
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if not isinstance(messages, list):
        raise RuntimeError("parent_pull_invalid")

    message = exact_message(messages, parent_sha)
    if message is None:
        print(json.dumps({
            "ok": True,
            "state": "HOLD_WAITING_EXACT_CHILD_RETURN_MESSAGE",
            "parent_sha": parent_sha,
            "certified": False,
            "operationally_enabled": False,
            "vote_created": False,
        }, sort_keys=True))
        return 0

    payload = message["payload"]
    message_id = str(message.get("message_id", ""))
    child_sha = str(payload["child_sha"])

    ack = federation_call("ack", {
        "agent_id": PARENT_AGENT,
        "message_id": message_id,
        "ack_state": "accepted",
        "reason": "pre_cert_link_evidence_received_not_certified",
    })
    reference = federation_call("reference", {
        "agent_id": PARENT_AGENT,
        "target_repo_id": CHILD_REPO_ID,
        "reference_type": "parent_link",
        "source_ref": parent_ref,
        "target_ref": "refs/heads/main",
        "source_sha": parent_sha,
        "target_sha": child_sha,
        "contract_version": "2.1.0",
    })

    print(json.dumps({
        "ok": True,
        "state": "PRECERT_BIDIRECTIONAL_LINK_PROVED_NOT_CERTIFIED",
        "parent_sha": parent_sha,
        "child_sha": child_sha,
        "child_contract_digest": payload["child_contract_digest"],
        "parent_contract_digest": payload["parent_contract_digest"],
        "message_id": message_id,
        "ack_result_present": isinstance(ack.get("result"), dict),
        "reference_result_present": isinstance(reference.get("result"), dict),
        "certified": False,
        "operationally_enabled": False,
        "vote_created": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
