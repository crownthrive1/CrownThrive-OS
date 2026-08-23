#!/usr/bin/env python3
"""Fail closed on the retired missing-r spelling of ThriveBase.

Human-facing prose must use ``ThriveBase``. Machine identifiers may use the
lowercase canonical token ``thrivebase``. The historical missing-r variant is
not a valid executable identity, filename, schema, function, slug, or current
documentation label.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "automation" / "thrivebase-canonical-naming-contract.v1.json"
TEXT_SUFFIXES = {
    ".c", ".css", ".csv", ".go", ".graphql", ".h", ".html", ".java",
    ".js", ".json", ".jsx", ".md", ".mdx", ".mjs", ".php", ".py",
    ".rb", ".rs", ".sh", ".sql", ".svg", ".toml", ".ts", ".tsx",
    ".txt", ".xml", ".yaml", ".yml",
}
EXCLUDED_PREFIXES = (".git/", "node_modules/", "vendor/")
EXCLUDED_PATHS = {
    "automation/thrivebase-canonical-naming-contract.v1.json",
    "scripts/validate_thrivebase_canonical_spelling.py",
}
RETIRED_TOKEN = "thi" + "vebase"
RETIRED_RE = re.compile(rf"\b{re.escape(RETIRED_TOKEN)}\b", re.IGNORECASE)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_contract() -> dict:
    if not CONTRACT_PATH.is_file():
        fail(f"missing naming contract: {CONTRACT_PATH.relative_to(ROOT)}")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if contract.get("contract_id") != "ct.contract.thrivebase-canonical-naming.v1":
        fail("ThriveBase naming contract identity drifted")
    if contract.get("state") != "ACTIVE_FAIL_CLOSED":
        fail("ThriveBase naming contract must remain ACTIVE_FAIL_CLOSED")
    canonical = contract.get("canonical", {})
    if canonical.get("human_label") != "ThriveBase":
        fail("canonical human label must be ThriveBase")
    if canonical.get("machine_token") != "thrivebase":
        fail("canonical machine token must be thrivebase")
    if contract.get("ci", {}).get("full_tracked_text_scan") is not True:
        fail("canonical spelling contract must require a full tracked-text scan")
    return contract


def tracked_files() -> list[Path]:
    try:
        output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    except (OSError, subprocess.CalledProcessError) as exc:
        fail(f"unable to enumerate trusted tracked files: {exc}")
    paths: list[Path] = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8")
        if rel in EXCLUDED_PATHS or rel.startswith(EXCLUDED_PREFIXES):
            continue
        path = ROOT / rel
        if path.is_file():
            paths.append(path)
    return paths


def parser_self_test() -> None:
    bad_examples = (("THI" + "VEBASE"), ("Thi" + "veBase"), ("thi" + "vebase-queue-consumer"))
    for value in bad_examples:
        assert RETIRED_RE.search(value), value
    for value in ("ThriveBase", "thrivebase", "thrivebase-queue-consumer"):
        assert RETIRED_RE.search(value) is None, value


def main() -> int:
    parser_self_test()
    contract = load_contract()
    violations: list[str] = []
    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        if RETIRED_RE.search(rel):
            violations.append(f"{rel}: filename/path uses retired missing-r spelling")
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            if RETIRED_RE.search(line):
                excerpt = line.strip()
                if len(excerpt) > 180:
                    excerpt = excerpt[:177] + "..."
                violations.append(f"{rel}:{line_number}: {excerpt}")
    if violations:
        preview = "\n".join(violations[:100])
        remainder = len(violations) - min(len(violations), 100)
        suffix = f"\n... and {remainder} additional violation(s)" if remainder else ""
        fail("retired ThriveBase spelling detected; use ThriveBase in prose and "
             f"thrivebase in machine identifiers:\n{preview}{suffix}")
    runtime = contract.get("legacy_runtime_compatibility", {})
    if runtime.get("state") != "QUARANTINED_PENDING_DEPENDENCY_TESTED_CUTOVER":
        fail("legacy runtime compatibility state drifted")
    if runtime.get("destructive_rename_authorized") is not False:
        fail("destructive runtime rename must remain unauthorized")
    print("ThriveBase canonical spelling contract passed.")
    print("Human label: ThriveBase; machine token: thrivebase.")
    print("Tracked text and paths contain no retired missing-r spelling.")
    print("Legacy runtime aliases remain quarantined pending dependency-tested cutover.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
