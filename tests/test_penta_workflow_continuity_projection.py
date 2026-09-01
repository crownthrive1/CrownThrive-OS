import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from penta.runtime.serialized import IntegrityError, git_gate
from penta.runtime.serialized.workflow_projection import project_workflow_receipt


class WorkflowContinuityProjectionTests(unittest.TestCase):
    def _repo(self, protected_patterns=None):
        td = tempfile.TemporaryDirectory()
        repo = Path(td.name)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Penta Test"], cwd=repo, check=True)
        policy = repo / "policy.json"
        policy.write_text(json.dumps({
            "schema": "crownthrive.penta.serialized.policy/v1",
            "protected_patterns": protected_patterns or [".github/workflows/**"],
            "receipt_glob": "penta/continuity/receipts/*.json",
        }))
        return td, repo, policy

    @staticmethod
    def _commit(repo: Path, message: str) -> str:
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", message], cwd=repo, check=True)
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()

    def test_workflow_modify_projects_valid_exact_head_receipt(self):
        td, repo, policy = self._repo()
        try:
            workflow = repo / ".github/workflows/gate.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("name: old\n")
            base = self._commit(repo, "base")
            workflow.write_text("name: new\n")
            head = self._commit(repo, "modify workflow")

            receipt = repo / "penta/continuity/receipts/ci.json"
            result = project_workflow_receipt(
                repo, base, head, policy, receipt, actor="test"
            )
            self.assertTrue(result["generated"])
            self.assertEqual(result["eligible_changes"], 1)
            gate = git_gate(repo, base, head, policy)
            self.assertEqual(gate["status"], "PASS")
            self.assertEqual(gate["continuity_checked"], 1)
        finally:
            td.cleanup()

    def test_workflow_delete_is_not_auto_projected(self):
        td, repo, policy = self._repo()
        try:
            workflow = repo / ".github/workflows/gate.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("name: old\n")
            base = self._commit(repo, "base")
            workflow.unlink()
            head = self._commit(repo, "delete workflow")

            receipt = repo / "penta/continuity/receipts/ci.json"
            result = project_workflow_receipt(repo, base, head, policy, receipt)
            self.assertFalse(result["generated"])
            self.assertFalse(receipt.exists())
            with self.assertRaises(IntegrityError):
                git_gate(repo, base, head, policy)
        finally:
            td.cleanup()

    def test_non_workflow_protected_modify_is_not_auto_projected(self):
        td, repo, policy = self._repo(
            [".github/workflows/**", "standards/**"]
        )
        try:
            standard = repo / "standards/control.md"
            standard.parent.mkdir(parents=True)
            standard.write_text("one\n")
            base = self._commit(repo, "base")
            standard.write_text("two\n")
            head = self._commit(repo, "modify standard")

            receipt = repo / "penta/continuity/receipts/ci.json"
            result = project_workflow_receipt(repo, base, head, policy, receipt)
            self.assertFalse(result["generated"])
            self.assertFalse(receipt.exists())
            with self.assertRaises(IntegrityError):
                git_gate(repo, base, head, policy)
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
