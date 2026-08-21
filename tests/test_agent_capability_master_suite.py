from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import agent_capability_master_suite as suite  # noqa: E402
import archive_integrity  # noqa: E402
import framework_compiler  # noqa: E402
import internal_linkage  # noqa: E402
import supply_chain_integrity  # noqa: E402


class SuiteTests(unittest.TestCase):
    def test_suite_invariants(self) -> None:
        result = suite.validate()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["agent_count"], 26)
        self.assertEqual(result["committee_surface_count"], 14)
        self.assertEqual(result["schedule_count"], 8)
        self.assertEqual(set(result["mode_counts"]), {"rigid", "fluid", "hybrid"})

    def test_one_candidate_skill_per_agent(self) -> None:
        candidates = suite.skill_candidates()
        self.assertEqual(len(candidates["packages"]), 26)
        self.assertTrue(all(row["commercial_state"] == "HOLD" for row in candidates["packages"]))
        self.assertTrue(all(row["mcp_state"] == "DISABLED" for row in candidates["packages"]))

    def test_framework_compiler_is_deterministic_and_fail_closed(self) -> None:
        self_test = framework_compiler.self_test()
        self.assertTrue(self_test["deterministic"])
        candidate = json.loads((ROOT / "framework-candidates/thrivealumni-committee-support.v1.json").read_text(encoding="utf-8"))
        compiled = framework_compiler.compile_candidate(candidate)
        self.assertEqual(compiled["test_status"], "PASS")
        self.assertEqual(compiled["factory_integration"]["framework_count_delta"], 0)
        with self.assertRaises(framework_compiler.CompileError):
            framework_compiler.compile_candidate(dict(candidate, activation_allowed=True))

    def test_archive_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "unsafe.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../escape.txt", "blocked")
            result = archive_integrity.inspect_zip(path)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any("unsafe member" in error for error in result["errors"]))

    def test_link_application_requires_receipt_and_is_additive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "source.mdx").write_text("---\ntitle: Source\n---\n\nBody\n", encoding="utf-8")
            (root / "target.mdx").write_text("---\ntitle: Target\n---\n\nBody\n", encoding="utf-8")
            manifest = root / "links.json"
            edge = {"edge_id": "edge-1", "source": "source.mdx", "target": "target.mdx", "status": "CANDIDATE", "approval_receipt": None}
            manifest.write_text(json.dumps({"edges": [edge]}), encoding="utf-8")
            result = internal_linkage.apply_approved(root, manifest)
            self.assertEqual(result["status"], "NO_CHANGE")
            edge.update(status="APPROVED", approval_receipt="test-human-receipt")
            manifest.write_text(json.dumps({"edges": [edge]}), encoding="utf-8")
            result = internal_linkage.apply_approved(root, manifest)
            self.assertEqual(result["delete_count"], 0)
            self.assertIn("edge-1", result["applied"])
            self.assertIn("CT-MANAGED-LINK:edge-1", (root / "source.mdx").read_text(encoding="utf-8"))

    def test_suite_workflow_supply_chain_controls(self) -> None:
        result = supply_chain_integrity.inspect_workflow(ROOT / ".github/workflows/agent-capability-master-suite-governance.yml")
        self.assertNotEqual(result["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
