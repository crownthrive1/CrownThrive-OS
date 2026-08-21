#!/usr/bin/env python3
"""Static, dependency-free governance checks for GitHub Actions workflows."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ACTION_RE = re.compile(r"^\s*(?:-\s*)?['\"]?uses['\"]?\s*:\s*([^\s#]+)", re.MULTILINE)
FLOW_ACTION_RE = re.compile(
    r"(?:^\s*(?:-\s*)?\{|^\s*['\"]?steps['\"]?\s*:\s*\[\s*\{)"
    r"[^#\n]*?['\"]?uses['\"]?\s*:\s*([^\s,#}\]]+)",
    re.MULTILINE,
)
PIN_RE = re.compile(r"^[^@\s]+@[0-9a-fA-F]{40}$")
DOCKER_PIN_RE = re.compile(r"^docker://[^@\s]+@sha256:[0-9a-fA-F]{64}$")
PERSIST_CREDENTIALS_RE = re.compile(
    r"^\s*['\"]?persist-credentials['\"]?\s*:\s*([^\s#]+)", re.MULTILINE
)
DANGEROUS_PATTERNS = {
    "pull_request_target": re.compile(
        r"(?:^\s*['\"]?pull_request_target['\"]?\s*:|"
        r"^\s*['\"]?on['\"]?\s*:\s*[\[{][^#\n]*?\bpull_request_target\b)",
        re.MULTILINE,
    ),
    "flow_style_on": re.compile(r"^\s*['\"]?on['\"]?\s*:\s*[\[{]", re.MULTILINE),
    "id_token_write": re.compile(
        r"^\s*['\"]?id-token['\"]?\s*:\s*['\"]?write['\"]?\s*$", re.MULTILINE
    ),
    "curl_pipe_shell": re.compile(r"\bcurl\b[^\n|]*\|\s*(?:ba)?sh\b"),
    "wget_pipe_shell": re.compile(r"\bwget\b[^\n|]*\|\s*(?:ba)?sh\b"),
    "destructive_git": re.compile(r"\bgit\s+(?:push\s+--force|reset\s+--hard)\b"),
    "recursive_delete": re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b"),
}


def permission_errors(text: str) -> list[str]:
    errors: list[str] = []
    lines = text.splitlines()
    top_level_contents_read = False
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)['\"]?permissions['\"]?\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        indent = len(match.group(1).expandtabs(2))
        inline = match.group(2).strip().strip("'\"").lower()
        if inline:
            if "write" in inline:
                errors.append("write-capable inline permissions are forbidden")
            if indent == 0 and inline == "read-all":
                top_level_contents_read = True
            continue
        block_values: dict[str, str] = {}
        for child in lines[index + 1 :]:
            if not child.strip() or child.lstrip().startswith("#"):
                continue
            child_indent = len(child) - len(child.lstrip(" \t"))
            if child_indent <= indent:
                break
            item = re.match(
                r"^\s*['\"]?([A-Za-z0-9_-]+)['\"]?\s*:\s*([^#]+?)\s*$",
                child,
            )
            if item:
                block_values[item.group(1).lower()] = item.group(2).strip().strip("'\"").lower()
        write_keys = sorted(key for key, value in block_values.items() if value in {"write", "write-all"})
        if write_keys:
            errors.append("write-capable permissions are forbidden: " + ", ".join(write_keys))
        if indent == 0 and block_values.get("contents") == "read":
            top_level_contents_read = True
    if not top_level_contents_read:
        errors.append("top-level read-only contents permission is required")
    return errors


def inspect_workflow(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    warnings: list[str] = []
    actions = [
        action.strip("'\"")
        for action in [*ACTION_RE.findall(text), *FLOW_ACTION_RE.findall(text)]
    ]
    for action in actions:
        if action.startswith("./"):
            if not action.startswith("./.github/actions/") or ".." in Path(action).parts:
                errors.append(f"local action escapes the governed action root: {action}")
            continue
        if action.startswith("docker://"):
            if not DOCKER_PIN_RE.fullmatch(action):
                errors.append(f"container action is not pinned to a sha256 digest: {action}")
            continue
        if not PIN_RE.fullmatch(action):
            errors.append(f"action is not pinned to a 40-hex commit: {action}")
    checkout_count = sum(action.startswith("actions/checkout@") for action in actions)
    if checkout_count:
        persist_values = [value.strip("'\"").lower() for value in PERSIST_CREDENTIALS_RE.findall(text)]
        if len([value for value in persist_values if value == "false"]) < checkout_count:
            errors.append("each actions/checkout step must set persist-credentials: false")
        if any(value != "false" for value in persist_values):
            errors.append("persist-credentials may not be enabled anywhere in the workflow")
    errors.extend(permission_errors(text))
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
    expanded: list[Path] = []
    for path in args.paths:
        if path.is_dir():
            expanded.extend(sorted({*path.rglob("*.yml"), *path.rglob("*.yaml")}))
        else:
            expanded.append(path)
    for path in expanded:
        if not path.is_file():
            rows.append({"path": str(path), "status": "FAIL", "errors": ["file not found"]})
        else:
            rows.append(inspect_workflow(path))
    status = "FAIL" if any(row["status"] == "FAIL" for row in rows) else "PASS"
    print(json.dumps({"status": status, "workflows": rows}, indent=2, sort_keys=True))
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
