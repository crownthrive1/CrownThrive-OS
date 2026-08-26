#!/usr/bin/env python3
"""PentaMation v1 — dependency-free governed workflow runtime.

This runtime provides durable local orchestration semantics for CrownThrive's
PentaMation layer. It intentionally does not embed provider credentials or
manufacture CHLOM authority. Provider-native handlers can be registered by a
bound host process after exact capability certification.

Core properties:
- SQLite durable instance/step/receipt state
- deterministic idempotency
- dependency-DAG validation
- CHLOM authority resolver hook
- PentaHybrid human-gate resolver hook
- bounded retries
- per-step verification
- terminal verification
- cryptographic receipts
- fail-closed state transitions

The included CLI exposes validation and a safe self-test only. Production hosts
should import ``PentaMationRuntime`` and register certified handlers explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

RISK_CLASSES = {"D0", "D1", "D2", "D3"}
TERMINAL_STATES = {"succeeded", "failed", "held", "cancelled", "governance_blocked"}
INSTANCE_STATES = {
    "registered",
    "discovered",
    "governance_pending",
    "ready",
    "running",
    "human_gate",
    "verifying",
    "succeeded",
    "governance_blocked",
    "dependency_blocked",
    "retry_wait",
    "compensating",
    "failed",
    "held",
    "cancelled",
}
DISPOSITIONS_APPROVED = {"approved", "approved_exact", "approved_with_conditions"}

Handler = Callable[[Mapping[str, Any], Mapping[str, Any]], Any]
AuthorityResolver = Callable[[str, str, Mapping[str, Any]], bool]
HumanGateResolver = Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None]
CustomVerifier = Callable[[Any, Mapping[str, Any]], bool]
TerminalVerifier = Callable[[str, Mapping[str, Any]], bool]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class PentaMationError(RuntimeError):
    pass


class WorkflowValidationError(PentaMationError):
    pass


class AuthorityBlocked(PentaMationError):
    pass


class HumanGateBlocked(PentaMationError):
    pass


@dataclass(frozen=True)
class StepResult:
    step_id: str
    output: Any
    receipt_id: str
    output_hash: str


def validate_workflow(workflow: Mapping[str, Any]) -> list[str]:
    """Validate the executable PentaMation contract without third-party libs."""
    errors: list[str] = []
    required = {
        "workflow_id",
        "version",
        "trigger",
        "risk_class",
        "authority_ref",
        "owner",
        "idempotency_key_strategy",
        "human_gate",
        "retry_policy",
        "compensation",
        "steps",
        "terminal_verify",
        "preserve",
    }
    missing = sorted(required - set(workflow))
    if missing:
        return [f"missing required fields: {', '.join(missing)}"]

    workflow_id = workflow.get("workflow_id")
    if not isinstance(workflow_id, str) or not workflow_id.startswith("penta.mation."):
        errors.append("workflow_id must start with 'penta.mation.'")
    if not isinstance(workflow.get("version"), int) or workflow["version"] < 1:
        errors.append("version must be an integer >= 1")
    if workflow.get("risk_class") not in RISK_CLASSES:
        errors.append(f"risk_class must be one of {sorted(RISK_CLASSES)}")
    if not str(workflow.get("authority_ref", "")).strip():
        errors.append("authority_ref must be non-empty")
    if not str(workflow.get("owner", "")).strip():
        errors.append("owner must be non-empty")
    if workflow.get("idempotency_key_strategy") not in {"explicit", "workflow_version_input_hash"}:
        errors.append("idempotency_key_strategy is invalid")

    trigger = workflow.get("trigger")
    if not isinstance(trigger, Mapping) or trigger.get("type") not in {"event", "schedule", "manual", "dependency"}:
        errors.append("trigger.type must be event, schedule, manual, or dependency")
    elif not str(trigger.get("source", "")).strip():
        errors.append("trigger.source must be non-empty")

    gate = workflow.get("human_gate")
    if not isinstance(gate, Mapping) or not isinstance(gate.get("required"), bool):
        errors.append("human_gate.required must be boolean")
    elif gate["required"] and not str(gate.get("policy_ref", "")).strip():
        errors.append("human_gate.policy_ref is required when human_gate.required is true")

    retry = workflow.get("retry_policy")
    if not isinstance(retry, Mapping):
        errors.append("retry_policy must be an object")
    else:
        attempts = retry.get("max_attempts")
        backoff = retry.get("backoff_seconds")
        if not isinstance(attempts, int) or attempts < 1 or attempts > 20:
            errors.append("retry_policy.max_attempts must be between 1 and 20")
        if not isinstance(backoff, list) or not backoff or any(not isinstance(v, int) or v < 0 for v in backoff):
            errors.append("retry_policy.backoff_seconds must be a non-empty list of non-negative integers")

    compensation = workflow.get("compensation")
    if not isinstance(compensation, Mapping) or compensation.get("mode") not in {"none", "rollback", "remedy", "manual"}:
        errors.append("compensation.mode must be none, rollback, remedy, or manual")

    steps = workflow.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("steps must be a non-empty list")
        return errors

    step_ids: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            errors.append(f"steps[{index}] must be an object")
            continue
        step_id = step.get("step_id")
        if not isinstance(step_id, str) or not step_id:
            errors.append(f"steps[{index}].step_id must be non-empty")
            continue
        if step_id in step_ids:
            errors.append(f"duplicate step_id: {step_id}")
        step_ids.add(step_id)
        if not str(step.get("handler", "")).strip():
            errors.append(f"{step_id}.handler must be non-empty")
        if not isinstance(step.get("depends_on"), list):
            errors.append(f"{step_id}.depends_on must be a list")
        if not isinstance(step.get("params"), Mapping):
            errors.append(f"{step_id}.params must be an object")
        verify = step.get("verify")
        if not isinstance(verify, Mapping) or verify.get("mode") not in {"handler_receipt", "equals", "non_null", "custom"}:
            errors.append(f"{step_id}.verify.mode is invalid")
        elif verify.get("mode") == "custom" and not str(verify.get("verifier", "")).strip():
            errors.append(f"{step_id}.verify.verifier is required for custom verification")

    graph: dict[str, set[str]] = {}
    for step in steps:
        if not isinstance(step, Mapping) or not isinstance(step.get("step_id"), str):
            continue
        deps = step.get("depends_on", [])
        graph[step["step_id"]] = set(deps if isinstance(deps, list) else [])
        for dep in graph[step["step_id"]]:
            if dep not in step_ids:
                errors.append(f"{step['step_id']} references unknown dependency: {dep}")
            if dep == step["step_id"]:
                errors.append(f"{step['step_id']} cannot depend on itself")

    # Executable step dependencies must be acyclic.
    if not errors:
        temporary: set[str] = set()
        permanent: set[str] = set()

        def visit(node: str) -> None:
            if node in permanent:
                return
            if node in temporary:
                raise WorkflowValidationError(f"cycle detected at step: {node}")
            temporary.add(node)
            for dep in graph.get(node, set()):
                visit(dep)
            temporary.remove(node)
            permanent.add(node)

        try:
            for node in graph:
                visit(node)
        except WorkflowValidationError as exc:
            errors.append(str(exc))

    terminal_verify = workflow.get("terminal_verify")
    if not isinstance(terminal_verify, list) or not terminal_verify or any(not str(v).strip() for v in terminal_verify):
        errors.append("terminal_verify must be a non-empty list")
    preserve = workflow.get("preserve")
    if not isinstance(preserve, list) or not preserve or any(not str(v).strip() for v in preserve):
        errors.append("preserve must be a non-empty list")
    return errors


def topological_steps(workflow: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    steps = {step["step_id"]: step for step in workflow["steps"]}
    remaining = set(steps)
    done: set[str] = set()
    ordered: list[Mapping[str, Any]] = []
    while remaining:
        ready = sorted(step_id for step_id in remaining if set(steps[step_id]["depends_on"]) <= done)
        if not ready:
            raise WorkflowValidationError("workflow dependency graph cannot be resolved")
        for step_id in ready:
            ordered.append(steps[step_id])
            done.add(step_id)
            remaining.remove(step_id)
    return ordered


class PentaMationRuntime:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.handlers: dict[str, Handler] = {}
        self.verifiers: dict[str, CustomVerifier] = {}
        self.terminal_verifiers: dict[str, TerminalVerifier] = {}
        self._init_db()

    def close(self) -> None:
        self.conn.close()

    def _init_db(self) -> None:
        self.conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS workflow_instances (
                instance_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                workflow_version INTEGER NOT NULL,
                workflow_hash TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL,
                workflow_json TEXT NOT NULL,
                input_json TEXT NOT NULL,
                output_json TEXT,
                authority_ref TEXT NOT NULL,
                risk_class TEXT NOT NULL,
                owner TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS step_attempts (
                attempt_id TEXT PRIMARY KEY,
                instance_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                state TEXT NOT NULL,
                output_json TEXT,
                error TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                UNIQUE(instance_id, step_id, attempt_number),
                FOREIGN KEY(instance_id) REFERENCES workflow_instances(instance_id)
            );
            CREATE TABLE IF NOT EXISTS human_decisions (
                decision_id TEXT PRIMARY KEY,
                instance_id TEXT NOT NULL,
                disposition TEXT NOT NULL,
                actor_ref TEXT NOT NULL,
                authority_ref TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                conditions_json TEXT NOT NULL,
                decided_at TEXT NOT NULL,
                FOREIGN KEY(instance_id) REFERENCES workflow_instances(instance_id)
            );
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id TEXT PRIMARY KEY,
                instance_id TEXT NOT NULL,
                step_id TEXT,
                receipt_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(instance_id) REFERENCES workflow_instances(instance_id)
            );
            """
        )
        self.conn.commit()

    def register_handler(self, name: str, handler: Handler) -> None:
        if not name or name in self.handlers:
            raise PentaMationError(f"handler already registered or invalid: {name}")
        self.handlers[name] = handler

    def register_verifier(self, name: str, verifier: CustomVerifier) -> None:
        if not name or name in self.verifiers:
            raise PentaMationError(f"verifier already registered or invalid: {name}")
        self.verifiers[name] = verifier

    def register_terminal_verifier(self, name: str, verifier: TerminalVerifier) -> None:
        if not name or name in self.terminal_verifiers:
            raise PentaMationError(f"terminal verifier already registered or invalid: {name}")
        self.terminal_verifiers[name] = verifier

    def submit(self, workflow: Mapping[str, Any], inputs: Mapping[str, Any], explicit_idempotency_key: str | None = None) -> str:
        errors = validate_workflow(workflow)
        if errors:
            raise WorkflowValidationError("; ".join(errors))

        strategy = workflow["idempotency_key_strategy"]
        if strategy == "explicit":
            if not explicit_idempotency_key:
                raise WorkflowValidationError("explicit idempotency key required")
            idem = explicit_idempotency_key
        else:
            idem = sha256_json({"workflow_id": workflow["workflow_id"], "version": workflow["version"], "inputs": inputs})

        existing = self.conn.execute(
            "SELECT instance_id FROM workflow_instances WHERE idempotency_key = ?", (idem,)
        ).fetchone()
        if existing:
            return str(existing["instance_id"])

        now = utc_now()
        instance_id = f"pm-{uuid.uuid4()}"
        self.conn.execute(
            """
            INSERT INTO workflow_instances (
                instance_id, workflow_id, workflow_version, workflow_hash,
                idempotency_key, state, workflow_json, input_json,
                authority_ref, risk_class, owner, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'registered', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                instance_id,
                workflow["workflow_id"],
                workflow["version"],
                sha256_json(workflow),
                idem,
                canonical_json(workflow),
                canonical_json(inputs),
                workflow["authority_ref"],
                workflow["risk_class"],
                workflow["owner"],
                now,
                now,
            ),
        )
        self.conn.commit()
        self._receipt(instance_id, None, "instance_registered", {"workflow_hash": sha256_json(workflow), "idempotency_key": idem})
        return instance_id

    def record_human_decision(
        self,
        instance_id: str,
        disposition: str,
        actor_ref: str,
        authority_ref: str,
        evidence_refs: list[str],
        conditions: Mapping[str, Any] | None = None,
    ) -> str:
        if disposition not in {"approved", "approved_exact", "approved_with_conditions", "rejected", "recused", "hold"}:
            raise PentaMationError(f"unsupported human disposition: {disposition}")
        self._get_instance(instance_id)
        decision_id = f"ph-{uuid.uuid4()}"
        self.conn.execute(
            """
            INSERT INTO human_decisions (
                decision_id, instance_id, disposition, actor_ref, authority_ref,
                evidence_json, conditions_json, decided_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                instance_id,
                disposition,
                actor_ref,
                authority_ref,
                canonical_json(evidence_refs),
                canonical_json(dict(conditions or {})),
                utc_now(),
            ),
        )
        self.conn.commit()
        self._receipt(instance_id, None, "human_decision", {"decision_id": decision_id, "disposition": disposition, "actor_ref": actor_ref, "authority_ref": authority_ref, "evidence_refs": evidence_refs})
        return decision_id

    def run(
        self,
        instance_id: str,
        authority_resolver: AuthorityResolver,
        human_gate_resolver: HumanGateResolver | None = None,
    ) -> str:
        row = self._get_instance(instance_id)
        if row["state"] in TERMINAL_STATES:
            return str(row["state"])

        workflow = json.loads(row["workflow_json"])
        inputs = json.loads(row["input_json"])
        self._set_state(instance_id, "discovered")
        self._set_state(instance_id, "governance_pending")

        authorized = bool(authority_resolver(workflow["authority_ref"], workflow["risk_class"], inputs))
        self._receipt(instance_id, None, "authority_resolution", {"authority_ref": workflow["authority_ref"], "risk_class": workflow["risk_class"], "authorized": authorized})
        if not authorized:
            self._set_state(instance_id, "governance_blocked", "authority resolver returned false")
            return "governance_blocked"

        gate = workflow["human_gate"]
        if gate["required"]:
            decision = self._latest_human_decision(instance_id)
            if decision is None and human_gate_resolver is not None:
                proposed = human_gate_resolver(workflow, inputs)
                if proposed:
                    self.record_human_decision(
                        instance_id,
                        str(proposed["disposition"]),
                        str(proposed["actor_ref"]),
                        str(proposed["authority_ref"]),
                        list(proposed.get("evidence_refs", [])),
                        dict(proposed.get("conditions", {})),
                    )
                    decision = self._latest_human_decision(instance_id)
            if decision is None:
                self._set_state(instance_id, "human_gate", "required human decision not present")
                return "human_gate"
            if decision["disposition"] not in DISPOSITIONS_APPROVED:
                state = "held" if decision["disposition"] in {"hold", "recused"} else "governance_blocked"
                self._set_state(instance_id, state, f"human disposition: {decision['disposition']}")
                return state

        self._set_state(instance_id, "ready")
        self._set_state(instance_id, "running")

        context: dict[str, Any] = {"inputs": inputs, "steps": {}}
        completed_steps = self._completed_step_outputs(instance_id)
        context["steps"].update(completed_steps)

        for step in topological_steps(workflow):
            step_id = step["step_id"]
            if step_id in completed_steps:
                continue
            handler_name = step["handler"]
            handler = self.handlers.get(handler_name)
            if handler is None:
                self._set_state(instance_id, "dependency_blocked", f"unregistered handler: {handler_name}")
                return "dependency_blocked"

            retry = workflow["retry_policy"]
            max_attempts = int(retry["max_attempts"])
            backoff = list(retry["backoff_seconds"])
            last_error: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                attempt_id = f"pa-{uuid.uuid4()}"
                started = utc_now()
                self.conn.execute(
                    "INSERT INTO step_attempts (attempt_id, instance_id, step_id, attempt_number, state, started_at) VALUES (?, ?, ?, ?, 'running', ?)",
                    (attempt_id, instance_id, step_id, attempt, started),
                )
                self.conn.commit()
                try:
                    output = handler(step["params"], context)
                    verified = self._verify_step(step, output, context)
                    if not verified:
                        raise PentaMationError(f"verification failed for step {step_id}")
                    output_hash = sha256_json(output)
                    self.conn.execute(
                        "UPDATE step_attempts SET state='succeeded', output_json=?, completed_at=? WHERE attempt_id=?",
                        (canonical_json(output), utc_now(), attempt_id),
                    )
                    self.conn.commit()
                    receipt_id = self._receipt(instance_id, step_id, "step_succeeded", {"attempt": attempt, "handler": handler_name, "output_hash": output_hash})
                    context["steps"][step_id] = output
                    last_error = None
                    break
                except Exception as exc:  # exact error is preserved; retry remains bounded
                    last_error = exc
                    self.conn.execute(
                        "UPDATE step_attempts SET state='failed', error=?, completed_at=? WHERE attempt_id=?",
                        (repr(exc), utc_now(), attempt_id),
                    )
                    self.conn.commit()
                    self._receipt(instance_id, step_id, "step_failed", {"attempt": attempt, "handler": handler_name, "error": repr(exc)})
                    if attempt < max_attempts:
                        self._set_state(instance_id, "retry_wait", repr(exc))
                        delay = backoff[min(attempt - 1, len(backoff) - 1)]
                        if delay:
                            time.sleep(delay)
                        self._set_state(instance_id, "running")

            if last_error is not None:
                return self._handle_failure(instance_id, workflow, context, step_id, last_error)

        self._set_state(instance_id, "verifying")
        for verifier_name in workflow["terminal_verify"]:
            verifier = self.terminal_verifiers.get(verifier_name)
            if verifier is None:
                self._set_state(instance_id, "held", f"missing terminal verifier: {verifier_name}")
                return "held"
            if not verifier(instance_id, context):
                self._set_state(instance_id, "held", f"terminal verification failed: {verifier_name}")
                return "held"
            self._receipt(instance_id, None, "terminal_verifier_pass", {"verifier": verifier_name})

        output = {"steps": context["steps"]}
        self.conn.execute(
            "UPDATE workflow_instances SET output_json=?, updated_at=? WHERE instance_id=?",
            (canonical_json(output), utc_now(), instance_id),
        )
        self.conn.commit()
        self._receipt(instance_id, None, "workflow_succeeded", {"output_hash": sha256_json(output), "preserve": workflow["preserve"]})
        self._set_state(instance_id, "succeeded")
        return "succeeded"

    def status(self, instance_id: str) -> dict[str, Any]:
        row = self._get_instance(instance_id)
        receipts = self.conn.execute(
            "SELECT receipt_id, step_id, receipt_type, payload_hash, created_at FROM receipts WHERE instance_id=? ORDER BY created_at, receipt_id",
            (instance_id,),
        ).fetchall()
        return {
            "instance_id": instance_id,
            "workflow_id": row["workflow_id"],
            "workflow_version": row["workflow_version"],
            "state": row["state"],
            "risk_class": row["risk_class"],
            "authority_ref": row["authority_ref"],
            "owner": row["owner"],
            "workflow_hash": row["workflow_hash"],
            "error": row["error"],
            "receipts": [dict(receipt) for receipt in receipts],
        }

    def _verify_step(self, step: Mapping[str, Any], output: Any, context: Mapping[str, Any]) -> bool:
        verify = step["verify"]
        mode = verify["mode"]
        if mode == "handler_receipt":
            return isinstance(output, Mapping) and bool(output.get("verified"))
        if mode == "non_null":
            return output is not None
        if mode == "equals":
            return output == verify.get("expected")
        if mode == "custom":
            name = verify.get("verifier")
            verifier = self.verifiers.get(str(name))
            if verifier is None:
                return False
            return bool(verifier(output, context))
        return False

    def _handle_failure(self, instance_id: str, workflow: Mapping[str, Any], context: Mapping[str, Any], step_id: str, error: Exception) -> str:
        compensation = workflow["compensation"]
        mode = compensation["mode"]
        if mode == "none":
            self._set_state(instance_id, "failed", f"{step_id}: {error!r}")
            return "failed"
        if mode in {"manual", "remedy"}:
            self._set_state(instance_id, "held", f"{step_id}: {error!r}; compensation={mode}")
            return "held"
        if mode == "rollback":
            handler_name = compensation.get("handler")
            handler = self.handlers.get(str(handler_name)) if handler_name else None
            if handler is None:
                self._set_state(instance_id, "held", f"rollback handler unavailable after {step_id}: {error!r}")
                return "held"
            self._set_state(instance_id, "compensating")
            try:
                result = handler({"failed_step": step_id, "error": repr(error)}, context)
                self._receipt(instance_id, None, "compensation_completed", {"mode": "rollback", "handler": handler_name, "result_hash": sha256_json(result)})
            except Exception as comp_error:
                self._set_state(instance_id, "held", f"rollback failed: {comp_error!r}; original={error!r}")
                return "held"
            self._set_state(instance_id, "failed", f"workflow rolled back after {step_id}: {error!r}")
            return "failed"
        self._set_state(instance_id, "held", f"unknown compensation state after {step_id}")
        return "held"

    def _receipt(self, instance_id: str, step_id: str | None, receipt_type: str, payload: Mapping[str, Any]) -> str:
        body = {
            "instance_id": instance_id,
            "step_id": step_id,
            "receipt_type": receipt_type,
            "payload": dict(payload),
            "created_at": utc_now(),
        }
        receipt_id = f"pr-{uuid.uuid4()}"
        body_hash = sha256_json(body)
        self.conn.execute(
            "INSERT INTO receipts (receipt_id, instance_id, step_id, receipt_type, payload_json, payload_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (receipt_id, instance_id, step_id, receipt_type, canonical_json(body), body_hash, body["created_at"]),
        )
        self.conn.commit()
        return receipt_id

    def _set_state(self, instance_id: str, state: str, error: str | None = None) -> None:
        if state not in INSTANCE_STATES:
            raise PentaMationError(f"invalid state: {state}")
        self.conn.execute(
            "UPDATE workflow_instances SET state=?, error=?, updated_at=? WHERE instance_id=?",
            (state, error, utc_now(), instance_id),
        )
        self.conn.commit()

    def _get_instance(self, instance_id: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM workflow_instances WHERE instance_id=?", (instance_id,)).fetchone()
        if row is None:
            raise PentaMationError(f"unknown instance: {instance_id}")
        return row

    def _latest_human_decision(self, instance_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM human_decisions WHERE instance_id=? ORDER BY decided_at DESC, decision_id DESC LIMIT 1",
            (instance_id,),
        ).fetchone()

    def _completed_step_outputs(self, instance_id: str) -> dict[str, Any]:
        rows = self.conn.execute(
            """
            SELECT s.step_id, s.output_json
            FROM step_attempts s
            JOIN (
                SELECT step_id, MAX(attempt_number) AS max_attempt
                FROM step_attempts
                WHERE instance_id=? AND state='succeeded'
                GROUP BY step_id
            ) x ON x.step_id=s.step_id AND x.max_attempt=s.attempt_number
            WHERE s.instance_id=? AND s.state='succeeded'
            """,
            (instance_id, instance_id),
        ).fetchall()
        return {row["step_id"]: json.loads(row["output_json"]) for row in rows}


def _safe_self_test() -> dict[str, Any]:
    workflow = {
        "workflow_id": "penta.mation.selftest",
        "version": 1,
        "trigger": {"type": "manual", "source": "self-test"},
        "risk_class": "D0",
        "authority_ref": "chlom.capability.selftest",
        "owner": "penta.mation",
        "idempotency_key_strategy": "workflow_version_input_hash",
        "human_gate": {"required": True, "policy_ref": "penta.hybrid.selftest", "required_role": "test-reviewer", "quorum": 1},
        "retry_policy": {"max_attempts": 2, "backoff_seconds": [0]},
        "compensation": {"mode": "none", "handler": None, "contract_ref": None},
        "steps": [
            {"step_id": "discover", "handler": "echo", "depends_on": [], "params": {"value": "discovered"}, "verify": {"mode": "non_null", "verifier": None}},
            {"step_id": "execute", "handler": "combine", "depends_on": ["discover"], "params": {"suffix": "-executed"}, "verify": {"mode": "equals", "expected": "discovered-executed", "verifier": None}},
        ],
        "terminal_verify": ["all_steps_present"],
        "preserve": ["DAIL", "PentaDocs"],
    }

    runtime = PentaMationRuntime(":memory:")
    runtime.register_handler("echo", lambda params, _ctx: params["value"])
    runtime.register_handler("combine", lambda params, ctx: ctx["steps"]["discover"] + params["suffix"])
    runtime.register_terminal_verifier("all_steps_present", lambda _instance, ctx: set(ctx["steps"]) == {"discover", "execute"})

    instance = runtime.submit(workflow, {"test": True})
    first = runtime.run(instance, lambda _authority, _risk, _inputs: True)
    if first != "human_gate":
        raise AssertionError(f"expected human_gate, got {first}")
    runtime.record_human_decision(instance, "approved_exact", "crownthrive.id.selftest-reviewer", "chlom.role.selftest-reviewer", ["evidence:selftest"])
    second = runtime.run(instance, lambda _authority, _risk, _inputs: True)
    if second != "succeeded":
        raise AssertionError(f"expected succeeded, got {second}")

    duplicate = runtime.submit(workflow, {"test": True})
    if duplicate != instance:
        raise AssertionError("idempotency did not return the existing instance")

    status = runtime.status(instance)
    if not status["receipts"]:
        raise AssertionError("receipts were not preserved")
    runtime.close()
    return {"pass": True, "instance_id": instance, "state": status["state"], "receipt_count": len(status["receipts"])}


def main() -> int:
    parser = argparse.ArgumentParser(description="PentaMation governed workflow runtime")
    parser.add_argument("--validate", type=Path, help="Validate an executable workflow JSON file")
    parser.add_argument("--self-test", action="store_true", help="Run safe in-memory runtime self-test")
    args = parser.parse_args()

    if args.self_test:
        try:
            result = _safe_self_test()
        except Exception as exc:
            print(json.dumps({"pass": False, "error": repr(exc)}, indent=2), file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2))
        return 0

    if args.validate:
        try:
            workflow = json.loads(args.validate.read_text(encoding="utf-8"))
        except Exception as exc:
            print(json.dumps({"valid": False, "errors": [repr(exc)]}, indent=2))
            return 2
        errors = validate_workflow(workflow)
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return 1 if errors else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
