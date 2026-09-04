"""Tests for universal Penta PR gate-awareness and non-certifying readiness."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from penta_pr_gate_awareness import (  # noqa: E402
    GateAwarenessError,
    evidence_path,
    prepare,
    receipt_path,
    validate_projection,
)


class GateAwarenessTests(unittest.TestCase):
    def git(self, repo: Path, *args: str) -> str:
        return subprocess.check_output(
            [
                "git",
                "-c",
                "gc.auto=0",
                "-c",
                "maintenance.auto=false",
                "-c",
                "maintenance.autoDetach=false",
                *args,
            ],
            cwd=repo,
            text=True,
        ).strip()

    def fixture(self) -> tuple[Path, str, str, tempfile.TemporaryDirectory[str]]:
        # The disposable fixture repo can briefly retain Git filesystem entries
        # after a completed subprocess on hosted runners. Cleanup must never turn
        # an otherwise passing behavioral test into a CI failure.
        temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        repo = Path(temp.name)
        self.git(repo.parent, "init", str(repo))
        self.git(repo, "config", "user.email", "ci@crownthrive.invalid")
        self.git(repo, "config", "user.name", "Penta CI")
        (repo / "config").mkdir(parents=True)
        (repo / "penta" / "registry").mkdir(parents=True)
        shutil.copytree(ROOT / "penta" / "runtime", repo / "penta" / "runtime")
        (repo / "penta" / "__init__.py").write_text("", encoding="utf-8")
        shutil.copy2(ROOT / "config" / "penta_pr_gate_awareness.json", repo / "config" / "penta_pr_gate_awareness.json")
        shutil.copy2(ROOT / "penta" / "registry" / "serialized-suite.json", repo / "penta" / "registry" / "serialized-suite.json")
        workflow = repo / ".github" / "workflows" / "sample.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: sample\n", encoding="utf-8")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "base")
        base = self.git(repo, "rev-parse", "HEAD")
        workflow.write_text("name: sample\non: workflow_dispatch\n", encoding="utf-8")
        self.git(repo, "add", str(workflow.relative_to(repo)))
        self.git(repo, "commit", "-m", "subject")
        subject = self.git(repo, "rev-parse", "HEAD")
        return repo, base, subject, temp

    def test_prepare_writes_exact_head_non_certifying_readiness(self) -> None:
        repo, base, subject, temp = self.fixture()
        self.addCleanup(temp.cleanup)
        result = prepare(
            repo=repo,
            repository="crownthrive1/CrownThrive-OS",
            base=base,
            head=subject,
            number=42,
            originator="penta.sample",
            policy_path=repo / "config" / "penta_pr_gate_awareness.json",
            serialized_policy_path=repo / "penta" / "registry" / "serialized-suite.json",
        )
        self.assertTrue(result["changed"])
        self.assertFalse(result["authority_created"])
        self.assertTrue(result["independent_certification_required"])
        packet = json.loads((repo / evidence_path(42)).read_text(encoding="utf-8"))
        receipt = json.loads((repo / receipt_path(42)).read_text(encoding="utf-8"))
        self.assertEqual(packet["readiness_state"], "READY_FOR_INDEPENDENT_REVIEW")
        self.assertEqual(packet["originator_identity"], "penta.sample")
        self.assertNotIn("self_certification_state", packet)
        self.assertNotIn("self_certifier_identity", packet)
        self.assertEqual(packet["subject_head_sha"], subject)
        self.assertEqual(packet["base_sha"], base)
        self.assertFalse(packet["authority_created"])
        self.assertTrue(packet["independent_certification_required"])
        self.assertFalse(packet["provider_results_manufactured"])
        self.assertEqual(receipt["readiness"]["state"], "READY_FOR_INDEPENDENT_REVIEW")
        self.assertFalse(receipt["readiness"]["authority_created"])
        self.assertTrue(receipt["readiness"]["independent_certification_required"])
        self.assertEqual(len(receipt["changes"]), 1)
        self.assertEqual(receipt["changes"][0]["path"], ".github/workflows/sample.yml")
        self.assertEqual(receipt["changes"][0]["rollback_ref"], base)

    def test_projection_validates_after_evidence_commit(self) -> None:
        repo, base, subject, temp = self.fixture()
        self.addCleanup(temp.cleanup)
        prepare(
            repo=repo,
            repository="crownthrive1/CrownThrive-OS",
            base=base,
            head=subject,
            number=43,
            originator="penta.sample",
            policy_path=repo / "config" / "penta_pr_gate_awareness.json",
            serialized_policy_path=repo / "penta" / "registry" / "serialized-suite.json",
        )
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "evidence projection")
        projection = self.git(repo, "rev-parse", "HEAD")
        result = validate_projection(
            repo=repo,
            base=base,
            head=projection,
            number=43,
            policy_path=repo / "config" / "penta_pr_gate_awareness.json",
            serialized_policy_path=repo / "penta" / "registry" / "serialized-suite.json",
        )
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["subject_head_sha"], subject)
        self.assertEqual(result["projection_head_sha"], projection)
        self.assertFalse(result["authority_created"])
        self.assertTrue(result["independent_certification_required"])

    def test_non_evidence_change_after_projection_invalidates_readiness(self) -> None:
        repo, base, subject, temp = self.fixture()
        self.addCleanup(temp.cleanup)
        prepare(
            repo=repo,
            repository="crownthrive1/CrownThrive-OS",
            base=base,
            head=subject,
            number=44,
            originator="penta.sample",
            policy_path=repo / "config" / "penta_pr_gate_awareness.json",
            serialized_policy_path=repo / "penta" / "registry" / "serialized-suite.json",
        )
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "evidence projection")
        (repo / "sample.txt").write_text("head moved\n", encoding="utf-8")
        self.git(repo, "add", "sample.txt")
        self.git(repo, "commit", "-m", "head moved")
        head = self.git(repo, "rev-parse", "HEAD")
        with self.assertRaises(GateAwarenessError):
            validate_projection(
                repo=repo,
                base=base,
                head=head,
                number=44,
                policy_path=repo / "config" / "penta_pr_gate_awareness.json",
                serialized_policy_path=repo / "penta" / "registry" / "serialized-suite.json",
            )


if __name__ == "__main__":
    unittest.main()
