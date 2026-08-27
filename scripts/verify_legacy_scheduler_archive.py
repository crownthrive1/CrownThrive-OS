#!/usr/bin/env python3
"""Fail closed when a change reintroduces A/B/C/D/S one-agent-one-clock scheduling.

This guard distinguishes legitimate historical, evidentiary, governance, certification,
and capability references from executable scheduling authority. It does not erase
immutable migrations or historical records.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
from collections.abc import Iterable

# Require an actual separator before the role letter. This prevents the ordinary
# plural word "agents" from being interpreted as the historical "Agent S" role.
ROLE = re.compile(
    r"(?i)(?:^|[^a-z0-9])(?:agent(?:[ ._/-]+)[abcds]|a/b/c/d/s|original[ ._-]?five|one[ ._-]?agent[ ._-]?one[ ._-]?clock)(?:[^a-z0-9]|$)"
)
CLOCK = re.compile(
    r"(?i)(schedule|scheduler|clock|chatgpt|external[ ._-]?task|recurring[ ._-]?task|hourly[ ._-]?relay|provider[ ._-]?task)"
)

# Explicit historical and prohibition language is allowed. These phrases state
# that the old topology cannot execute; they are not evidence of reactivation.
HISTORICAL_OR_PROHIBITED = re.compile(
    r"(?i)("
    r"historical(?:-only)?|history|retired(?:_scheduling_scaffolding)?|superseded|"
    r"archiv(?:e|ed|al)|former|prior|dated context|"
    r"do not reactivate|must not be reactivated|reactivation prohibited|"
    r"no current clock|has no current clock|no standalone clock|"
    r"not a replacement|not retained as runnable|not part of the current|"
    r"do not create|must not create|does not create|cannot create|cannot schedule"
    r")"
)
OLD_PROVIDER_TASK_IDS = {
    "6a85065e56f08191aefd4180c2038452",
    "6a8c7dc030988191944f67b75d54e891",
    "6a85129d5b74819188cc0790c923efed",
}

ALLOWED_EXACT = {
    ".github/workflows/legacy-scheduler-scaffolding-recurrence-guard.yml",
    "governance/archive/legacy-abcds-scheduler-scaffolding.v1.json",
    "institutional-archive/legacy-scheduler/legacy-abcds-scheduler-archive-2026-08-27.json",
    "knowledge/legacy-abcds-scheduler-scaffolding-archive.mdx",
    "scripts/validate-legacy-abcds-scheduler-archive.sql",
    "scripts/verify_legacy_scheduler_archive.py",
    "supabase/migrations/20260827164000_archive_legacy_abcds_scheduler_scaffolding_v1.sql",
    "tests/test_legacy_scheduler_archive.py",
}
ALLOWED_PREFIXES = (
    "governance/archive/",
    "institutional-archive/",
)
TEXT_EXTENSIONS = {
    ".md",
    ".mdx",
    ".json",
    ".yml",
    ".yaml",
    ".sql",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".toml",
    ".sh",
}


def changed_files(root: pathlib.Path, base: str | None) -> Iterable[pathlib.Path]:
    if base and set(base) != {"0"}:
        try:
            output = subprocess.check_output(
                ["git", "diff", "--name-only", f"{base}...HEAD"],
                cwd=root,
                text=True,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError:
            output = subprocess.check_output(
                ["git", "diff", "--name-only", f"{base}..HEAD"],
                cwd=root,
                text=True,
                stderr=subprocess.STDOUT,
            )
        for name in output.splitlines():
            candidate = root / name
            if candidate.is_file():
                yield candidate
        return

    for candidate in root.rglob("*"):
        if (
            candidate.is_file()
            and ".git" not in candidate.parts
            and candidate.suffix.lower() in TEXT_EXTENSIONS
        ):
            yield candidate


def is_archive_path(relative: str) -> bool:
    return relative in ALLOWED_EXACT or relative.startswith(ALLOWED_PREFIXES)


def scan(root: pathlib.Path, base: str | None) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for path in changed_files(root, base):
        relative = path.relative_to(root).as_posix()
        if is_archive_path(relative):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(task_id in line for task_id in OLD_PROVIDER_TASK_IDS):
                violations.append(
                    {
                        "kind": "retired_provider_task_identity",
                        "path": relative,
                        "line": line_number,
                        "text": line[:320],
                    }
                )
                continue

            if (
                ROLE.search(line)
                and CLOCK.search(line)
                and not HISTORICAL_OR_PROHIBITED.search(line)
            ):
                violations.append(
                    {
                        "kind": "legacy_scheduler_semantics",
                        "path": relative,
                        "line": line_number,
                        "text": line[:320],
                    }
                )

    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--base")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    violations = scan(root, args.base)
    result = {
        "schema": "crownthrive.legacy-scheduler-recurrence-scan.v1",
        "disposition": "RETIRED_SCHEDULING_SCAFFOLDING",
        "reactivation_allowed": False,
        "base": args.base,
        "violations": violations,
        "count": len(violations),
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("PASS" if not violations else json.dumps(result, indent=2, sort_keys=True))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
