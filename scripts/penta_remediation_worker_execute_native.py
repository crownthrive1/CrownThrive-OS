#!/usr/bin/env python3
"""Bounded remediation writeback using the workflow-scoped GitHub token.

Same-repository read/comment/label operations use GITHUB_TOKEN rather than the
shared PentaPM PAT. Sweeps process only remediation PRs that still carry
``penta:hold``. Most importantly, verified ``no_code_delta`` resolutions are
represented by their durable DAIL/database receipt and PR comment; they never
create or refresh a synthetic execution-receipt commit on the PR branch.
Actual code repair deltas retain the canonical branch-receipt path.
"""
from __future__ import annotations

import os
from typing import Any

from scripts import penta_remediation_worker_execute as worker


def main() -> int:
    native = os.environ.get("GITHUB_TOKEN") or ""
    if not native:
        raise SystemExit("workflow_scoped_github_token_required")

    # Keep the canonical vaulted PentaPM token untouched. The base worker reads
    # this environment name, so bind it only inside this process to github.token.
    os.environ["PENTA_PM_GITHUB_TOKEN"] = native

    original_open_prs = worker.GH.open_prs
    original_labels_for = worker.labels_for
    original_write_receipt = worker.write_receipt_file
    label_cache: dict[int, set[str]] = {}

    def cached_labels(gh: worker.GH, number: int) -> set[str]:
        if number not in label_cache:
            label_cache[number] = original_labels_for(gh, number)
        return label_cache[number]

    def held_remediation_prs(gh: worker.GH) -> list[dict[str, Any]]:
        kept: list[dict[str, Any]] = []
        for pr in original_open_prs(gh):
            number = int(pr["number"])
            labels = cached_labels(gh, number)
            if "penta:remediation" in labels and "penta:hold" in labels:
                kept.append(pr)
        return kept

    def bounded_receipt_write(
        gh: worker.GH,
        pr: dict[str, Any],
        execution: dict[str, Any],
    ) -> str | None:
        receipt = execution.get("receipt") or {}
        if bool(receipt.get("no_code_delta")):
            return None
        return original_write_receipt(gh, pr, execution)

    worker.labels_for = cached_labels
    worker.GH.open_prs = held_remediation_prs
    worker.write_receipt_file = bounded_receipt_write
    return worker.main()


if __name__ == "__main__":
    raise SystemExit(main())
