import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from penta.runtime.serialized import (
    ConflictError,
    DeletedError,
    IntegrityError,
    PentaSerializedStore,
    ValidationError,
    git_gate,
)


class PentaSerializedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = PentaSerializedStore(Path(self.tmp.name) / "store")
        self.store.init()

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_update_requires_expected_revision(self):
        first = self.store.put(
            "docs:policy:alpha", "PentaScribe", "1.0.0",
            {
                "record_id": "alpha",
                "record_type": "policy",
                "source_refs": ["docs/a.md"],
                "lifecycle_state": "ACTIVE",
            },
            actor="test",
        )
        self.assertEqual(first.event["operation"], "create")
        with self.assertRaises(ConflictError):
            self.store.put(
                "docs:policy:alpha", "PentaScribe", "1.0.1",
                {
                    "record_id": "alpha",
                    "record_type": "policy",
                    "source_refs": ["docs/a.md"],
                    "lifecycle_state": "ACTIVE",
                },
                actor="test",
                reason="change",
            )
        second = self.store.put(
            "docs:policy:alpha", "PentaScribe", "1.0.1",
            {
                "record_id": "alpha",
                "record_type": "policy",
                "source_refs": ["docs/a.md"],
                "lifecycle_state": "ACTIVE",
            },
            actor="test",
            reason="change",
            expected_revision=first.event["revision_id"],
        )
        self.assertEqual(second.event["parent_revision"], first.event["revision_id"])

    def test_stale_write_fails(self):
        first = self.store.put("asset:x", "Generic", "1", {"v": 1}, actor="test")
        second = self.store.put(
            "asset:x", "Generic", "2", {"v": 2},
            actor="test", reason="update", expected_revision=first.event["revision_id"]
        )
        with self.assertRaises(ConflictError):
            self.store.put(
                "asset:x", "Generic", "3", {"v": 3},
                actor="test", reason="stale", expected_revision=first.event["revision_id"]
            )
        self.assertEqual(self.store.get("asset:x")["revision_id"], second.event["revision_id"])

    def test_tombstone_and_restore_preserve_history(self):
        first = self.store.put("asset:x", "Generic", "1", {"v": 1}, actor="test")
        tomb = self.store.tombstone(
            "asset:x", expected_revision=first.event["revision_id"],
            actor="test", reason="retired"
        )
        with self.assertRaises(DeletedError):
            self.store.get("asset:x")
        with self.assertRaises(DeletedError):
            self.store.put(
                "asset:x", "Generic", "2", {"v": 2},
                actor="test", reason="blind resurrection",
                expected_revision=tomb.event["revision_id"]
            )
        restored = self.store.restore(
            "asset:x", expected_revision=tomb.event["revision_id"],
            actor="test", reason="rollback retirement"
        )
        self.assertEqual(restored.event["payload"], {"v": 1})
        self.assertEqual([e["operation"] for e in self.store.history("asset:x")],
                         ["create", "tombstone", "restore"])

    def test_idempotency_is_replay_safe(self):
        first = self.store.put(
            "asset:x", "Generic", "1", {"v": 1},
            actor="test", idempotency_key="req-1"
        )
        replay = self.store.put(
            "asset:x", "Generic", "1", {"v": 1},
            actor="test", idempotency_key="req-1"
        )
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(first.event["event_id"], replay.event["event_id"])
        with self.assertRaises(ConflictError):
            self.store.put(
                "asset:x", "Generic", "9", {"v": 9},
                actor="test", reason="different", idempotency_key="req-1",
                expected_revision=first.event["revision_id"],
            )

    def test_family_adapter_validation(self):
        with self.assertRaises(ValidationError):
            self.store.put(
                "version:x", "PentaVersion", "1.0.0",
                {"subject_id": "x"}, actor="test"
            )
        event = self.store.put(
            "version:x", "PentaVersion", "1.0.0",
            {
                "subject_id": "x",
                "version": "1.0.0",
                "version_scheme": "semver",
                "lifecycle_state": "ACTIVE",
                "effective_at": "2026-08-26T00:00:00Z",
            },
            actor="test"
        )
        self.assertEqual(event.event["kind"], "PentaVersion")

    def test_verify_detects_tamper(self):
        self.store.put("asset:x", "Generic", "1", {"v": 1}, actor="test")
        self.store.verify()
        ledger = self.store.ledger
        event = json.loads(ledger.read_text().splitlines()[0])
        event["payload"]["v"] = 999
        ledger.write_text(json.dumps(event) + "\n")
        with self.assertRaises(IntegrityError):
            self.store.verify()

    def test_snapshot_is_content_addressed(self):
        self.store.put("asset:x", "Generic", "1", {"v": 1}, actor="test")
        snap = self.store.snapshot(actor="test", reason="recovery baseline")
        self.assertEqual(snap["schema"], "crownthrive.penta.serialized.snapshot/v1")
        self.assertTrue(snap["snapshot_hash"])
        self.assertEqual(len(list(self.store.snapshots.glob("*.json"))), 1)

    def test_hard_delete_not_exposed(self):
        meta = self.store.init()
        self.assertFalse(meta["hard_delete"])
        self.assertFalse(hasattr(self.store, "delete"))

    def test_git_gate_requires_receipt_for_protected_modify(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Penta Test"], cwd=repo, check=True)
            (repo / "canonical.txt").write_text("one\n")
            (repo / "policy.json").write_text(json.dumps({
                "schema": "crownthrive.penta.serialized.policy/v1",
                "protected_patterns": ["canonical.txt"],
                "receipt_glob": "penta/continuity/receipts/*.json",
            }))
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
            base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            previous_blob = subprocess.check_output(
                ["git", "rev-parse", f"{base}:canonical.txt"], cwd=repo, text=True
            ).strip()

            (repo / "canonical.txt").write_text("two\n")
            subprocess.run(["git", "add", "canonical.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "modify"], cwd=repo, check=True)
            no_receipt_head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo, text=True
            ).strip()
            with self.assertRaises(IntegrityError):
                git_gate(repo, base, no_receipt_head, repo / "policy.json")

            new_blob = subprocess.check_output(
                ["git", "rev-parse", f"{no_receipt_head}:canonical.txt"], cwd=repo, text=True
            ).strip()
            receipt_dir = repo / "penta/continuity/receipts"
            receipt_dir.mkdir(parents=True)
            (receipt_dir / "r1.json").write_text(json.dumps({
                "schema": "crownthrive.penta.serialized.git-receipt/v1",
                "receipt_id": "r1",
                "changes": [{
                    "path": "canonical.txt",
                    "operation": "modify",
                    "previous_blob_sha": previous_blob,
                    "new_blob_sha": new_blob,
                    "reason": "controlled update",
                    "rollback_ref": base,
                }],
            }))
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "receipt"], cwd=repo, check=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            result = git_gate(repo, base, head, repo / "policy.json")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["continuity_checked"], 1)


if __name__ == "__main__":
    unittest.main()
