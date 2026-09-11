#!/usr/bin/env python3
"""Universal Penta PR gate awareness and non-certifying originator readiness.

The originator may project exact-head evidence that a candidate is ready for
independent review. The projection is evidence only: it creates no certification,
provider truth, merge authority, D3 authority, or release authority.
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


EVIDENCE_SCHEMA = "ct.penta.pr.originator-readiness.v2"
RECEIPT_SCHEMA = "ct.penta.pr.originator-readiness-receipt.v2"
DEFAULT_POLICY = "config/penta_pr_gate_awareness.json"
DEFAULT_SERIALIZED_POLICY = "penta/registry/serialized-suite.json"
READY_STATE = "READY_FOR_INDEPENDENT_REVIEW"


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
        ["git", *args], cwd=repo, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise GateAwarenessError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _ensure_commit(repo: Path, ref: str) -> None:
    _git(repo, "cat-file", "-e", f"{ref}^{{commit}}")


def _blob_sha(repo: Path, ref: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", f"{ref}:{path}"], cwd=repo, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def _tree_sha(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", f"{ref}^{{tree}}")


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=repo,
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def evidence_path(number: int) -> str:
    return f"penta/evidence/pr-originator-readiness/pr-{number}.json"


def receipt_path(number: int) -> str:
    return f"penta/evidence/pr-originator-readiness/pr-{number}-receipt.json"


def _projection_paths(number: int) -> set[str]:
    return {evidence_path(number), receipt_path(number)}


def _contains_self_certification(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            "self_cert" in str(key).lower() or _contains_self_certification(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_self_certification(item) for item in value)
    return isinstance(value, str) and "SELF_CERT" in value.upper()


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
                "operation": "rename", "old_path": old_path, "path": path,
                "previous_blob_sha": _blob_sha(repo, base, old_path),
                "new_blob_sha": _blob_sha(repo, head, path),
            }
        else:
            path = parts[1]
            operation = {"A": "add", "M": "modify", "D": "delete"}.get(code, "modify")
            change = {
                "operation": operation, "path": path,
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


def build_continuity_receipt(*, repo: Path, base: str, subject_head: str, number: int,
                             originator: str, serialized_policy: Mapping[str, Any]) -> dict[str, Any]:
    controlled = [
        change for change in _source_changes(repo, base, subject_head, number)
        if _continuity_required(change, serialized_policy)
    ]
    items: list[dict[str, Any]] = []
    for change in controlled:
        item: dict[str, Any] = {
            "path": change["path"], "operation": change["operation"],
            "reason": f"PR #{number} originator readiness binds this controlled change to its exact source head and rollback baseline.",
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

    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": f"ct.penta.pr-originator-readiness.{number}.{subject_head[:12]}",
        "created_at": utc_now(), "actor": originator,
        "reason": f"Non-certifying originator-readiness evidence for PR #{number}; independent provider, security, governance, and certification gates remain mandatory.",
        "subject": {"pr_number": number, "base_sha": base, "subject_head_sha": subject_head},
        "changes": items,
        "readiness": {
            "state": READY_STATE, "originator": originator, "authority_created": False,
            "provider_results_manufactured": False, "final_gate_bypassed": False,
            "independent_certification_required": True,
        },
    }
    receipt["receipt_sha256"] = sha256_json(receipt)
    return receipt


def build_evidence_packet(*, repo: Path, repository: str, base: str, subject_head: str,
                          number: int, originator: str, policy: Mapping[str, Any],
                          receipt: Mapping[str, Any]) -> dict[str, Any]:
    changes = _source_changes(repo, base, subject_head, number)
    packet: dict[str, Any] = {
        "schema": EVIDENCE_SCHEMA, "policy_version": policy.get("version"),
        "repository": repository, "pr_number": number, "base_sha": base,
        "subject_head_sha": subject_head, "subject_tree_sha": _tree_sha(repo, subject_head),
        "rollback_ref": base, "originator_identity": originator,
        "readiness_state": READY_STATE,
        "readiness_scope": "originator_evidence_ready_for_independent_review",
        "authority_created": False, "independent_certification_required": True,
        "provider_results_manufactured": False, "required_gate_bypass": False,
        "final_institutional_certification_state": "PENDING_INDEPENDENT_GATES_READBACK_AND_DAIL",
        "dail_binding_state": "REQUIRED_BEFORE_INSTITUTIONAL_CERTIFICATION",
        "changes": changes, "change_set_sha256": sha256_json(changes),
        "continuity_receipt": {
            "path": receipt_path(number), "sha256": receipt.get("receipt_sha256"),
            "controlled_changes": len(receipt.get("changes", [])),
        },
        "gate_matrix": [
            {"context": context, "state": "PENDING_PROVIDER_READBACK"}
            for context in policy.get("gate_awareness", {}).get("required_contexts", [])
        ],
        "evidence_contract": {
            "exact_base": True, "exact_subject_head": True, "git_blob_identity": True,
            "rollback_preserved": True, "changed_file_manifest": True,
            "head_change_invalidates_packet": True, "provider_truth_remains_external": True,
            "originator_is_not_certifier": True,
        },
        "generated_at": utc_now(),
    }
    packet["evidence_sha256"] = sha256_json(packet)
    return packet


def _validate_hash(payload: Mapping[str, Any], field: str) -> None:
    observed = payload.get(field)
    basis = dict(payload)
    basis.pop(field, None)
    if observed != sha256_json(basis):
        raise GateAwarenessError(f"{field} mismatch")


def validate_projection(*, repo: Path, base: str, head: str, number: int,
                        policy_path: Path, serialized_policy_path: Path) -> dict[str, Any]:
    _ensure_commit(repo, base)
    _ensure_commit(repo, head)
    epath = repo / evidence_path(number)
    rpath = repo / receipt_path(number)
    if not epath.exists():
        raise GateAwarenessError(f"missing originator-readiness evidence blob: {evidence_path(number)}")
    if not rpath.exists():
        raise GateAwarenessError(f"missing originator-readiness evidence receipt: {receipt_path(number)}")

    policy = _load_json(policy_path)
    packet = _load_json(epath)
    receipt = _load_json(rpath)
    if packet.get("schema") != EVIDENCE_SCHEMA:
        raise GateAwarenessError("unsupported originator-readiness evidence schema")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise GateAwarenessError("unsupported originator-readiness receipt schema")
    if _contains_self_certification(packet) or _contains_self_certification(receipt):
        raise GateAwarenessError("originator certification vocabulary is prohibited")
    if packet.get("pr_number") != number or packet.get("base_sha") != base:
        raise GateAwarenessError("originator-readiness exact PR/base identity mismatch")
    if packet.get("readiness_state") != READY_STATE:
        raise GateAwarenessError("originator-readiness state is not ready for independent review")
    if packet.get("authority_created") is not False:
        raise GateAwarenessError("originator-readiness attempted to create authority")
    if packet.get("independent_certification_required") is not True:
        raise GateAwarenessError("originator-readiness removed independent certification")
    if packet.get("provider_results_manufactured") is not False or packet.get("required_gate_bypass") is not False:
        raise GateAwarenessError("originator-readiness attempted to manufacture provider truth or bypass a gate")

    readiness = receipt.get("readiness", {})
    if (readiness.get("state") != READY_STATE or readiness.get("authority_created") is not False
            or readiness.get("independent_certification_required") is not True
            or readiness.get("provider_results_manufactured") is not False
            or readiness.get("final_gate_bypassed") is not False):
        raise GateAwarenessError("originator-readiness receipt authority boundary invalid")

    _validate_hash(packet, "evidence_sha256")
    _validate_hash(receipt, "receipt_sha256")
    if packet.get("continuity_receipt", {}).get("sha256") != receipt.get("receipt_sha256"):
        raise GateAwarenessError("readiness packet is not bound to its evidence receipt")

    subject = str(packet.get("subject_head_sha") or "")
    _ensure_commit(repo, subject)
    if not _is_ancestor(repo, subject, head):
        raise GateAwarenessError("originator-readiness subject head is not an ancestor of the PR head")
    projection = collect_changes(repo, subject, head)
    unexpected = [item["path"] for item in projection if item["path"] not in _projection_paths(number)]
    if unexpected:
        raise GateAwarenessError("originator-readiness became stale after non-evidence changes: " + ", ".join(sorted(unexpected)))

    expected_changes = _source_changes(repo, base, subject, number)
    if packet.get("changes") != expected_changes or packet.get("change_set_sha256") != sha256_json(expected_changes):
        raise GateAwarenessError("originator-readiness change manifest/digest mismatch")
    if packet.get("subject_tree_sha") != _tree_sha(repo, subject):
        raise GateAwarenessError("originator-readiness source tree digest mismatch")
    required_contexts = policy.get("gate_awareness", {}).get("required_contexts", [])
    if [item.get("context") for item in packet.get("gate_matrix", [])] != required_contexts:
        raise GateAwarenessError("originator-readiness required-gate matrix drifted")

    proc = subprocess.run([
        sys.executable, "-m", "penta.runtime.serialized", "git-gate", "--repo", ".",
        "--base", base, "--head", subject, "--policy", str(serialized_policy_path.relative_to(repo)),
    ], cwd=repo, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise GateAwarenessError("PentaSerialized rejected originator-readiness continuity: " + (proc.stderr.strip() or proc.stdout.strip()))

    return {
        "schema": "ct.penta.pr.originator-readiness-validation.v2", "state": "PASS",
        "pr_number": number, "base_sha": base, "subject_head_sha": subject,
        "projection_head_sha": head, "originator": packet["originator_identity"],
        "source_changes": len(expected_changes), "continuity_changes": len(receipt.get("changes", [])),
        "evidence_sha256": packet["evidence_sha256"], "receipt_sha256": receipt["receipt_sha256"],
        "authority_created": False, "independent_certification_required": True,
        "final_institutional_certification": "STILL_REQUIRES_PROVIDER_GATES_READBACK_AND_DAIL",
    }


def prepare(*, repo: Path, repository: str, base: str, head: str, number: int,
            originator: str, policy_path: Path, serialized_policy_path: Path) -> dict[str, Any]:
    _ensure_commit(repo, base)
    _ensure_commit(repo, head)
    if (repo / evidence_path(number)).exists() and (repo / receipt_path(number)).exists():
        try:
            validation = validate_projection(repo=repo, base=base, head=head, number=number,
                                             policy_path=policy_path, serialized_policy_path=serialized_policy_path)
            return {"changed": False, "reason": "current_readiness_projection_valid", "validation": validation}
        except GateAwarenessError:
            pass
    policy = _load_json(policy_path)
    serialized_policy = _load_json(serialized_policy_path)
    receipt = build_continuity_receipt(repo=repo, base=base, subject_head=head, number=number,
                                       originator=originator, serialized_policy=serialized_policy)
    packet = build_evidence_packet(repo=repo, repository=repository, base=base, subject_head=head,
                                   number=number, originator=originator, policy=policy, receipt=receipt)
    rpath, epath = repo / receipt_path(number), repo / evidence_path(number)
    rpath.parent.mkdir(parents=True, exist_ok=True)
    epath.parent.mkdir(parents=True, exist_ok=True)
    rpath.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    epath.write_text(json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "changed": True, "reason": "originator_readiness_projection_written", "pr_number": number,
        "base_sha": base, "subject_head_sha": head, "evidence_path": evidence_path(number),
        "receipt_path": receipt_path(number), "evidence_sha256": packet["evidence_sha256"],
        "receipt_sha256": receipt["receipt_sha256"], "authority_created": False,
        "independent_certification_required": True,
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
    try:
        if args.command == "prepare":
            result = prepare(repo=repo, repository=args.repository, base=args.base, head=args.head,
                             number=args.pr_number, originator=args.originator,
                             policy_path=policy_path, serialized_policy_path=serialized_policy_path)
        else:
            result = validate_projection(repo=repo, base=args.base, head=args.head, number=args.pr_number,
                                         policy_path=policy_path, serialized_policy_path=serialized_policy_path)
    except GateAwarenessError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
