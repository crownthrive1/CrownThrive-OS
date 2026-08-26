"""PentaSerialized durable serialization and continuity control plane.

Standard-library only. Provides canonical serialization, append-only hash-chained
ledger, optimistic concurrency gates, tombstones, restore, snapshots, integrity
verification, idempotency, family adapters, and Git diff continuity receipts.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

try:
    import fcntl
except ImportError:  # pragma: no cover - fail closed on unsupported hosts
    fcntl = None

SCHEMA = "crownthrive.penta.serialized/v1"
STORE_SCHEMA = "crownthrive.penta.serialized.store/v1"
SNAPSHOT_SCHEMA = "crownthrive.penta.serialized.snapshot/v1"
RECEIPT_SCHEMA = "crownthrive.penta.serialized.git-receipt/v1"

KIND_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "PentaVersion": (
        "subject_id", "version", "version_scheme", "lifecycle_state", "effective_at"
    ),
    "PentaFormat": (
        "format_id", "media_type", "schema_version", "canonical_extension"
    ),
    "PentaSOPs": (
        "sop_id", "owner", "lifecycle_state", "effective_at", "review_due", "steps"
    ),
    "PentaSLAs": (
        "sla_id", "service_id", "effective_at", "targets", "escalation_owner"
    ),
    "PentaScribe": (
        "record_id", "record_type", "source_refs", "lifecycle_state"
    ),
}

class PentaSerializedError(RuntimeError):
    """Base error."""

class ConflictError(PentaSerializedError):
    """Optimistic concurrency or idempotency conflict."""

class IntegrityError(PentaSerializedError):
    """Ledger or serialization integrity failure."""

class ValidationError(PentaSerializedError):
    """Invalid record or policy input."""

class DeletedError(PentaSerializedError):
    """Mutation attempted against a tombstoned artifact."""

def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

def canonical_json(value: Any) -> str:
    """Deterministic UTF-8-safe JSON representation."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

def stable_key(key: str) -> str:
    if not isinstance(key, str) or not key.strip():
        raise ValidationError("artifact_key must be a non-empty string")
    key = key.strip()
    if len(key) > 240:
        raise ValidationError("artifact_key exceeds 240 characters")
    if "\x00" in key or "\n" in key or "\r" in key:
        raise ValidationError("artifact_key contains forbidden control characters")
    return key

def validate_kind(kind: str, payload: Any) -> None:
    if not isinstance(kind, str) or not kind.strip():
        raise ValidationError("kind must be a non-empty string")
    if payload is not None and not isinstance(payload, Mapping):
        raise ValidationError("payload must be a JSON object")
    required = KIND_REQUIRED_FIELDS.get(kind)
    if required:
        missing = [field for field in required if payload is None or field not in payload]
        if missing:
            raise ValidationError(
                f"{kind} payload missing required fields: {', '.join(missing)}"
            )
    if kind == "PentaSOPs" and payload is not None:
        if not isinstance(payload.get("steps"), list) or not payload["steps"]:
            raise ValidationError("PentaSOPs.steps must be a non-empty list")
    if kind == "PentaSLAs" and payload is not None:
        if not isinstance(payload.get("targets"), Mapping) or not payload["targets"]:
            raise ValidationError("PentaSLAs.targets must be a non-empty object")
    if kind == "PentaScribe" and payload is not None:
        if not isinstance(payload.get("source_refs"), list):
            raise ValidationError("PentaScribe.source_refs must be a list")

def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        try:
            dirfd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        except OSError:
            pass
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()

@dataclass(frozen=True)
class MutationResult:
    event: dict[str, Any]
    idempotent_replay: bool = False

class PentaSerializedStore:
    """Append-only serialized artifact store with a materialized current index."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.meta = self.root / "meta" / "store.json"
        self.ledger = self.root / "ledger" / "events.jsonl"
        self.index = self.root / "index" / "current.json"
        self.snapshots = self.root / "snapshots"
        self.lock_file = self.root / ".penta-serialized.lock"

    def init(self) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.index.parent.mkdir(parents=True, exist_ok=True)
        self.snapshots.mkdir(parents=True, exist_ok=True)
        if not self.meta.exists():
            metadata = {
                "schema": STORE_SCHEMA,
                "store_id": str(uuid.uuid4()),
                "created_at": utc_now(),
                "serialization": "canonical-json",
                "hash": "sha256",
                "mutation_model": "append-only-with-tombstones",
                "hard_delete": False,
            }
            _atomic_write(self.meta, json.dumps(metadata, indent=2, sort_keys=True) + "\n")
        if not self.ledger.exists():
            _atomic_write(self.ledger, "")
        if not self.index.exists():
            _atomic_write(self.index, "{}\n")
        return json.loads(self.meta.read_text(encoding="utf-8"))

    @contextlib.contextmanager
    def _lock(self) -> Iterator[None]:
        if fcntl is None:
            raise IntegrityError("POSIX file locking unavailable; refusing mutation")
        self.init()
        with self.lock_file.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _events(self) -> list[dict[str, Any]]:
        self.init()
        events: list[dict[str, Any]] = []
        for number, line in enumerate(self.ledger.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise IntegrityError(f"ledger line {number} is invalid JSON") from exc
            events.append(event)
        return events

    @staticmethod
    def _materialize(events: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        current: dict[str, dict[str, Any]] = {}
        for event in events:
            current[event["artifact_key"]] = {
                "artifact_id": event["artifact_id"],
                "artifact_key": event["artifact_key"],
                "kind": event["kind"],
                "version": event["version"],
                "revision_id": event["revision_id"],
                "payload_hash": event["payload_hash"],
                "operation": event["operation"],
                "tombstoned": event["operation"] == "tombstone",
                "updated_at": event["timestamp"],
                "sequence": event["sequence"],
            }
        return current

    def current_index(self) -> dict[str, dict[str, Any]]:
        return self._materialize(self._events())

    def _write_index(self, events: list[dict[str, Any]]) -> None:
        current = self._materialize(events)
        _atomic_write(self.index, json.dumps(current, indent=2, sort_keys=True) + "\n")

    @staticmethod
    def _event_hash(event_without_hash: Mapping[str, Any]) -> str:
        return sha256_json(event_without_hash)

    def _find_idempotency(self, events: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.get("idempotency_key") == key:
                return event
        return None

    def _append(
        self,
        *,
        artifact_key: str,
        kind: str,
        version: str,
        operation: str,
        payload: Mapping[str, Any] | None,
        actor: str,
        reason: str,
        expected_revision: str | None,
        idempotency_key: str | None,
        metadata: Mapping[str, Any] | None = None,
    ) -> MutationResult:
        key = stable_key(artifact_key)
        if operation not in {"create", "update", "tombstone", "restore", "migrate"}:
            raise ValidationError(f"unsupported operation: {operation}")
        if not isinstance(version, str) or not version.strip():
            raise ValidationError("version must be a non-empty string")
        if not isinstance(actor, str) or not actor.strip():
            raise ValidationError("actor must be a non-empty string")
        if operation != "tombstone":
            validate_kind(kind, payload)

        mutation_fingerprint = sha256_json({
            "artifact_key": key,
            "kind": kind,
            "version": version,
            "payload": payload,
            "actor": actor,
            "reason": reason,
            "metadata": metadata or {},
        })

        with self._lock():
            events = self._events()
            current = self._materialize(events).get(key)

            if idempotency_key:
                prior = self._find_idempotency(events, idempotency_key)
                if prior:
                    if prior.get("mutation_fingerprint") != mutation_fingerprint:
                        raise ConflictError("idempotency key reused for a different mutation")
                    return MutationResult(prior, idempotent_replay=True)

            if operation in {"update", "tombstone", "restore", "migrate"} and not reason.strip():
                raise ValidationError(f"{operation} requires a non-empty reason")

            if current is None:
                if operation not in {"create", "migrate"}:
                    raise ConflictError(f"{operation} requires an existing artifact")
                if expected_revision is not None:
                    raise ConflictError("new artifact cannot have expected_revision")
                artifact_id = str(uuid.uuid4())
                parent_revision = None
            else:
                artifact_id = current["artifact_id"]
                parent_revision = current["revision_id"]
                if expected_revision is None:
                    raise ConflictError(
                        "existing artifact mutation requires expected_revision; "
                        "blind overwrite/delete is prohibited"
                    )
                if expected_revision != parent_revision:
                    raise ConflictError(
                        f"stale expected_revision: expected current {parent_revision}"
                    )
                if current["tombstoned"] and operation != "restore":
                    raise DeletedError("artifact is tombstoned; restore before further mutation")
                if not current["tombstoned"] and operation == "restore":
                    raise ConflictError("restore requires a tombstoned current revision")
                if operation == "create":
                    raise ConflictError("artifact already exists; use update")

            payload_dict = dict(payload) if payload is not None else None
            payload_hash = sha256_json(payload_dict) if payload_dict is not None else None
            revision_basis = {
                "schema": SCHEMA,
                "artifact_id": artifact_id,
                "artifact_key": key,
                "kind": kind,
                "version": version,
                "operation": operation,
                "parent_revision": parent_revision,
                "payload_hash": payload_hash,
                "payload": payload_dict,
                "actor": actor,
                "reason": reason,
                "metadata": dict(metadata or {}),
            }
            revision_id = sha256_json(revision_basis)
            timestamp = utc_now()
            previous_event_hash = events[-1]["event_hash"] if events else None
            event = {
                **revision_basis,
                "sequence": len(events) + 1,
                "event_id": str(uuid.uuid4()),
                "revision_id": revision_id,
                "timestamp": timestamp,
                "previous_event_hash": previous_event_hash,
                "idempotency_key": idempotency_key,
                "mutation_fingerprint": mutation_fingerprint,
            }
            event["event_hash"] = self._event_hash(event)
            with self.ledger.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(event) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            events.append(event)
            self._write_index(events)
            return MutationResult(event)

    def put(
        self,
        artifact_key: str,
        kind: str,
        version: str,
        payload: Mapping[str, Any],
        *,
        actor: str,
        reason: str = "",
        expected_revision: str | None = None,
        idempotency_key: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> MutationResult:
        current = self.current_index().get(stable_key(artifact_key))
        operation = "create" if current is None else "update"
        return self._append(
            artifact_key=artifact_key, kind=kind, version=version, operation=operation,
            payload=payload, actor=actor, reason=reason,
            expected_revision=expected_revision, idempotency_key=idempotency_key,
            metadata=metadata,
        )

    def get(self, artifact_key: str, *, include_tombstoned: bool = False) -> dict[str, Any]:
        key = stable_key(artifact_key)
        for event in reversed(self._events()):
            if event["artifact_key"] == key:
                if event["operation"] == "tombstone" and not include_tombstoned:
                    raise DeletedError(f"{key} is tombstoned")
                return event
        raise KeyError(key)

    def history(self, artifact_key: str) -> list[dict[str, Any]]:
        key = stable_key(artifact_key)
        return [event for event in self._events() if event["artifact_key"] == key]

    def tombstone(
        self,
        artifact_key: str,
        *,
        expected_revision: str,
        actor: str,
        reason: str,
        idempotency_key: str | None = None,
    ) -> MutationResult:
        current = self.get(artifact_key)
        return self._append(
            artifact_key=artifact_key,
            kind=current["kind"],
            version=current["version"],
            operation="tombstone",
            payload=None,
            actor=actor,
            reason=reason,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            metadata={"preserved_revision": current["revision_id"]},
        )

    def restore(
        self,
        artifact_key: str,
        *,
        expected_revision: str,
        actor: str,
        reason: str,
        version: str | None = None,
        idempotency_key: str | None = None,
    ) -> MutationResult:
        tombstone = self.get(artifact_key, include_tombstoned=True)
        if tombstone["operation"] != "tombstone":
            raise ConflictError("artifact is not tombstoned")
        prior_live = None
        for event in reversed(self.history(artifact_key)[:-1]):
            if event["operation"] != "tombstone":
                prior_live = event
                break
        if prior_live is None:
            raise IntegrityError("no live revision available to restore")
        return self._append(
            artifact_key=artifact_key,
            kind=prior_live["kind"],
            version=version or prior_live["version"],
            operation="restore",
            payload=prior_live["payload"],
            actor=actor,
            reason=reason,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            metadata={
                "restored_from_revision": prior_live["revision_id"],
                "tombstone_revision": tombstone["revision_id"],
            },
        )

    def verify(self) -> dict[str, Any]:
        events = self._events()
        previous_hash = None
        current_revision: dict[str, str] = {}
        current_artifact_id: dict[str, str] = {}
        idempotency: dict[str, str] = {}
        for idx, event in enumerate(events, 1):
            required = {
                "schema", "sequence", "event_id", "artifact_id", "artifact_key", "kind",
                "version", "operation", "revision_id", "payload_hash", "timestamp",
                "previous_event_hash", "event_hash", "actor", "reason",
                "mutation_fingerprint", "metadata",
            }
            missing = sorted(required - set(event))
            if missing:
                raise IntegrityError(f"event {idx} missing fields: {', '.join(missing)}")
            if event["schema"] != SCHEMA:
                raise IntegrityError(f"event {idx} has unsupported schema")
            if event["sequence"] != idx:
                raise IntegrityError(f"event {idx} sequence mismatch")
            if event["previous_event_hash"] != previous_hash:
                raise IntegrityError(f"event {idx} chain predecessor mismatch")
            hash_basis = {k: v for k, v in event.items() if k != "event_hash"}
            if self._event_hash(hash_basis) != event["event_hash"]:
                raise IntegrityError(f"event {idx} event_hash mismatch")
            payload = event.get("payload")
            expected_payload_hash = sha256_json(payload) if payload is not None else None
            if event["payload_hash"] != expected_payload_hash:
                raise IntegrityError(f"event {idx} payload_hash mismatch")
            key = event["artifact_key"]
            prior_rev = current_revision.get(key)
            prior_id = current_artifact_id.get(key)
            if event["parent_revision"] != prior_rev:
                raise IntegrityError(f"event {idx} parent revision mismatch for {key}")
            if prior_id is not None and event["artifact_id"] != prior_id:
                raise IntegrityError(f"event {idx} stable artifact id changed for {key}")
            if event.get("idempotency_key"):
                idem = event["idempotency_key"]
                fp = event["mutation_fingerprint"]
                if idem in idempotency and idempotency[idem] != fp:
                    raise IntegrityError(f"conflicting idempotency key in ledger: {idem}")
                idempotency[idem] = fp
            current_revision[key] = event["revision_id"]
            current_artifact_id[key] = event["artifact_id"]
            previous_hash = event["event_hash"]

        materialized = self._materialize(events)
        on_disk = json.loads(self.index.read_text(encoding="utf-8")) if self.index.exists() else {}
        if on_disk != materialized:
            raise IntegrityError("materialized index does not match ledger")
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "events": len(events),
            "artifacts": len(materialized),
            "tombstones": sum(1 for x in materialized.values() if x["tombstoned"]),
            "last_event_hash": previous_hash,
            "index_matches": True,
        }

    def snapshot(self, *, actor: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise ValidationError("snapshot requires a reason")
        integrity = self.verify()
        events = self._events()
        current = self._materialize(events)
        live_records: dict[str, Any] = {}
        for key, state in current.items():
            event = self.get(key, include_tombstoned=True)
            live_records[key] = {
                "state": state,
                "payload": event.get("payload"),
                "metadata": event.get("metadata", {}),
            }
        body = {
            "schema": SNAPSHOT_SCHEMA,
            "snapshot_id": str(uuid.uuid4()),
            "created_at": utc_now(),
            "actor": actor,
            "reason": reason,
            "ledger_event_count": len(events),
            "last_event_hash": integrity["last_event_hash"],
            "records": live_records,
        }
        body["snapshot_hash"] = sha256_json(body)
        filename = f"{body['created_at'].replace(':', '').replace('+', '_')}-{body['snapshot_hash'][:16]}.json"
        _atomic_write(
            self.snapshots / filename,
            json.dumps(body, indent=2, sort_keys=True) + "\n",
        )
        return body

    def doctor(self) -> dict[str, Any]:
        metadata = self.init()
        integrity = self.verify()
        return {
            "status": "PASS",
            "store_id": metadata["store_id"],
            "hard_delete": metadata["hard_delete"],
            "integrity": integrity,
            "family_adapters": sorted(KIND_REQUIRED_FIELDS),
        }


def _git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if proc.returncode != 0:
        raise IntegrityError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()

def _blob_sha(repo: Path, ref: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", f"{ref}:{path}"], cwd=repo, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    return proc.stdout.strip() if proc.returncode == 0 else None

def load_policy(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "crownthrive.penta.serialized.policy/v1":
        raise ValidationError("unsupported continuity policy schema")
    return data

def _is_protected(path: str, policy: Mapping[str, Any]) -> bool:
    return any(
        fnmatch.fnmatch(path, pattern)
        for pattern in policy.get("protected_patterns", [])
    )

def collect_git_changes(repo: Path, base: str, head: str) -> list[dict[str, Any]]:
    output = _git(["diff", "--name-status", "--find-renames", f"{base}...{head}"], repo)
    changes = []
    for line in output.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        code = status[0]
        if code == "R":
            old, new = parts[1], parts[2]
            changes.append({"operation": "rename", "path": new, "old_path": old})
        else:
            path = parts[1]
            operation = {"A": "add", "M": "modify", "D": "delete"}.get(code, "modify")
            changes.append({"operation": operation, "path": path})
    return changes

def load_receipts(repo: Path, policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    pattern = policy.get("receipt_glob", "penta/continuity/receipts/*.json")
    receipts = []
    for path in sorted(repo.glob(pattern)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid receipt JSON: {path}") from exc
        if data.get("schema") != RECEIPT_SCHEMA:
            raise ValidationError(f"unsupported receipt schema: {path}")
        data["_path"] = path.relative_to(repo).as_posix()
        receipts.append(data)
    return receipts

def git_gate(repo: Path, base: str, head: str, policy_path: Path) -> dict[str, Any]:
    policy = load_policy(policy_path)
    changes = collect_git_changes(repo, base, head)
    receipts = load_receipts(repo, policy)
    receipt_entries: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for receipt in receipts:
        for item in receipt.get("changes", []):
            receipt_entries.setdefault((item.get("path"), item.get("operation")), []).append(
                {**item, "_receipt": receipt["_path"]}
            )

    violations: list[dict[str, Any]] = []
    checked = 0
    for change in changes:
        op, path = change["operation"], change["path"]
        requires = (
            op == "delete"
            or op == "rename"
            or (op == "modify" and _is_protected(path, policy))
        )
        if not requires:
            continue
        checked += 1
        candidates = receipt_entries.get((path, op), [])
        matched = False
        for item in candidates:
            if not item.get("reason") or not item.get("rollback_ref"):
                continue
            if op in {"modify", "delete"}:
                expected_previous = _blob_sha(repo, base, path)
                if item.get("previous_blob_sha") != expected_previous:
                    continue
            if op in {"modify", "rename"}:
                expected_new = _blob_sha(repo, head, path)
                if item.get("new_blob_sha") != expected_new:
                    continue
            if op == "delete" and not item.get("tombstone", False):
                continue
            if op == "rename":
                if item.get("old_path") != change.get("old_path"):
                    continue
                expected_previous = _blob_sha(repo, base, change["old_path"])
                if item.get("previous_blob_sha") != expected_previous:
                    continue
                if not item.get("successor"):
                    continue
            matched = True
            break
        if not matched:
            violations.append({
                **change,
                "reason": "missing or invalid PentaSerialized continuity receipt",
            })

    result = {
        "schema": "crownthrive.penta.serialized.git-gate/v1",
        "status": "PASS" if not violations else "HOLD",
        "base": base,
        "head": head,
        "changes": len(changes),
        "continuity_checked": checked,
        "violations": violations,
    }
    if violations:
        raise IntegrityError(canonical_json(result))
    return result

def _load_payload(value: str) -> dict[str, Any]:
    if value.startswith("@"):
        return json.loads(Path(value[1:]).read_text(encoding="utf-8"))
    return json.loads(value)

def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="penta-serialized")
    sub = p.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("store")

    put = sub.add_parser("put")
    put.add_argument("store")
    put.add_argument("artifact_key")
    put.add_argument("kind")
    put.add_argument("version")
    put.add_argument("payload", help="JSON or @path")
    put.add_argument("--actor", required=True)
    put.add_argument("--reason", default="")
    put.add_argument("--expected-revision")
    put.add_argument("--idempotency-key")

    get = sub.add_parser("get")
    get.add_argument("store")
    get.add_argument("artifact_key")
    get.add_argument("--include-tombstoned", action="store_true")

    hist = sub.add_parser("history")
    hist.add_argument("store")
    hist.add_argument("artifact_key")

    tomb = sub.add_parser("tombstone")
    tomb.add_argument("store")
    tomb.add_argument("artifact_key")
    tomb.add_argument("--expected-revision", required=True)
    tomb.add_argument("--actor", required=True)
    tomb.add_argument("--reason", required=True)
    tomb.add_argument("--idempotency-key")

    restore = sub.add_parser("restore")
    restore.add_argument("store")
    restore.add_argument("artifact_key")
    restore.add_argument("--expected-revision", required=True)
    restore.add_argument("--actor", required=True)
    restore.add_argument("--reason", required=True)
    restore.add_argument("--version")
    restore.add_argument("--idempotency-key")

    verify = sub.add_parser("verify")
    verify.add_argument("store")

    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("store")
    snapshot.add_argument("--actor", required=True)
    snapshot.add_argument("--reason", required=True)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("store")

    gate = sub.add_parser("git-gate")
    gate.add_argument("--repo", default=".")
    gate.add_argument("--base", required=True)
    gate.add_argument("--head", required=True)
    gate.add_argument("--policy", required=True)

    return p

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "git-gate":
            _print(git_gate(Path(args.repo), args.base, args.head, Path(args.policy)))
            return 0
        store = PentaSerializedStore(args.store)
        if args.command == "init":
            _print(store.init())
        elif args.command == "put":
            result = store.put(
                args.artifact_key, args.kind, args.version, _load_payload(args.payload),
                actor=args.actor, reason=args.reason,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
            )
            _print({"idempotent_replay": result.idempotent_replay, **result.event})
        elif args.command == "get":
            _print(store.get(args.artifact_key, include_tombstoned=args.include_tombstoned))
        elif args.command == "history":
            _print(store.history(args.artifact_key))
        elif args.command == "tombstone":
            _print(store.tombstone(
                args.artifact_key, expected_revision=args.expected_revision,
                actor=args.actor, reason=args.reason,
                idempotency_key=args.idempotency_key,
            ).event)
        elif args.command == "restore":
            _print(store.restore(
                args.artifact_key, expected_revision=args.expected_revision,
                actor=args.actor, reason=args.reason, version=args.version,
                idempotency_key=args.idempotency_key,
            ).event)
        elif args.command == "verify":
            _print(store.verify())
        elif args.command == "snapshot":
            _print(store.snapshot(actor=args.actor, reason=args.reason))
        elif args.command == "doctor":
            _print(store.doctor())
        else:  # pragma: no cover
            parser.error("unknown command")
        return 0
    except (PentaSerializedError, KeyError, json.JSONDecodeError) as exc:
        print(f"PentaSerialized HOLD: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
