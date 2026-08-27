#!/usr/bin/env python3
"""Penta lifecycle proof primitives.

Pure, fail-closed helpers shared by PentaPR relatives. This module does not
mutate GitHub; callers persist the returned receipt through their evidence lane.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA = "ct.penta.lifecycle-proof.20260826.v1"
ALLOWED = {
    "OPEN": {"CLASSIFIED"},
    "CLASSIFIED": {"NURTURE", "RESTACK", "READY", "CLOSE_CANDIDATE"},
    "NURTURE": {"CLASSIFIED", "READY", "CLOSE_CANDIDATE"},
    "RESTACK": {"CLASSIFIED", "READY", "CLOSE_CANDIDATE"},
    "READY": {"MERGE_CANDIDATE", "CLASSIFIED"},
    "MERGE_CANDIDATE": {"MERGED", "CLASSIFIED"},
    "CLOSE_CANDIDATE": {"CLOSED", "CLASSIFIED"},
    "MERGED": {"REVERT_CANDIDATE"},
    "REVERT_CANDIDATE": {"REVERTED"},
    "CLOSED": set(),
    "REVERTED": set(),
}


def canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def transition(previous: str, current: str) -> None:
    if previous not in ALLOWED:
        raise ValueError(f"unknown_previous_state:{previous}")
    if current not in ALLOWED[previous]:
        raise ValueError(f"illegal_transition:{previous}->{current}")


def build_receipt(*, pr: int, previous: str, current: str, head_sha: str,
                  authority: str, observed_head_sha: str, checks: dict[str, Any],
                  terminal_sha: str | None = None, previous_receipt_sha256: str | None = None,
                  observed_at: str) -> dict[str, Any]:
    transition(previous, current)
    if not head_sha or observed_head_sha != head_sha:
        raise ValueError("exact_head_readback_failed")
    if current == "MERGED" and not terminal_sha:
        raise ValueError("merged_without_terminal_sha")
    if current == "REVERTED" and not terminal_sha:
        raise ValueError("reverted_without_terminal_sha")
    body = {
        "schema": SCHEMA,
        "pr": pr,
        "previous": previous,
        "current": current,
        "head_sha": head_sha,
        "observed_head_sha": observed_head_sha,
        "authority": authority,
        "checks": checks,
        "terminal_sha": terminal_sha,
        "previous_receipt_sha256": previous_receipt_sha256,
        "observed_at": observed_at,
    }
    body["receipt_sha256"] = hashlib.sha256(canonical(body)).hexdigest()
    return body


def verify_receipt(receipt: dict[str, Any]) -> None:
    supplied = receipt.get("receipt_sha256")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    expected = hashlib.sha256(canonical(body)).hexdigest()
    if supplied != expected:
        raise ValueError("receipt_digest_mismatch")
    transition(str(receipt["previous"]), str(receipt["current"]))
    if receipt.get("head_sha") != receipt.get("observed_head_sha"):
        raise ValueError("receipt_exact_head_mismatch")
    if receipt.get("current") in {"MERGED", "REVERTED"} and not receipt.get("terminal_sha"):
        raise ValueError("terminal_receipt_missing_sha")
