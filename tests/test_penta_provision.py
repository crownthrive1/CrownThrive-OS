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


if __name__ == "__main__":
    unittest.main()
