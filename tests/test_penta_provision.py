from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from penta.runtime.provision import ProvisionError, git_blob_sha, provision


class PentaProvisionTests(unittest.TestCase):
    def _repo(self):
        td = tempfile.TemporaryDirectory()
        repo = Path(td.name)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@crownthrive.local"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "PentaTest"], cwd=repo, check=True)
        (repo / "seed.txt").write_text("seed\n")
        manifest = repo / "developers/manifests/supabase-production-convergence-state.v1.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({
            "migration_custody": {
                "provider_readback_scope": "supabase_migrations.schema_migrations",
                "provider_migration_count": 999,
                "provider_last_migration_version": "20260827172622",
                "provider_last_migration_name": "canonical_os_repository_function_rebind",
                "repository_migration_file_count": 0,
                "default_branch": "main",
                "default_branch_status": "MIGRATIONS_FAILED",
                "last_observed_error": "Remote migration versions not found in local migrations directory.",
                "gate": "HOLD",
                "owner": "test",
                "required_resolution": "provider reconciliation required"
            }
        }, indent=2) + "\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
        subprocess.run(["git", "checkout", "-qb", "preserved/source"], cwd=repo, check=True)
        payload = b"authoritative\n"
        src = repo / "archive" / "artifact.sql"
        src.parent.mkdir(parents=True)
        src.write_bytes(payload)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "preserve"], cwd=repo, check=True)
        subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
        return td, repo, payload

    def test_restores_exact_declared_blob_and_is_idempotent(self):
        td, repo, payload = self._repo()
        self.addCleanup(td.cleanup)
        req = {"request_id": "t1", "artifacts": [{
            "destination_path": "supabase/migrations/artifact.sql",
            "source_ref": "preserved/source",
            "source_path": "archive/artifact.sql",
            "expected_blob_sha": git_blob_sha(payload),
        }]}
        first = provision(repo, req, apply=True)
        second = provision(repo, req, apply=True)
        self.assertEqual(first["changed"], 1)
        self.assertEqual(second["changed"], 0)
        self.assertEqual(second["artifacts"][0]["state"], "ALREADY_PRESENT")

    def test_refuses_mismatched_destination(self):
        td, repo, payload = self._repo()
        self.addCleanup(td.cleanup)
        dest = repo / "supabase/migrations/artifact.sql"
        dest.parent.mkdir(parents=True)
        dest.write_text("wrong\n")
        req = {"request_id": "t2", "artifacts": [{
            "destination_path": "supabase/migrations/artifact.sql",
            "source_ref": "preserved/source",
            "source_path": "archive/artifact.sql",
            "expected_blob_sha": git_blob_sha(payload),
        }]}
        with self.assertRaises(ProvisionError):
            provision(repo, req, apply=True)

    def test_refreshes_only_local_custody_and_preserves_provider_hold(self):
        td, repo, payload = self._repo()
        self.addCleanup(td.cleanup)
        req = {"request_id": "t3", "artifacts": [{
            "destination_path": "supabase/migrations/artifact.sql",
            "source_ref": "preserved/source",
            "source_path": "archive/artifact.sql",
            "expected_blob_sha": git_blob_sha(payload),
        }]}
        receipt = provision(repo, req, apply=True, refresh_local_custody=True)
        custody = json.loads((repo / "developers/manifests/supabase-production-convergence-state.v1.json").read_text())["migration_custody"]
        self.assertEqual(custody["repository_migration_file_count"], 1)
        self.assertEqual(custody["provider_migration_count"], 999)
        self.assertEqual(custody["gate"], "HOLD")
        self.assertEqual(custody["default_branch_status"], "MIGRATIONS_FAILED")
        self.assertFalse(receipt["provider_evidence_mutated"])
        self.assertFalse(receipt["hold_promotion"])


if __name__ == "__main__":
    unittest.main()
