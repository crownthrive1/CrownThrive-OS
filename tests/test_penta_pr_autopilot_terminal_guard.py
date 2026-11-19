from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "penta_pr_autopilot.py"


class PentaPrAutopilotTerminalGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        scripts_path = str(SCRIPTS)
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        spec = importlib.util.spec_from_file_location(
            "penta_pr_autopilot_terminal_guard_test",
            SCRIPT,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("unable_to_load_penta_pr_autopilot")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.module = module

    def test_merge_and_close_fail_closed_with_typed_holds(self) -> None:
        self.assertEqual(
            self.module.autonomous_terminal_mutation_guard("MERGE"),
            (False, "HOLD_INDEPENDENT_SEMANTIC_GATE_OWNER_RESULTS_REQUIRED"),
        )
        self.assertEqual(
            self.module.autonomous_terminal_mutation_guard("CLOSE"),
            (False, "HOLD_SUCCESSOR_OR_TERMINAL_HANDOFF_PROVIDER_READBACK_REQUIRED"),
        )

    def test_only_exact_nonterminal_allowlist_passes(self) -> None:
        for disposition in ("RESTACK", "NURTURE"):
            with self.subTest(disposition=disposition):
                self.assertEqual(
                    self.module.autonomous_terminal_mutation_guard(disposition),
                    (True, "PASS_NONTERMINAL_AUTONOMOUS_ACTION"),
                )

    def test_unknown_missing_and_malformed_dispositions_fail_closed(self) -> None:
        unsupported = (
            None,
            "",
            "UNKNOWN",
            "DELETE",
            "merge",
            "RESTACK ",
            "NURTURE\\t",
            0,
            False,
            [],
            {},
        )
        for disposition in unsupported:
            with self.subTest(disposition=repr(disposition)):
                self.assertEqual(
                    self.module.autonomous_terminal_mutation_guard(disposition),
                    (False, "HOLD_UNSUPPORTED_OR_MISSING_DISPOSITION"),
                )

    def test_autopilot_source_never_invokes_terminal_mutators(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("lifecycle.attempt_merge(", source)
        self.assertNotIn("lifecycle.pentacloser(", source)
        self.assertIn("AUTONOMOUS_NONTERMINAL_ALLOWLIST", source)
        self.assertIn("HOLD_UNSUPPORTED_OR_MISSING_DISPOSITION", source)


if __name__ == "__main__":
    unittest.main()
