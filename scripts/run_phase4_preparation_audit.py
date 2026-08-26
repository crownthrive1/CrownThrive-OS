#!/usr/bin/env python3
"""Run the CrownThrive Phase-4 preparation audit over the existing Phase-3 execution baseline."""

from __future__ import annotations

import json
import os
import subprocess
import sys
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


def main() -> int:
    results = [
        run("v4_gate_contract", [PYTHON, "scripts/validate_gate_registry_v4.py"]),
        run("phase3_execution_baseline", [PYTHON, "scripts/run_phase3_convergence_audit.py"]),
    ]
    failures = [item for item in results if not item[1]]

    receipt = {
        "schema": "ct.audit.phase4-preparation.local.v4",
        "status": "PASS" if not failures else "FAIL",
        "current_institutional_phase": "Phase 3 — Execute",
        "target_phase": "Phase 4 — preparation",
        "gate_contract_version": "4.0.0",
        "accepted_contract_generations": [1, 2, 3, 4],
        "phase3_execution_authority_preserved": True,
        "legacy_workflow_names_preserved": True,
        "stable_required_status_context_preserved": True,
        "network_probes_disabled": True,
        "failed": [label for label, _passed, _detail in failures],
        "promotion_semantics": "preparation_only; no blanket Phase-4 activation or authority promotion",
    }
    print(json.dumps(receipt, sort_keys=True))

    for label, _passed, detail in failures:
        print(f"\n--- {label} ---\n{detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
