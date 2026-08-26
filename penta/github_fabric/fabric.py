#!/usr/bin/env python3
"""Deterministic PentaRunners/PentaPunters/PentaActions/PentaResults runtime."""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


class FabricError(ValueError):
    """A fail-closed execution-fabric contract violation."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_contract(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FabricError("fabric contract must be a JSON object")
    return value


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("schema") != "ct.penta.github-execution-fabric.v1":
        raise FabricError("unsupported fabric schema")
    runners = contract.get("runners")
    actions = contract.get("actions")
    if not isinstance(runners, list) or not runners:
        raise FabricError("at least one runner is required")
    if not isinstance(actions, list) or not actions:
        raise FabricError("at least one action is required")
    runner_ids: set[str] = set()
    for runner in runners:
        runner_id = runner.get("id")
        labels = runner.get("labels")
        if not runner_id or runner_id in runner_ids or not isinstance(labels, list) or not labels:
            raise FabricError("runner identities and labels must be unique and non-empty")
        runner_ids.add(runner_id)
        if runner.get("state") not in {"production", "certification_only", "hold"}:
            raise FabricError(f"invalid runner state: {runner_id}")
    action_ids: set[str] = set()
    for action in actions:
        action_id = action.get("id")
        argv = action.get("argv")
        if not action_id or action_id in action_ids:
            raise FabricError("action identities must be unique and non-empty")
        if not isinstance(argv, list) or not argv or not all(isinstance(v, str) and v for v in argv):
            raise FabricError(f"action argv must be a non-empty string array: {action_id}")
        if action.get("shell") is not False:
            raise FabricError(f"shell execution is prohibited: {action_id}")
        action_ids.add(action_id)


def select_runner(contract: Mapping[str, Any], required_labels: Sequence[str]) -> Mapping[str, Any]:
    required = set(required_labels)
    candidates = [
        r for r in contract["runners"]
        if r["state"] == "production" and required.issubset(set(r["labels"]))
    ]
    if not candidates:
        raise FabricError("no production runner satisfies the requested labels")
    return sorted(candidates, key=lambda r: (r.get("priority", 100), r["id"]))[0]


def select_action(contract: Mapping[str, Any], action_id: str) -> Mapping[str, Any]:
    action = next((a for a in contract["actions"] if a["id"] == action_id), None)
    if action is None or action.get("state") != "production":
        raise FabricError("requested action is not production eligible")
    return action


@dataclass(frozen=True)
class ExecutionResult:
    receipt: dict[str, Any]
    exit_code: int


def execute_request(
    contract: Mapping[str, Any], request: Mapping[str, Any], *, observed_at: str | None = None
) -> ExecutionResult:
    """Validate, route and execute one allowlisted action without a shell."""
    validate_contract(contract)
    if request.get("schema") != "ct.penta.action-request.v1":
        raise FabricError("unsupported request schema")
    request_id = request.get("request_id")
    authority_ref = request.get("authority_ref")
    if not isinstance(request_id, str) or not request_id or not isinstance(authority_ref, str) or not authority_ref:
        raise FabricError("request_id and authority_ref are required")
    labels = request.get("required_labels", [])
    if not isinstance(labels, list) or not all(isinstance(v, str) for v in labels):
        raise FabricError("required_labels must be a string array")
    runner = select_runner(contract, labels)
    action = select_action(contract, str(request.get("action_id", "")))
    if action["id"] not in runner.get("allowed_actions", []):
        raise FabricError("selected runner is not authorized for the requested action")
    completed = subprocess.run(action["argv"], capture_output=True, text=True, shell=False, timeout=action.get("timeout_seconds", 60), check=False)
    output = {"stdout": completed.stdout, "stderr": completed.stderr, "exit_code": completed.returncode}
    body: dict[str, Any] = {
        "schema": "ct.penta.action-result.v1",
        "request_id": request_id,
        "request_sha256": digest(request),
        "contract_sha256": digest(contract),
        "authority_ref": authority_ref,
        "runner_id": runner["id"],
        "action_id": action["id"],
        "status": "passed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
        "authority_note": "Execution evidence does not manufacture provider, economic, legal, release, or governance authority.",
    }
    body["result_sha256"] = digest(body)
    return ExecutionResult(receipt=body, exit_code=completed.returncode)


def write_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
