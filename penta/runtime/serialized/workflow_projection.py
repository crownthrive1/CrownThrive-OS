"""Exact-head ephemeral continuity projection for modified GitHub Actions workflows.

This module is deliberately narrow. It may derive lineage/rollback evidence only
for in-place modifications of protected files under ``.github/workflows/``.
Deletes, renames, and every non-workflow protected path remain subject to the
normal committed PentaSerialized continuity-receipt contract.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
from pathlib import Path
from typing import Any

from .core import (
    RECEIPT_SCHEMA,
    IntegrityError,
    _blob_sha,
    _is_protected,
    collect_git_changes,
    load_policy,
)


def project_workflow_receipt(
    repo: Path,
    base: str,
    head: str,
    policy_path: Path,
    output_path: Path,
    *,
    actor: str = "github-actions[bot]",
    rollback_ref: str | None = None,
    receipt_id: str | None = None,
) -> dict[str, Any]:
    """Project an ephemeral receipt for exact workflow modifications only.

    The returned receipt has no approval semantics. The caller may temporarily
    place it beneath the policy receipt glob while invoking ``git_gate`` and
    must remove that temporary copy afterward.
    """
    repo = repo.resolve()
    policy_path = policy_path if policy_path.is_absolute() else repo / policy_path
    output_path = output_path if output_path.is_absolute() else repo / output_path
    policy = load_policy(policy_path)
    changes = collect_git_changes(repo, base, head)
    entries: list[dict[str, Any]] = []

    for change in changes:
        operation = change["operation"]
        path = change["path"]
        if operation != "modify":
            continue
        if not path.startswith(".github/workflows/"):
            continue
        if not _is_protected(path, policy):
            continue

        previous = _blob_sha(repo, base, path)
        current = _blob_sha(repo, head, path)
        if not previous or not current:
            raise IntegrityError(f"exact workflow lineage unresolved for {path}")
        entries.append({
            "path": path,
            "operation": "modify",
            "previous_blob_sha": previous,
            "new_blob_sha": current,
            "reason": (
                "CI-derived exact-head continuity projection for an in-place "
                "GitHub Actions workflow modification; lineage/rollback evidence "
                "only and not merge, release, certification, or provider authority."
            ),
            "rollback_ref": rollback_ref or base,
        })

    with contextlib.suppress(FileNotFoundError):
        output_path.unlink()

    result: dict[str, Any] = {
        "schema": "crownthrive.penta.serialized.workflow-projection-result/v1",
        "generated": bool(entries),
        "base": base,
        "head": head,
        "eligible_changes": len(entries),
        "output": str(output_path),
    }
    if not entries:
        return result

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": receipt_id or (
            f"ct.penta.serialized.ci-workflow-projection.{head[:12]}"
        ),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "actor": actor,
        "reason": (
            "Exact-head machine-derived continuity projection for modified GitHub "
            "Actions workflow blobs. This record proves lineage and rollback only; "
            "it grants zero independent approval or merge authority."
        ),
        "changes": entries,
        "continuity": {
            "silent_replacement": False,
            "silent_delete": False,
            "tombstones": [],
            "successors": [],
            "rollback_preserved": True,
            "projection_scope": "modified_existing_github_workflows_only",
        },
        "exclusions": [
            "No delete or rename is auto-receipted.",
            "No non-workflow protected path is auto-receipted.",
            "No merge, release, certification, provider, credential, rights, or financial authority is manufactured.",
            "The receipt is ephemeral workflow evidence and is never committed back to the candidate branch.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result["receipt_id"] = receipt["receipt_id"]
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="penta-serialized-workflow-projection")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--actor", default="github-actions[bot]")
    parser.add_argument("--rollback-ref")
    parser.add_argument("--receipt-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = project_workflow_receipt(
            Path(args.repo),
            args.base,
            args.head,
            Path(args.policy),
            Path(args.output),
            actor=args.actor,
            rollback_ref=args.rollback_ref,
            receipt_id=args.receipt_id,
        )
    except (IntegrityError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"PentaSerialized workflow projection HOLD: {exc}")
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
