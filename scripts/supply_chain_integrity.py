#!/usr/bin/env python3
"""Static, dependency-free governance checks for GitHub Actions workflows."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ACTION_RE = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)
PIN_RE = re.compile(r"^[^@]+@[0-9a-fA-F]{40}$")
DANGEROUS_PATTERNS = {
    "pull_request_target": re.compile(r"^\s*pull_request_target\s*:", re.MULTILINE),
    "id_token_write": re.compile(r"^\s*id-token\s*:\s*write\s*$", re.MULTILINE),
    "curl_pipe_shell": re.compile(r"\bcurl\b[^\n|]*\|\s*(?:ba)?sh\b"),
    "wget_pipe_shell": re.compile(r"\bwget\b[^\n|]*\|\s*(?:ba)?sh\b"),
    "destructive_git": re.compile(r"\bgit\s+(?:push\s+--force|reset\s+--hard)\b"),
    "recursive_delete": re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b"),
}


def inspect_workflow(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    warnings: list[str] = []
    actions = ACTION_RE.findall(text)
    for action in actions:
        if action.startswith("./") or action.startswith("docker://"):
            continue
        if not PIN_RE.fullmatch(action):
            errors.append(f"action is not pinned to a 40-hex commit: {action}")
    if not re.search(r"(?ms)^permissions:\s*\n\s+contents:\s*read\s*$", text):
        errors.append("top-level read-only contents permission is required")
    if "timeout-minutes:" not in text:
        errors.append("bounded timeout-minutes is required")
    if "concurrency:" not in text or "cancel-in-progress:" not in text:
        errors.append("concurrency cancellation is required")
    for label, pattern in DANGEROUS_PATTERNS.items():
        if pattern.search(text):
            errors.append(f"forbidden workflow pattern: {label}")
    if re.search(r"^\s*schedule\s*:", text, re.MULTILINE) and 'cron: "52 * * * *"' not in text:
        warnings.append("suite dispatcher should use the reserved minute-52 lane")
    if "workflow_dispatch:" not in text:
        warnings.append("workflow lacks manual dispatch for controlled verification")
    if "pull_request:" not in text:
        warnings.append("workflow lacks pull-request validation")
    return {
        "path": str(path),
        "status": "FAIL" if errors else ("PASS_WITH_WARNINGS" if warnings else "PASS"),
        "actions": actions,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    rows = []
    for path in args.paths:
        if not path.is_file():
            rows.append({"path": str(path), "status": "FAIL", "errors": ["file not found"]})
        else:
            rows.append(inspect_workflow(path))
    status = "FAIL" if any(row["status"] == "FAIL" for row in rows) else "PASS"
    print(json.dumps({"status": status, "workflows": rows}, indent=2, sort_keys=True))
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
