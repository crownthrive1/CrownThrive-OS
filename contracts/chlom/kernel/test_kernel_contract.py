from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reference.chlom_runtime import CHLOMReferenceEngine
from reference.chlom_runtime.model import KernelContractError

POLICY = ROOT / "reference" / "chlom_runtime" / "policies" / "core.v0.json"
FIXTURE = Path(__file__).with_name("conformance.v1.json")


def _set_path(value: dict, dotted: str, replacement) -> None:
    current = value
    parts = dotted.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = replacement


def _remove_path(value: dict, dotted: str) -> None:
    current = value
    parts = dotted.split(".")
    for part in parts[:-1]:
        current = current[part]
    current.pop(parts[-1], None)


class KernelContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.engine = CHLOMReferenceEngine(self.bundle["rules"])

    def materialize(self, case: dict) -> dict:
        request = copy.deepcopy(self.fixture["base_request"])
        for dotted in case.get("remove", []):
            _remove_path(request, dotted)
        for dotted, replacement in case.get("set", {}).items():
            _set_path(request, dotted, replacement)
        return request

    def test_conformance_cases(self):
        for case in self.fixture["cases"]:
            with self.subTest(case_id=case["case_id"]):
                self.engine = CHLOMReferenceEngine(self.bundle["rules"])
                request = self.materialize(case)
                mode = case.get("mode", "single")
                expected_error = case.get("expected_error")

                if mode == "retry_same":
                    first = self.engine.evaluate(copy.deepcopy(request))
                    second = self.engine.evaluate(copy.deepcopy(request))
                    self.assertEqual(first.effect, case["expected_effect"])
                    self.assertEqual(first.decision_id, second.decision_id)
                    self.assertEqual(first.event_id, second.event_id)
                    self.assertEqual(
                        len(self.engine.ledger.events), case["expected_ledger_events"]
                    )
                    continue

                if mode == "reuse_key_with_patch":
                    self.engine.evaluate(copy.deepcopy(request))
                    conflicting = copy.deepcopy(request)
                    for dotted, replacement in case["conflicting_set"].items():
                        _set_path(conflicting, dotted, replacement)
                    with self.assertRaisesRegex(KernelContractError, expected_error):
                        self.engine.evaluate(conflicting)
                    continue

                if expected_error:
                    with self.assertRaisesRegex(KernelContractError, expected_error):
                        self.engine.evaluate(request)
                    continue

                decision = self.engine.evaluate(request)
                self.assertEqual(decision.effect, case["expected_effect"])
                if "expected_reason" in case:
                    self.assertIn(case["expected_reason"], decision.reasons)
                self.assertEqual(
                    decision.contract_id, "ct.contract.chlom.kernel.decision.v1"
                )
                self.assertEqual(
                    decision.request_contract_id, "ct.contract.chlom.kernel.request.v1"
                )
                self.assertEqual(decision.prototype_state, "phase_2_99_semantic_oracle")
                self.assertTrue(self.engine.ledger.verify())


if __name__ == "__main__":
    unittest.main()
