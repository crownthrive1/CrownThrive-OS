from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "runtime" / "skills_fleet_gap_closure.py"
SPEC = importlib.util.spec_from_file_location("skills_fleet_gap_closure", RUNTIME_PATH)
runtime = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(runtime)


class SkillsFleetGapClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = runtime.load_registry(ROOT)

    def task(self, **overrides):
        base = {
            "task_id": "ct.task.test.0001",
            "directive_id": "ct.directive.test",
            "skill_id": "ct.skill.convergence.skill-fleet-gap-analyzer.v1",
            "subject_id": "ct.subject.test",
            "source_ref": "git:0123456789abcdef",
            "requested_authority": "D1",
            "mode": "dry-run",
            "observed_at": "2026-09-02T20:30:00Z",
            "inputs": {"scope": "test"},
            "evidence_refs": ["git:0123456789abcdef"],
        }
        base.update(overrides)
        return base

    def test_registry_has_unique_24_skills_and_docs(self):
        runtime.validate_registry(self.registry, root=ROOT)
        self.assertEqual(24, len(self.registry["skills"]))
        ids = [item["skill_id"] for item in self.registry["skills"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_registry_defaults_resolve_for_list(self):
        first = runtime.find_skill(self.registry, self.registry["skills"][0]["skill_id"])
        self.assertEqual("candidate", first["lifecycle_state"])
        self.assertEqual("D2", first["max_authority"])
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = runtime.cmd_list(self.registry)
        rows = json.loads(buffer.getvalue())
        self.assertEqual(0, result)
        self.assertEqual(24, len(rows))
        self.assertTrue(all(row["state"] == "candidate" for row in rows))

    def test_plan_is_secret_free_and_side_effect_free(self):
        receipt = runtime.plan_task(self.task(), self.registry)
        self.assertEqual("PLANNED", receipt["state"])
        self.assertFalse(receipt["side_effects"])
        self.assertFalse(receipt["provider_invoked"])
        self.assertRegex(receipt["canonical_fingerprint"], r"^[a-f0-9]{64}$")

    def test_missing_evidence_produces_hold(self):
        receipt = runtime.plan_task(self.task(evidence_refs=[]), self.registry)
        self.assertEqual("HOLD", receipt["state"])
        self.assertIn("NO_EVIDENCE_REFS_SUPPLIED_FOR_EFFECT_CLAIM", receipt["hold_reasons"])

    def test_d3_is_denied(self):
        with self.assertRaisesRegex(runtime.ContractError, "INVALID_AUTHORITY"):
            runtime.plan_task(self.task(requested_authority="D3"), self.registry)

    def test_live_mode_is_denied(self):
        with self.assertRaisesRegex(runtime.ContractError, "LIVE_MODE_DISABLED"):
            runtime.plan_task(self.task(mode="live"), self.registry)

    def test_secret_key_is_denied(self):
        with self.assertRaisesRegex(runtime.ContractError, "SECRET_BEARING_INPUT_REJECTED"):
            runtime.plan_task(self.task(inputs={"api_token": "do-not-store"}), self.registry)

    def test_secret_value_is_denied(self):
        with self.assertRaisesRegex(runtime.ContractError, "SECRET_BEARING_INPUT_REJECTED"):
            runtime.plan_task(self.task(inputs={"value": "sk-proj-abcdefghijklmnop"}), self.registry)

    def test_fingerprint_is_deterministic(self):
        one = runtime.plan_task(self.task(), self.registry)
        two = runtime.plan_task(self.task(), self.registry)
        self.assertEqual(one["canonical_fingerprint"], two["canonical_fingerprint"])
        self.assertEqual(one["receipt_id"], two["receipt_id"])


if __name__ == "__main__":
    unittest.main()
