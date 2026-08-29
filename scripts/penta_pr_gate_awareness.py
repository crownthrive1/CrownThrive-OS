#!/usr/bin/env python3
"""Universal Penta PR gate-awareness and originator self-certification.

The engine lets the originating Penta submit its own exact-head evidence and
continuity blobs. SELF_CERTIFIED means the originator has produced a complete,
hash-bound candidate evidence packet; it never fabricates provider gate results
and it does not replace repository-required gates, destination readback, DAIL
binding, or D3/human-reserved authority.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


EVIDENCE_SCHEMA = "ct.penta.pr.self-certification.v1"
RECEIPT_SCHEMA = "crownthrive.penta.serialized.git-receipt/v1"
DEFAULT_POLICY = "config/penta_pr_gate_awareness.json"
DEFAULT_SERIALIZED_POLICY = "penta/registry/serialized-suite.json"


class GateAwarenessError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise GateAwarenessError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _ensure_commit(repo: Path, ref: str) -> None:
    _git(repo, "cat-file", "-e", f"{ref}^{{commit}}")


def _blob_sha(repo: Path, ref: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", f"{ref}:{path}"],
        cwd=repo,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def _tree_sha(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", f"{ref}^{{tree}}")


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def evidence_path(number: int) -> str:
    return f"penta/evidence/pr-self-cert/pr-{number}.json"


def receipt_path(number: int) -> str:
    return f"penta/continuity/receipts/pr-{number}-self-certification.json"


def _projection_paths(number: int) -> set[str]:
    return {evidence_path(number), receipt_path(number)}


def collect_changes(repo: Path, base: str, head: str) -> list[dict[str, Any]]:
    raw = _git(repo, "diff", "--name-status", "--find-renames", f"{base}...{head}")
    changes: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        code = status[0]
        if code == "R":
            old_path, path = parts[1], parts[2]
            change = {
                "operation": "rename",
                "old_path": old_path,
                "path": path,
                "previous_blob_sha": _blob_sha(repo, base, old_path),
                "new_blob_sha": _blob_sha(repo, head, path),
            }
        else:
            path = parts[1]
            operation = {"A": "add", "M": "modify", "D": "delete"}.get(code, "modify")
            change = {
                "operation": operation,
                "path": path,
                "previous_blob_sha": _blob_sha(repo, base, path),
                "new_blob_sha": _blob_sha(repo, head, path),
            }
        changes.append(change)
    return sorted(changes, key=lambda item: (item["path"], item["operation"]))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateAwarenessError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise GateAwarenessError(f"expected JSON object: {path}")
    return value


def _is_protected(path: str, serialized_policy: Mapping[str, Any]) -> bool:
    import fnmatch

    return any(fnmatch.fnmatch(path, pattern) for pattern in serialized_policy.get("protected_patterns", []))


def _continuity_required(change: Mapping[str, Any], serialized_policy: Mapping[str, Any]) -> bool:
    operation = change["operation"]
    if operation in {"delete", "rename"}:
        return True
    return operation == "modify" and _is_protected(str(change["path"]), serialized_policy)


def _source_changes(repo: Path, base: str, subject_head: str, number: int) -> list[dict[str, Any]]:
    excluded = _projection_paths(number)
    return [change for change in collect_changes(repo, base, subject_head) if change["path"] not in excluded]


def build_continuity_receipt(
    *,
    repo: Path,
    base: str,
    subject_head: str,
    number: int,
    originator: str,
    serialized_policy: Mapping[str, Any],
) -> dict[str, Any]:
    controlled = [
        change for change in _source_changes(repo, base, subject_head, number)
        if _continuity_required(change, serialized_policy)
    ]
    items: list[dict[str, Any]] = []
    for change in controlled:
        item = {
            "path": change["path"],
            "operation": change["operation"],
            "reason": (
                f"PR #{number} originator self-certification binds this protected change "
                "to its exact source head and rollback baseline."
            ),
            "rollback_ref": base,
        }
        if change.get("previous_blob_sha") is not None:
            item["previous_blob_sha"] = change["previous_blob_sha"]
        if change.get("new_blob_sha") is not None:
            item["new_blob_sha"] = change["new_blob_sha"]
        if change["operation"] == "delete":
            item["tombstone"] = True
        if change["operation"] == "rename":
            item["old_path"] = change["old_path"]
            item["successor"] = change["path"]
        items.append(item)

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": f"ct.penta.pr-self-cert.{number}.{subject_head[:12]}",
        "created_at": utc_now(),
        "actor": originator,
        "reason": (
            f"Originator self-certification continuity packet for PR #{number}; "
            "preserves exact-source lineage and rollback while final provider gates remain independent."
        ),
        "subject": {
            "pr_number": number,
            "base_sha": base,
            "subject_head_sha": subject_head,
        },
        "changes": items,
        "self_certification": {
            "state": "SELF_CERTIFIED",
            "originator": originator,
            "provider_results_manufactured": False,
            "final_gate_bypassed": False,
        },
    }
    receipt["receipt_sha256"] = sha256_json(receipt)
    return receipt


def build_evidence_packet(
    *,
    repo: Path,
    repository: str,
    base: str,
    subject_head: str,
    number: int,
    originator: str,
    policy: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    changes = _source_changes(repo, base, subject_head, number)
    packet = {
        "schema": EVIDENCE_SCHEMA,
        "policy_version": policy.get("version"),
        "repository": repository,
        "pr_number": number,
        "base_sha": base,
        "subject_head_sha": subject_head,
        "subject_tree_sha": _tree_sha(repo, subject_head),
        "rollback_ref": base,
        "originator_identity": originator,
        "self_certifier_identity": originator,
        "self_certification_state": "SELF_CERTIFIED",
        "self_certification_scope": "originator_evidence_and_gate_readiness",
        "provider_results_manufactured": False,
        "required_gate_bypass": False,
        "final_institutional_certification_state": "PENDING_REQUIRED_GATES_READBACK_AND_DAIL",
        "dail_binding_state": "REQUIRED_BEFORE_INSTITUTIONAL_CERTIFICATION",
        "changes": changes,
        "change_set_sha256": sha256_json(changes),
        "continuity_receipt": {
            "path": receipt_path(number),
            "sha256": receipt.get("receipt_sha256"),
            "controlled_changes": len(receipt.get("changes", [])),
        },
        "gate_matrix": [
            {"context": context, "state": "PENDING_PROVIDER_READBACK"}
            for context in policy.get("gate_awareness", {}).get("required_contexts", [])
        ],
        "evidence_contract": {
            "exact_base": True,
            "exact_subject_head": True,
            "git_blob_identity": True,
            "rollback_preserved": True,
            "changed_file_manifest": True,
            "head_change_invalidates_packet": True,
            "provider_truth_remains_external": True,
        },
        "generated_at": utc_now(),
    }
    packet["evidence_sha256"] = sha256_json(packet)
    return packet


def _validate_hash(payload: Mapping[str, Any], field: str) -> None:
    observed = payload.get(field)
    basis = dict(payload)
    basis.pop(field, None)
    expected = sha256_json(basis)
    if observed != expected:
        raise GateAwarenessError(f"{field} mismatch")


def validate_projection(
    *,
    repo: Path,
    base: str,
    head: str,
    number: int,
    policy_path: Path,
    serialized_policy_path: Path,
) -> dict[str, Any]:
    _ensure_commit(repo, base)
    _ensure_commit(repo, head)
    epath = repo / evidence_path(number)
    rpath = repo / receipt_path(number)
    if not epath.exists():
        raise GateAwarenessError(f"missing self-certification evidence blob: {evidence_path(number)}")
    if not rpath.exists():
        raise GateAwarenessError(f"missing continuity receipt blob: {receipt_path(number)}")

    policy = _load_json(policy_path)
    packet = _load_json(epath)
    receipt = _load_json(rpath)
    if packet.get("schema") != EVIDENCE_SCHEMA:
        raise GateAwarenessError("unsupported self-certification evidence schema")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise GateAwarenessError("unsupported continuity receipt schema")
    if packet.get("pr_number") != number:
        raise GateAwarenessError("self-certification PR identity mismatch")
    if packet.get("base_sha") != base:
        raise GateAwarenessError("self-certification base SHA is stale")
    if packet.get("self_certification_state") != "SELF_CERTIFIED":
        raise GateAwarenessError("originator self-certification is not PASS")
    if packet.get("provider_results_manufactured") is not False or packet.get("required_gate_bypass") is not False:
        raise GateAwarenessError("self-certification attempted to manufacture provider truth or bypass a gate")
    if packet.get("originator_identity") != packet.get("self_certifier_identity"):
        raise GateAwarenessError("originator self-certifier identity is not self-bound")

    _validate_hash(packet, "evidence_sha256")
    _validate_hash(receipt, "receipt_sha256")
    if packet.get("continuity_receipt", {}).get("sha256") != receipt.get("receipt_sha256"):
        raise GateAwarenessError("evidence packet is not bound to the continuity receipt")

    subject = str(packet.get("subject_head_sha") or "")
    _ensure_commit(repo, subject)
    if not _is_ancestor(repo, subject, head):
        raise GateAwarenessError("self-certification subject head is not an ancestor of the PR head")

    projection = collect_changes(repo, subject, head)
    allowed = _projection_paths(number)
    unexpected = [item["path"] for item in projection if item["path"] not in allowed]
    if unexpected:
        raise GateAwarenessError(
            "self-certification became stale after non-evidence changes: " + ", ".join(sorted(unexpected))
        )

    expected_changes = _source_changes(repo, base, subject, number)
    if packet.get("changes") != expected_changes:
        raise GateAwarenessError("self-certification change manifest does not match trusted Git diff")
    if packet.get("change_set_sha256") != sha256_json(expected_changes):
        raise GateAwarenessError("self-certification change-set digest mismatch")
    if packet.get("subject_tree_sha") != _tree_sha(repo, subject):
        raise GateAwarenessError("self-certification source tree digest mismatch")

    required_contexts = policy.get("gate_awareness", {}).get("required_contexts", [])
    observed_contexts = [item.get("context") for item in packet.get("gate_matrix", [])]
    if observed_contexts != required_contexts:
        raise GateAwarenessError("self-certification required-gate matrix drifted")

    # Re-run the canonical PentaSerialized gate against the exact source diff.
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "penta.runtime.serialized",
            "git-gate",
            "--repo",
            ".",
            "--base",
            base,
            "--head",
            subject,
            "--policy",
            str(serialized_policy_path.relative_to(repo)),
        ],
        cwd=repo,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise GateAwarenessError(
            "PentaSerialized rejected originator continuity evidence: " + (proc.stderr.strip() or proc.stdout.strip())
        )

    return {
        "schema": "ct.penta.pr.self-certification-validation.v1",
        "state": "PASS",
        "pr_number": number,
        "base_sha": base,
        "subject_head_sha": subject,
        "projection_head_sha": head,
        "originator": packet["originator_identity"],
        "source_changes": len(expected_changes),
        "continuity_changes": len(receipt.get("changes", [])),
        "evidence_sha256": packet["evidence_sha256"],
        "receipt_sha256": receipt["receipt_sha256"],
        "final_institutional_certification": "STILL_REQUIRES_PROVIDER_GATES_READBACK_AND_DAIL",
    }


def prepare(
    *,
    repo: Path,
    repository: str,
    base: str,
    head: str,
    number: int,
    originator: str,
    policy_path: Path,
    serialized_policy_path: Path,
) -> dict[str, Any]:
    _ensure_commit(repo, base)
    _ensure_commit(repo, head)

    # If the current head is already a valid source+evidence projection, do not
    # generate another evidence commit. This makes synchronize events idempotent.
    if (repo / evidence_path(number)).exists() and (repo / receipt_path(number)).exists():
        try:
            validation = validate_projection(
                repo=repo,
                base=base,
                head=head,
                number=number,
                policy_path=policy_path,
                serialized_policy_path=serialized_policy_path,
            )
            return {"changed": False, "reason": "current_projection_valid", "validation": validation}
        except GateAwarenessError:
            pass

    policy = _load_json(policy_path)
    serialized_policy = _load_json(serialized_policy_path)
    receipt = build_continuity_receipt(
        repo=repo,
        base=base,
        subject_head=head,
        number=number,
        originator=originator,
        serialized_policy=serialized_policy,
    )
    packet = build_evidence_packet(
        repo=repo,
        repository=repository,
        base=base,
        subject_head=head,
        number=number,
        originator=originator,
        policy=policy,
        receipt=receipt,
    )

    rpath = repo / receipt_path(number)
    epath = repo / evidence_path(number)
    rpath.parent.mkdir(parents=True, exist_ok=True)
    epath.parent.mkdir(parents=True, exist_ok=True)
    rpath.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    epath.write_text(json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "changed": True,
        "reason": "self_certification_projection_written",
        "pr_number": number,
        "base_sha": base,
        "subject_head_sha": head,
        "evidence_path": evidence_path(number),
        "receipt_path": receipt_path(number),
        "evidence_sha256": packet["evidence_sha256"],
        "receipt_sha256": receipt["receipt_sha256"],
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("prepare", "validate"):
        s = sub.add_parser(name)
        s.add_argument("--repo", default=".")
        s.add_argument("--repository", default="crownthrive1/CrownThrive-OS")
        s.add_argument("--base", required=True)
        s.add_argument("--head", required=True)
        s.add_argument("--pr-number", type=int, required=True)
        s.add_argument("--policy", default=DEFAULT_POLICY)
        s.add_argument("--serialized-policy", default=DEFAULT_SERIALIZED_POLICY)
        if name == "prepare":
            s.add_argument("--originator", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = repo / policy_path
    serialized_policy_path = Path(args.serialized_policy)
    if not serialized_policy_path.is_absolute():
        serialized_policy_path = repo / serialized_policy_path

    if args.command == "prepare":
        result = prepare(
            repo=repo,
            repository=args.repository,
            base=args.base,
            head=args.head,
            number=args.pr_number,
            originator=args.originator,
            policy_path=policy_path,
            serialized_policy_path=serialized_policy_path,
        )
    else:
        result = validate_projection(
            repo=repo,
            base=args.base,
            head=args.head,
            number=args.pr_number,
            policy_path=policy_path,
            serialized_policy_path=serialized_policy_path,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
