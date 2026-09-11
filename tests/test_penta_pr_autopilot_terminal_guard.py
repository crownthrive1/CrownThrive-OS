from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "penta_pr_autopilot.py"


def _load_module():
    scripts_path = str(SCRIPTS)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    spec = importlib.util.spec_from_file_location("penta_pr_autopilot_terminal_guard_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_terminal_guard_fails_closed_for_merge_and_close() -> None:
    module = _load_module()
    assert module.autonomous_terminal_mutation_guard("MERGE") == (
        False,
        "HOLD_INDEPENDENT_SEMANTIC_GATE_OWNER_RESULTS_REQUIRED",
    )
    assert module.autonomous_terminal_mutation_guard("CLOSE") == (
        False,
        "HOLD_SUCCESSOR_OR_TERMINAL_HANDOFF_PROVIDER_READBACK_REQUIRED",
    )


def test_terminal_guard_allows_only_nonterminal_autonomous_actions() -> None:
    module = _load_module()
    assert module.autonomous_terminal_mutation_guard("RESTACK") == (
        True,
        "PASS_NON_TERMINAL_AUTONOMOUS_ACTION",
    )
    assert module.autonomous_terminal_mutation_guard("NURTURE") == (
        True,
        "PASS_NON_TERMINAL_AUTONOMOUS_ACTION",
    )


def test_autopilot_source_does_not_invoke_terminal_mutators() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "lifecycle.attempt_merge(" not in source
    assert "lifecycle.pentacloser(" not in source
    assert "HOLD_INDEPENDENT_SEMANTIC_GATE_OWNER_RESULTS_REQUIRED" in source
    assert "HOLD_SUCCESSOR_OR_TERMINAL_HANDOFF_PROVIDER_READBACK_REQUIRED" in source
