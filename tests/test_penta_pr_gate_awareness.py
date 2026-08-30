"""Tests for universal Penta PR gate-awareness originator-readiness projection."""

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
    LEGACY_SELF_CERT_STATE,
    READINESS_STATE,
    evidence_path,
    prepare,
    receipt_path,
    sha256_json,
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
        temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        repo = Path(temp.name)
        self.git(repo.parent, "init", str(repo))
        self.git(repo, "config", "user.email", "ci@crownthrive.invalid")
        self.git(repo, "config", "user.name", "Penta CI")
        (repo / "config").mkdir(parents=True)
        (repo / "penta" / "registry").mkdir(parents=True)
        shutil.copytree(ROOT / "penta" / "runtime", repo / "penta" / "runtime")
        (repo / "penta" / "__init__.py").write_text("", encoding="utf-8")
        shutil.copy2(
            ROOT / "config" / "penta_pr_gate_awareness.json",
            repo / "config" / "penta_pr_gate_awareness.json",
        )
        shutil.copy2(
            ROOT / "penta" / "registry" / "serialized-suite.json",
            repo / "penta" / "registry" / "serialized-suite.json",
        )
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

    def prepare_fixture(self, number: int):
        repo, base, subject, temp = self.fixture()
        self.addCleanup(temp.cleanup)
        result = prepare(
            repo=repo,
            repository="crownthrive1/CrownThrive-OS",
            base=base,
            head=subject,
            number=number,
            originator="penta.sample",
            policy_path=repo / "config" / "penta_pr_gate_awareness.json",
            serialized_policy_path=repo / "penta" / "registry" / "serialized-suite.json",
        )
        return repo, base, subject, result

    def test_prepare_records_readiness_without_certification_authority(self) -> None:
        repo, base, subject, result = self.prepare_fixture(42)
        self.assertTrue(result["changed"])
        packet = json.loads((repo / evidence_path(42)).read_text(encoding="utf-8"))
        receipt = json.loads((repo / receipt_path(42)).read_text(encoding="utf-8"))

        self.assertEqual(packet["originator_readiness_state"], READINESS_STATE)
        self.assertEqual(packet["self_certification_state"], LEGACY_SELF_CERT_STATE)
        self.assertNotEqual(packet["self_certification_state"], "SELF_CERTIFIED")
        self.assertEqual(packet["actor_class"], "originator_same_lane")
        self.assertFalse(packet["independent_certification"])
        self.assertFalse(packet["authority_created"])
        self.assertFalse(packet["merge_authority"])
        self.assertFalse(packet["release_authority"])
        self.assertTrue(packet["requires_pentacertifier"])
        self.assertFalse(packet["provider_results_manufactured"])
        self.assertFalse(packet["required_gate_bypass"])
        self.assertEqual(packet["subject_head_sha"], subject)
        self.assertEqual(packet["base_sha"], base)

        self.assertEqual(receipt["originator_readiness"]["state"], READINESS_STATE)
        self.assertEqual(receipt["self_certification"]["state"], LEGACY_SELF_CERT_STATE)
        self.assertTrue(receipt["self_certification"]["legacy_alias_only"])
        self.assertFalse(receipt["self_certification"]["independent_certification"])
        self.assertFalse(receipt["self_certification"]["merge_authority"])
        self.assertTrue(receipt["self_certification"]["requires_pentacertifier"])
        self.assertEqual(len(receipt["changes"]), 1)
        self.assertEqual(receipt["changes"][0]["path"], ".github/workflows/sample.yml")
        self.assertEqual(receipt["changes"][0]["rollback_ref"], base)

    def test_projection_validates_after_readiness_commit(self) -> None:
        repo, base, subject, _ = self.prepare_fixture(43)
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "readiness evidence projection")
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
        self.assertFalse(result["independent_certification"])
        self.assertFalse(result["merge_authority"])
        self.assertFalse(result["release_authority"])
        self.assertTrue(result["requires_pentacertifier"])
        self.assertEqual(
            result["final_institutional_certification"],
            "NOT_GRANTED_REQUIRES_INDEPENDENT_PENTACERTIFIER_AND_DAIL",
        )

    def test_legacy_self_certified_state_is_rejected(self) -> None:
        repo, base, _, _ = self.prepare_fixture(44)
        packet_path = repo / evidence_path(44)
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["self_certification_state"] = "SELF_CERTIFIED"
        packet["evidence_sha256"] = sha256_json({k: v for k, v in packet.items() if k != "evidence_sha256"})
        packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "legacy ambiguous evidence")
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

    def test_attempted_certification_or_authority_claim_is_rejected(self) -> None:
        repo, base, _, _ = self.prepare_fixture(45)
        packet_path = repo / evidence_path(45)
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["independent_certification"] = True
        packet["merge_authority"] = True
        packet["evidence_sha256"] = sha256_json({k: v for k, v in packet.items() if k != "evidence_sha256"})
        packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "attempt authority escalation")
        head = self.git(repo, "rev-parse", "HEAD")
        with self.assertRaises(GateAwarenessError):
            validate_projection(
                repo=repo,
                base=base,
                head=head,
                number=45,
                policy_path=repo / "config" / "penta_pr_gate_awareness.json",
                serialized_policy_path=repo / "penta" / "registry" / "serialized-suite.json",
            )

    def test_non_evidence_change_after_projection_invalidates_readiness(self) -> None:
        repo, base, _, _ = self.prepare_fixture(46)
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "readiness evidence projection")
        (repo / "sample.txt").write_text("head moved\n", encoding="utf-8")
        self.git(repo, "add", "sample.txt")
        self.git(repo, "commit", "-m", "head moved")
        head = self.git(repo, "rev-parse", "HEAD")
        with self.assertRaises(GateAwarenessError):
            validate_projection(
                repo=repo,
                base=base,
                head=head,
                number=46,
                policy_path=repo / "config" / "penta_pr_gate_awareness.json",
                serialized_policy_path=repo / "penta" / "registry" / "serialized-suite.json",
            )


if __name__ == "__main__":
    unittest.main()
