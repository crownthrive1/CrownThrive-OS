#!/usr/bin/env python3
"""Run the local, secret-free CrownThrive Phase 3 convergence audit."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
ENV = {**os.environ, "PENTA_DISABLE_NETWORK_PROBES": "1"}


def run(label: str, command: list[str]) -> tuple[str, bool, str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=ENV,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return label, completed.returncode == 0, completed.stdout.strip()


def static_integrity() -> tuple[str, bool, str]:
    counts = {"json": 0, "python": 0, "svg": 0, "shell": 0}
    errors: list[str] = []
    ignored = {".git", "node_modules", "__pycache__"}

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in ignored for part in path.parts):
            continue
        relative = path.relative_to(ROOT).as_posix()
        try:
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
                counts["json"] += 1
            elif path.suffix == ".py":
                ast.parse(path.read_text(encoding="utf-8"), filename=relative)
                counts["python"] += 1
            elif path.suffix == ".svg":
                ET.parse(path)
                counts["svg"] += 1
            elif path.suffix == ".sh":
                result = subprocess.run(
                    ["bash", "-n", str(path)],
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                counts["shell"] += 1
                if result.returncode:
                    errors.append(f"{relative}: {result.stdout.strip()}")
        except (OSError, SyntaxError, ValueError, json.JSONDecodeError, ET.ParseError) as error:
            errors.append(f"{relative}: {error}")

    detail = json.dumps({"counts": counts, "errors": errors}, sort_keys=True)
    return "static_integrity", not errors, detail


def main() -> int:
    checks: list[tuple[str, list[str]]] = [
        (
            "unit_tests",
            [PYTHON, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        ),
        ("retired_phase_aliases", [PYTHON, "scripts/penta_gap_closure.py", ".", "--json"]),
    ]

    for validator in sorted((ROOT / "scripts").glob("validate_*.py")):
        checks.append((f"validator:{validator.name}", [PYTHON, str(validator.relative_to(ROOT))]))

    for self_test in (
        "scripts/classify_governance_run.py",
        "scripts/evaluate_ct_p299_machine_exit.py",
        "scripts/governed_current_pr_preflight_v2.py",
        "scripts/governed_merge_decision.py",
        "scripts/penta_institutional_runtime.py",
        "scripts/pentamation_runtime.py",
        "scripts/resolve_pm_notification_recipients.py",
        "scripts/security_self_heal_plan.py",
        "scripts/validate_phase_2_99_hard_exit_ledger.py",
        "runtime/penta_observability.py",
    ):
        checks.append((f"self_test:{self_test}", [PYTHON, self_test, "--self-test"]))

    for javascript_test in (
        "contracts/mcp/test-external-certification-security-hold.mjs",
        "developers/reference/chlom-wallet/continuity/test-continuity-penta-v2.mjs",
    ):
        checks.append((f"node_test:{javascript_test}", ["node", javascript_test]))

    results = [static_integrity()]
    results.extend(run(label, command) for label, command in checks)
    failures = [result for result in results if not result[1]]

    receipt = {
        "schema": "ct.audit.phase3-convergence.local.v1",
        "status": "PASS" if not failures else "FAIL",
        "institutional_phase": "Phase 3 — Execute",
        "network_probes_disabled": True,
        "checks": len(results),
        "validators": len(list((ROOT / "scripts").glob("validate_*.py"))),
        "failed": [label for label, _passed, _detail in failures],
        "provider_scope": "local_secret_free_only; provider CI/readback remains independent",
    }
    print(json.dumps(receipt, sort_keys=True))

    for label, _passed, detail in failures:
        print(f"\n--- {label} ---\n{detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
